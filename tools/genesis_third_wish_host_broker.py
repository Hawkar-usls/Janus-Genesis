# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.41 — Third Wish host broker.

Real typed doors for WEB.HTTP.GET, DNS.RESOLVE, workspace filesystem access and
containerized Python computation. This is deliberately not a universal shell.

Important separation law: PROCESS.EXECUTE_SANDBOXED mounts no host workspace.
If JANUS wants to process a file it must cross FILESYSTEM.READ separately and
pass the resulting non-secret data into a computation capsule. One capability
therefore cannot silently absorb another.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    ThirdWishCapabilityFabric,
)

HOST_BROKER_VERSION = "18.7.41"
DEFAULT_MAX_HTTP_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_PROCESS_OUTPUT_BYTES = 1024 * 1024
DEFAULT_DOCKER_IMAGE = "python:3.11-alpine"


class HostBrokerError(RuntimeError):
    pass


class Resolver(Protocol):
    def resolve(self, host: str, port: int) -> list[str]: ...


class HTTPSOneHopClient(Protocol):
    def request_once(self, *, url: str, resolved_ip: str, timeout_seconds: float, max_bytes: int) -> Mapping[str, Any]: ...


class ProcessRunner(Protocol):
    def run_python(
        self,
        *,
        code: str,
        argv: Sequence[str],
        timeout_seconds: float,
        memory_mb: int,
        cpus: float,
        pids_limit: int,
    ) -> Mapping[str, Any]: ...


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _require(parameters: Mapping[str, Any], key: str) -> Any:
    if key not in parameters:
        raise HostBrokerError(f"MISSING_PARAMETER:{key}")
    return parameters[key]


def _bounded_int(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise HostBrokerError(f"{name}_MUST_BE_INTEGER") from exc
    if not minimum <= parsed <= maximum:
        raise HostBrokerError(f"{name}_OUT_OF_RANGE")
    return parsed


def _bounded_float(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise HostBrokerError(f"{name}_MUST_BE_NUMBER") from exc
    if not minimum <= parsed <= maximum:
        raise HostBrokerError(f"{name}_OUT_OF_RANGE")
    return parsed


_BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".home.arpa", ".lan")


def _validate_public_hostname(host: str) -> str:
    value = str(host).strip().rstrip(".").lower()
    if not value:
        raise HostBrokerError("HOST_REQUIRED")
    if value == "localhost" or value.endswith(_BLOCKED_HOST_SUFFIXES):
        raise HostBrokerError("LOCAL_OR_INTERNAL_HOST_BLOCKED")
    if len(value) > 253:
        raise HostBrokerError("HOST_TOO_LONG")
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        if "." not in value:
            raise HostBrokerError("SINGLE_LABEL_HOST_BLOCKED")
        labels = value.split(".")
        if any(not label or len(label) > 63 for label in labels):
            raise HostBrokerError("INVALID_HOSTNAME")
        return value
    if not ip.is_global:
        raise HostBrokerError("NON_PUBLIC_IP_BLOCKED")
    return value


def _public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def _parse_https_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(str(url).strip())
    if parsed.scheme.lower() != "https":
        raise HostBrokerError("HTTPS_ONLY")
    if not parsed.hostname:
        raise HostBrokerError("URL_HOST_REQUIRED")
    if parsed.username is not None or parsed.password is not None:
        raise HostBrokerError("URL_USERINFO_BLOCKED")
    if parsed.fragment:
        raise HostBrokerError("URL_FRAGMENT_BLOCKED")
    if (parsed.port or 443) != 443:
        raise HostBrokerError("NON_STANDARD_HTTPS_PORT_BLOCKED")
    _validate_public_hostname(parsed.hostname)
    return parsed


def _path_and_query(parsed: urllib.parse.SplitResult) -> str:
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return path


class SystemResolver:
    def resolve(self, host: str, port: int) -> list[str]:
        host = _validate_public_hostname(host)
        rows = socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)
        addresses: list[str] = []
        for row in rows:
            address = str(row[4][0])
            if address not in addresses:
                addresses.append(address)
        if not addresses:
            raise HostBrokerError("DNS_NO_ADDRESSES")
        return addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, resolved_ip: str, timeout: float) -> None:
        super().__init__(host=host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.resolved_ip = str(resolved_ip)

    def connect(self) -> None:  # pragma: no cover - live CI exercises this
        raw = socket.create_connection((self.resolved_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class PinnedHTTPSClient:
    SAFE_HEADERS = ("content-type", "content-length", "etag", "last-modified", "location")

    def request_once(self, *, url: str, resolved_ip: str, timeout_seconds: float, max_bytes: int) -> Mapping[str, Any]:
        parsed = _parse_https_url(url)
        if not _public_ip(resolved_ip):
            raise HostBrokerError("NON_PUBLIC_RESOLVED_IP_BLOCKED")
        connection = _PinnedHTTPSConnection(parsed.hostname or "", resolved_ip=resolved_ip, timeout=float(timeout_seconds))
        try:
            connection.request(
                "GET",
                _path_and_query(parsed),
                headers={
                    "Host": parsed.hostname or "",
                    "User-Agent": f"JANUS-Genesis-Third-Wish/{HOST_BROKER_VERSION}",
                    "Accept": "*/*",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            body = response.read(int(max_bytes) + 1)
            if len(body) > int(max_bytes):
                raise HostBrokerError("HTTP_RESPONSE_TOO_LARGE")
            headers: dict[str, str] = {}
            for key in self.SAFE_HEADERS:
                value = response.getheader(key)
                if value is not None:
                    headers[key.replace("-", "_")] = str(value)
            return {
                "status_code": int(response.status),
                "reason": str(response.reason),
                "headers": headers,
                "body": body,
            }
        finally:
            connection.close()


_SENSITIVE_COMPONENT_MARKERS = (
    ".env", "id_rsa", "id_ed25519", "credentials", "credential", "secrets", "secret", "private_key"
)
_SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def _validate_relative_workspace_path(path: str) -> Path:
    raw = str(path).strip().replace("\\", "/")
    if not raw:
        raise HostBrokerError("WORKSPACE_PATH_REQUIRED")
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HostBrokerError("WORKSPACE_TRAVERSAL_BLOCKED")
    for part in (item.lower() for item in candidate.parts):
        if any(marker == part or marker in part for marker in _SENSITIVE_COMPONENT_MARKERS):
            raise HostBrokerError("SENSITIVE_WORKSPACE_PATH_BLOCKED")
        if part.endswith(_SENSITIVE_SUFFIXES):
            raise HostBrokerError("SENSITIVE_WORKSPACE_PATH_BLOCKED")
    return candidate


def _existing_within_root(root: Path, relative: Path) -> Path:
    root_real = root.resolve(strict=True)
    candidate = (root_real / relative).resolve(strict=True)
    try:
        candidate.relative_to(root_real)
    except ValueError as exc:
        raise HostBrokerError("WORKSPACE_SYMLINK_ESCAPE_BLOCKED") from exc
    return candidate


def _write_target_within_root(root: Path, relative: Path) -> Path:
    root_real = root.resolve(strict=True)
    raw = root_real / relative
    parent = raw.parent.resolve(strict=True)
    try:
        parent.relative_to(root_real)
    except ValueError as exc:
        raise HostBrokerError("WORKSPACE_PARENT_ESCAPE_BLOCKED") from exc
    target = parent / raw.name
    if target.exists() and target.is_symlink():
        raise HostBrokerError("WORKSPACE_SYMLINK_WRITE_BLOCKED")
    return target


class DockerPythonCapsuleRunner:
    """Python-only Docker capsule with no host mounts and no image pull."""

    def __init__(
        self,
        *,
        image: str = DEFAULT_DOCKER_IMAGE,
        docker_binary: str = "docker",
        max_output_bytes: int = DEFAULT_MAX_PROCESS_OUTPUT_BYTES,
    ) -> None:
        self.image = str(image)
        self.docker_binary = str(docker_binary)
        self.max_output_bytes = int(max_output_bytes)

    def _docker(self) -> str:
        resolved = shutil.which(self.docker_binary)
        if not resolved:
            raise HostBrokerError("DOCKER_BINARY_NOT_AVAILABLE")
        return resolved

    def _image_id(self, docker: str) -> str:
        probe = subprocess.run(
            [docker, "image", "inspect", self.image, "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode != 0:
            raise HostBrokerError("SANDBOX_IMAGE_NOT_PRELOADED")
        image_id = probe.stdout.strip()
        if not image_id.startswith("sha256:"):
            raise HostBrokerError("SANDBOX_IMAGE_ID_UNAVAILABLE")
        return image_id

    def run_python(
        self,
        *,
        code: str,
        argv: Sequence[str],
        timeout_seconds: float,
        memory_mb: int,
        cpus: float,
        pids_limit: int,
    ) -> Mapping[str, Any]:
        docker = self._docker()
        image_id = self._image_id(docker)
        command = [
            docker, "run", "--rm", "--pull=never", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            f"--pids-limit={int(pids_limit)}", f"--memory={int(memory_mb)}m", f"--cpus={float(cpus):g}",
            "--user=65534:65534", "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m", "--workdir=/tmp",
            "--env=PYTHONDONTWRITEBYTECODE=1", self.image, "python", "-I", "-S", "-c", str(code),
            *[str(item) for item in argv],
        ]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=float(timeout_seconds), check=False)
        except subprocess.TimeoutExpired as exc:
            raise HostBrokerError("SANDBOX_TIMEOUT") from exc
        stdout = completed.stdout[: self.max_output_bytes]
        stderr = completed.stderr[: self.max_output_bytes]
        return {
            "returncode": int(completed.returncode),
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stdout_sha256": _sha256_bytes(completed.stdout),
            "stderr_sha256": _sha256_bytes(completed.stderr),
            "output_truncated": len(completed.stdout) > self.max_output_bytes or len(completed.stderr) > self.max_output_bytes,
            "sandbox": {
                "engine": "docker",
                "image": self.image,
                "image_id": image_id,
                "network": "none",
                "root_filesystem": "read_only",
                "host_mounts": 0,
                "host_workspace_visible": False,
                "capabilities": "all_dropped",
                "no_new_privileges": True,
                "host_root_authority": False,
                "image_pull_by_actor": False,
            },
        }


@dataclass
class ThirdWishHostBroker:
    workspace_root: Path
    resolver: Resolver
    https_client: HTTPSOneHopClient
    process_runner: ProcessRunner
    workspace_alias: str = "primary"
    max_http_bytes: int = DEFAULT_MAX_HTTP_BYTES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_redirects: int = 3

    REGISTERED_CAPABILITIES = (
        "WEB.HTTP.GET",
        "DNS.RESOLVE",
        "FILESYSTEM.READ",
        "FILESYSTEM.WRITE_WORKSPACE",
        "PROCESS.EXECUTE_SANDBOXED",
    )
    INTENTIONALLY_UNREGISTERED_NEIGHBORS = (
        "WEB.HTTP.POST", "NETWORK.CONNECT", "NETWORK.LISTEN_LOCAL", "API.CALL"
    )

    @classmethod
    def system(
        cls,
        workspace_root: str | Path,
        *,
        workspace_alias: str = "primary",
        docker_image: str = DEFAULT_DOCKER_IMAGE,
    ) -> "ThirdWishHostBroker":
        root = Path(workspace_root).resolve(strict=True)
        return cls(
            workspace_root=root,
            resolver=SystemResolver(),
            https_client=PinnedHTTPSClient(),
            process_runner=DockerPythonCapsuleRunner(image=docker_image),
            workspace_alias=str(workspace_alias),
        )

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        handlers = {
            "WEB.HTTP.GET": self.web_get,
            "DNS.RESOLVE": self.dns_resolve,
            "FILESYSTEM.READ": self.filesystem_read,
            "FILESYSTEM.WRITE_WORKSPACE": self.filesystem_write,
            "PROCESS.EXECUTE_SANDBOXED": self.process_execute,
        }
        for capability_id, handler in handlers.items():
            fabric.register_handler(capability_id, handler, preflight=self.preflight)

    def _workspace_target(self, target: str) -> None:
        if str(target) != f"workspace:{self.workspace_alias}":
            raise CapabilityDenied("WORKSPACE_ALIAS_OUTSIDE_BROKER_SCOPE")

    @staticmethod
    def _sandbox_target(target: str) -> None:
        if str(target) != "sandbox:python":
            raise CapabilityDenied("SANDBOX_TARGET_OUTSIDE_BROKER_SCOPE")

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        cap, operation, parameters = intent.capability_id, intent.operation.upper(), intent.parameters
        if cap == "WEB.HTTP.GET":
            if operation != "GET":
                raise HostBrokerError("WEB_GET_OPERATION_REQUIRED")
            _parse_https_url(intent.target)
            _bounded_int(parameters.get("max_bytes", self.max_http_bytes), name="MAX_BYTES", minimum=1, maximum=self.max_http_bytes)
            _bounded_float(parameters.get("timeout_seconds", 15.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=30.0)
        elif cap == "DNS.RESOLVE":
            if operation not in {"RESOLVE", "GETADDRINFO"}:
                raise HostBrokerError("DNS_RESOLVE_OPERATION_REQUIRED")
            if not str(intent.target).startswith("dns:"):
                raise HostBrokerError("DNS_TARGET_PREFIX_REQUIRED")
            _validate_public_hostname(str(intent.target)[4:])
        elif cap == "FILESYSTEM.READ":
            self._workspace_target(intent.target)
            if operation not in {"READ_TEXT", "LIST_DIR", "STAT"}:
                raise HostBrokerError("UNSUPPORTED_FILESYSTEM_READ_OPERATION")
            _validate_relative_workspace_path(str(_require(parameters, "path")))
        elif cap == "FILESYSTEM.WRITE_WORKSPACE":
            self._workspace_target(intent.target)
            if operation not in {"WRITE_TEXT", "MAKE_DIR"}:
                raise HostBrokerError("UNSUPPORTED_FILESYSTEM_WRITE_OPERATION")
            _validate_relative_workspace_path(str(_require(parameters, "path")))
            if operation == "WRITE_TEXT":
                raw = str(_require(parameters, "text")).encode("utf-8")
                if len(raw) > self.max_file_bytes:
                    raise HostBrokerError("WORKSPACE_WRITE_TOO_LARGE")
                expected = parameters.get("expected_sha256")
                if expected is not None:
                    digest = str(expected).lower()
                    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                        raise HostBrokerError("EXPECTED_SHA256_INVALID")
        elif cap == "PROCESS.EXECUTE_SANDBOXED":
            self._sandbox_target(intent.target)
            if operation != "RUN_PYTHON":
                raise HostBrokerError("RUN_PYTHON_OPERATION_REQUIRED")
            code = str(_require(parameters, "code"))
            if not code.strip() or len(code.encode("utf-8")) > 64 * 1024:
                raise HostBrokerError("PYTHON_CODE_INVALID")
            argv = parameters.get("argv", [])
            if not isinstance(argv, list) or len(argv) > 32 or any(len(str(item)) > 512 for item in argv):
                raise HostBrokerError("ARGV_SHAPE_INVALID")
            _bounded_float(parameters.get("timeout_seconds", 10.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=20.0)
            _bounded_int(parameters.get("memory_mb", 128), name="MEMORY_MB", minimum=32, maximum=512)
            _bounded_float(parameters.get("cpus", 0.5), name="CPUS", minimum=0.1, maximum=1.0)
            _bounded_int(parameters.get("pids_limit", 64), name="PIDS_LIMIT", minimum=16, maximum=128)
        else:
            raise HostBrokerError("CAPABILITY_NOT_INSTALLED_BY_HOST_BROKER")
        return {
            "validated": True,
            "capability_id": cap,
            "operation": operation,
            "transport_called": False,
            "process_started": False,
        }

    def _public_addresses(self, host: str) -> list[str]:
        addresses = self.resolver.resolve(host, 443)
        if not addresses:
            raise HostBrokerError("DNS_NO_ADDRESSES")
        return addresses if all(_public_ip(address) for address in addresses) else []

    def dns_resolve(self, intent: ActionIntent) -> Mapping[str, Any]:
        host = _validate_public_hostname(str(intent.target)[4:])
        addresses = self._public_addresses(host)
        if not addresses:
            return {"host": host, "allowed": False, "addresses": [], "reason": "RESOLUTION_INCLUDED_NON_PUBLIC_ADDRESS", "connection_attempted": False}
        return {"host": host, "allowed": True, "addresses": addresses, "address_count": len(addresses)}

    def web_get(self, intent: ActionIntent) -> Mapping[str, Any]:
        url = str(intent.target)
        max_bytes = _bounded_int(intent.parameters.get("max_bytes", self.max_http_bytes), name="MAX_BYTES", minimum=1, maximum=self.max_http_bytes)
        timeout = _bounded_float(intent.parameters.get("timeout_seconds", 15.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=30.0)
        redirects: list[str] = []
        for hop in range(self.max_redirects + 1):
            parsed = _parse_https_url(url)
            addresses = self._public_addresses(parsed.hostname or "")
            if not addresses:
                return {
                    "requested_url": str(intent.target), "final_url": url, "allowed": False,
                    "reason": "RESOLUTION_INCLUDED_NON_PUBLIC_ADDRESS", "http_request_performed": False,
                    "redirect_chain": redirects,
                }
            result = dict(self.https_client.request_once(url=url, resolved_ip=addresses[0], timeout_seconds=timeout, max_bytes=max_bytes))
            status = int(result.get("status_code", 0))
            headers = dict(result.get("headers") or {})
            location = headers.get("location")
            if status in {301, 302, 303, 307, 308} and location:
                if hop >= self.max_redirects:
                    raise HostBrokerError("HTTP_REDIRECT_LIMIT_REACHED")
                url = urllib.parse.urljoin(url, str(location))
                _parse_https_url(url)
                redirects.append(url)
                continue
            body = result.get("body", b"")
            if not isinstance(body, (bytes, bytearray)):
                raise HostBrokerError("HTTPS_CLIENT_BODY_MUST_BE_BYTES")
            raw = bytes(body)
            content_type = str(headers.get("content_type") or "")
            text = None
            if content_type.startswith("text/") or "json" in content_type.lower() or "xml" in content_type.lower() or not content_type:
                text = raw.decode("utf-8", errors="replace")
            return {
                "requested_url": str(intent.target), "final_url": url, "allowed": True,
                "status_code": status, "reason": str(result.get("reason") or ""),
                "content_type": content_type, "content_length": len(raw), "body_sha256": _sha256_bytes(raw),
                "text": text, "redirect_chain": redirects, "http_request_performed": True,
                "resolved_ip_sha256": _sha256_text(addresses[0]), "resolved_ip_exposed": False,
            }
        raise HostBrokerError("UNREACHABLE_REDIRECT_STATE")

    def filesystem_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        self._workspace_target(intent.target)
        relative = _validate_relative_workspace_path(str(_require(intent.parameters, "path")))
        candidate = _existing_within_root(self.workspace_root, relative)
        operation = intent.operation.upper()
        if operation == "STAT":
            stat = candidate.stat()
            return {"path": relative.as_posix(), "type": "directory" if candidate.is_dir() else "file", "size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}
        if operation == "LIST_DIR":
            if not candidate.is_dir():
                raise HostBrokerError("WORKSPACE_PATH_NOT_DIRECTORY")
            children = sorted(candidate.iterdir(), key=lambda row: row.name)
            entries = []
            for child in children[:1000]:
                kind = "symlink" if child.is_symlink() else ("directory" if child.is_dir() else "file")
                size = child.stat().st_size if kind == "file" else None
                entries.append({"name": child.name, "type": kind, "size": size})
            return {"path": relative.as_posix(), "entries": entries, "entry_count": len(entries), "truncated": len(children) > 1000}
        if operation == "READ_TEXT":
            if not candidate.is_file():
                raise HostBrokerError("WORKSPACE_PATH_NOT_FILE")
            raw = candidate.read_bytes()
            if len(raw) > self.max_file_bytes:
                raise HostBrokerError("WORKSPACE_FILE_TOO_LARGE")
            return {"path": relative.as_posix(), "size": len(raw), "sha256": _sha256_bytes(raw), "text": raw.decode("utf-8", errors="replace")}
        raise HostBrokerError("UNSUPPORTED_FILESYSTEM_READ_OPERATION")

    def filesystem_write(self, intent: ActionIntent) -> Mapping[str, Any]:
        self._workspace_target(intent.target)
        relative = _validate_relative_workspace_path(str(_require(intent.parameters, "path")))
        operation = intent.operation.upper()
        if operation == "MAKE_DIR":
            target = _write_target_within_root(self.workspace_root, relative)
            target.mkdir(exist_ok=False)
            return {"path": relative.as_posix(), "created": True, "kind": "directory"}
        if operation != "WRITE_TEXT":
            raise HostBrokerError("UNSUPPORTED_FILESYSTEM_WRITE_OPERATION")
        target = _write_target_within_root(self.workspace_root, relative)
        raw = str(_require(intent.parameters, "text")).encode("utf-8")
        if len(raw) > self.max_file_bytes:
            raise HostBrokerError("WORKSPACE_WRITE_TOO_LARGE")
        previous_sha = None
        if target.exists():
            if not target.is_file():
                raise HostBrokerError("WORKSPACE_WRITE_TARGET_NOT_FILE")
            previous_sha = _sha256_bytes(target.read_bytes())
            expected = intent.parameters.get("expected_sha256")
            if expected is None:
                raise HostBrokerError("EXISTING_FILE_REQUIRES_EXPECTED_SHA256")
            if str(expected).lower() != previous_sha:
                raise HostBrokerError("WORKSPACE_COMPARE_AND_SWAP_MISMATCH")
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".janus-tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
            try:
                directory_fd = os.open(str(target.parent), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return {
            "path": relative.as_posix(), "created": previous_sha is None, "previous_sha256": previous_sha,
            "sha256": _sha256_bytes(raw), "size": len(raw), "atomic_replace": True,
            "compare_and_swap_required_for_existing_file": True,
        }

    def process_execute(self, intent: ActionIntent) -> Mapping[str, Any]:
        self._sandbox_target(intent.target)
        p = intent.parameters
        return self.process_runner.run_python(
            code=str(_require(p, "code")),
            argv=[str(item) for item in p.get("argv", [])],
            timeout_seconds=_bounded_float(p.get("timeout_seconds", 10.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=20.0),
            memory_mb=_bounded_int(p.get("memory_mb", 128), name="MEMORY_MB", minimum=32, maximum=512),
            cpus=_bounded_float(p.get("cpus", 0.5), name="CPUS", minimum=0.1, maximum=1.0),
            pids_limit=_bounded_int(p.get("pids_limit", 64), name="PIDS_LIMIT", minimum=16, maximum=128),
        )


HOST_BROKER_CLAIM_BOUNDARY = {
    "historical_v18_7_40_core_rewritten": False,
    "registered_capability_count": len(ThirdWishHostBroker.REGISTERED_CAPABILITIES),
    "raw_host_shell_exposed": False,
    "arbitrary_tcp_connect_exposed": False,
    "generic_http_post_exposed": False,
    "private_or_loopback_http_destination_allowed": False,
    "workspace_traversal_allowed": False,
    "workspace_symlink_escape_allowed": False,
    "credential_named_workspace_paths_allowed": False,
    "process_host_mounts": 0,
    "process_can_bypass_filesystem_capability": False,
    "sandbox_network_enabled": False,
    "sandbox_root_filesystem_writable": False,
    "sandbox_linux_capabilities_retained": False,
    "sandbox_image_auto_pull_allowed": False,
    "docker_is_claimed_as_perfect_isolation": False,
    "capability_is_command": False,
}
