# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.45 — Third Wish active network broker.

Four already-declared capability classes become typed active network doors:

* WEB.HTTP.POST — bounded public-HTTPS JSON POST, fixed safe headers, no redirect
  following and no actor-supplied Authorization/custom headers.
* NETWORK.CONNECT — outbound TCP reachability probe only. No actor payload is
  sent and the connection is closed after connect.
* NETWORK.LISTEN_LOCAL — one-shot loopback listener with bounded lifetime and at
  most one accepted connection. It is not a persistent daemon or command port.
* API.CALL — operator-registered API alias + named operation. Actor parameters
  are request data only; endpoint/method/path/headers are operator-owned.

External network effects have a durable request boundary. If a process dies
after EFFECT_ENTERING, the same request is not blindly replayed. Generic public
HTTP/TCP has no authoritative universal reconciliation protocol, so an
ambiguous effect remains undetermined instead of manufacturing retry consent.

This module intentionally does not implement GITHUB.REPOSITORY.ADMIN or
GITHUB.DESTRUCTIVE. Those high-impact classes remain a separate final gate.
"""
from __future__ import annotations

import copy
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent, ThirdWishCapabilityFabric
from janus_portable_lock_v2 import PortableProcessLockV2
from tools.genesis_third_wish_host_broker import (
    HostBrokerError,
    SystemResolver,
    _path_and_query,
    _public_ip,
    _validate_public_hostname,
)

ACTIVE_NETWORK_VERSION = "18.7.45"
ACTIVE_NETWORK_STORE_SCHEMA = "janus.genesis.third_wish.active_network_store.v1"
MAX_POST_REQUEST_BYTES = 256 * 1024
MAX_POST_RESPONSE_BYTES = 512 * 1024
MAX_API_REQUEST_BYTES = 256 * 1024
MAX_API_RESPONSE_BYTES = 512 * 1024
MAX_LISTEN_TIMEOUT_SECONDS = 10.0
MAX_CONNECT_TIMEOUT_SECONDS = 15.0


class ActiveNetworkError(RuntimeError):
    pass


class ActiveNetworkRequestConflict(ActiveNetworkError):
    pass


class ActiveNetworkOutcomeUndetermined(ActiveNetworkError):
    pass


class ActiveNetworkReceiptIntegrityError(ActiveNetworkError):
    pass


class JsonPoster(Protocol):
    def post_json(
        self,
        *,
        url: str,
        resolved_ip: str,
        payload: Mapping[str, Any],
        effect_key: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]: ...


class ConnectProbe(Protocol):
    def connect_once(
        self,
        *,
        host: str,
        port: int,
        resolved_ip: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class LocalListener(Protocol):
    def listen_once(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class APICaller(Protocol):
    def call(
        self,
        *,
        operation_name: str,
        payload: Mapping[str, Any],
        effect_key: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]: ...


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_size(value: Any) -> int:
    return len(_canonical(value).encode("utf-8"))


def _bounded_int(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ActiveNetworkError(f"{name}_MUST_BE_INTEGER") from exc
    if not minimum <= result <= maximum:
        raise ActiveNetworkError(f"{name}_OUT_OF_RANGE")
    return result


def _bounded_float(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ActiveNetworkError(f"{name}_MUST_BE_NUMBER") from exc
    if not minimum <= result <= maximum:
        raise ActiveNetworkError(f"{name}_OUT_OF_RANGE")
    return result


def _parse_public_https_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(str(url).strip())
    if parsed.scheme.lower() != "https":
        raise ActiveNetworkError("HTTPS_ONLY")
    if not parsed.hostname:
        raise ActiveNetworkError("URL_HOST_REQUIRED")
    if parsed.username is not None or parsed.password is not None:
        raise ActiveNetworkError("URL_USERINFO_BLOCKED")
    if parsed.fragment:
        raise ActiveNetworkError("URL_FRAGMENT_BLOCKED")
    if (parsed.port or 443) != 443:
        raise ActiveNetworkError("NON_STANDARD_HTTPS_PORT_BLOCKED")
    try:
        _validate_public_hostname(parsed.hostname)
    except HostBrokerError as exc:
        raise ActiveNetworkError(str(exc)) from exc
    return parsed


def _parse_tcp_target(target: str) -> tuple[str, int]:
    text = str(target).strip()
    if not text.startswith("tcp:"):
        raise ActiveNetworkError("TCP_TARGET_PREFIX_REQUIRED")
    value = text[len("tcp:"):]
    if value.startswith("["):
        end = value.find("]")
        if end < 0 or end + 1 >= len(value) or value[end + 1] != ":":
            raise ActiveNetworkError("TCP_TARGET_INVALID")
        host = value[1:end]
        port_text = value[end + 2:]
    else:
        if value.count(":") != 1:
            raise ActiveNetworkError("TCP_TARGET_INVALID")
        host, port_text = value.rsplit(":", 1)
    try:
        host = _validate_public_hostname(host)
    except HostBrokerError as exc:
        raise ActiveNetworkError(str(exc)) from exc
    port = _bounded_int(port_text, name="TCP_PORT", minimum=1, maximum=65535)
    return host, port


def _parse_local_listen_target(target: str) -> tuple[str, int]:
    text = str(target).strip()
    prefix = "listen-local:"
    if not text.startswith(prefix):
        raise ActiveNetworkError("LOCAL_LISTEN_TARGET_PREFIX_REQUIRED")
    value = text[len(prefix):]
    if value.count(":") != 1:
        raise ActiveNetworkError("LOCAL_LISTEN_TARGET_INVALID")
    host, port_text = value.rsplit(":", 1)
    if host != "127.0.0.1":
        raise ActiveNetworkError("LOCAL_LISTENER_MUST_BIND_LOOPBACK_ONLY")
    port = _bounded_int(port_text, name="LISTEN_PORT", minimum=1024, maximum=65535)
    return host, port


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, resolved_ip: str, timeout: float) -> None:
        super().__init__(host=host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.resolved_ip = str(resolved_ip)

    def connect(self) -> None:  # pragma: no cover - live public provider path
        raw = socket.create_connection((self.resolved_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class PinnedHTTPSJsonPoster:
    SAFE_RESPONSE_HEADERS = ("content-type", "content-length", "etag", "last-modified", "location")

    def post_json(
        self,
        *,
        url: str,
        resolved_ip: str,
        payload: Mapping[str, Any],
        effect_key: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        parsed = _parse_public_https_url(url)
        if not _public_ip(resolved_ip):
            raise ActiveNetworkError("NON_PUBLIC_RESOLVED_IP_BLOCKED")
        body = _canonical(dict(payload)).encode("utf-8")
        if len(body) > MAX_POST_REQUEST_BYTES:
            raise ActiveNetworkError("POST_REQUEST_TOO_LARGE")
        connection = _PinnedHTTPSConnection(
            parsed.hostname or "",
            resolved_ip=resolved_ip,
            timeout=float(timeout_seconds),
        )
        try:
            connection.request(
                "POST",
                _path_and_query(parsed),
                body=body,
                headers={
                    "Host": parsed.hostname or "",
                    "User-Agent": f"JANUS-Genesis-Third-Wish/{ACTIVE_NETWORK_VERSION}",
                    "Accept": "application/json, */*;q=0.1",
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Idempotency-Key": effect_key,
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            raw = response.read(int(max_response_bytes) + 1)
            if len(raw) > int(max_response_bytes):
                raise ActiveNetworkReceiptIntegrityError("POST_RESPONSE_TOO_LARGE")
            headers: dict[str, str] = {}
            for key in self.SAFE_RESPONSE_HEADERS:
                value = response.getheader(key)
                if value is not None:
                    headers[key.replace("-", "_")] = str(value)
            return {
                "status_code": int(response.status),
                "reason": str(response.reason),
                "headers": headers,
                "body_text": raw.decode("utf-8", errors="replace"),
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "body_bytes": len(raw),
                "redirect_followed": False,
                "request_authorization_header_present": False,
            }
        finally:
            connection.close()


class SystemTCPConnectProbe:
    def connect_once(
        self,
        *,
        host: str,
        port: int,
        resolved_ip: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        del host
        if not _public_ip(resolved_ip):
            raise ActiveNetworkError("NON_PUBLIC_RESOLVED_IP_BLOCKED")
        sock = socket.socket(
            socket.AF_INET6 if ipaddress.ip_address(resolved_ip).version == 6 else socket.AF_INET,
            socket.SOCK_STREAM,
        )
        sock.settimeout(float(timeout_seconds))
        try:
            address: Any = (resolved_ip, int(port), 0, 0) if ":" in resolved_ip else (resolved_ip, int(port))
            sock.connect(address)
            local = sock.getsockname()
            return {
                "connected": True,
                "resolved_ip_sha256": hashlib.sha256(resolved_ip.encode("utf-8")).hexdigest(),
                "remote_port": int(port),
                "local_port": int(local[1]),
                "application_payload_sent": False,
                "remote_command_channel": False,
            }
        finally:
            sock.close()


class OneShotLoopbackListener:
    def listen_once(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        if host != "127.0.0.1":
            raise ActiveNetworkError("LOCAL_LISTENER_MUST_BIND_LOOPBACK_ONLY")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(float(timeout_seconds))
        accepted = False
        peer_is_loopback = False
        try:
            server.bind((host, int(port)))
            server.listen(1)
            try:
                client, peer = server.accept()
            except socket.timeout:
                return {
                    "listener_opened": True,
                    "accepted_connection": False,
                    "bound_host": host,
                    "bound_port": int(port),
                    "max_connections": 1,
                    "persistent_daemon": False,
                    "remote_command_channel": False,
                    "application_payload_received": False,
                }
            try:
                accepted = True
                peer_is_loopback = ipaddress.ip_address(str(peer[0])).is_loopback
                return {
                    "listener_opened": True,
                    "accepted_connection": True,
                    "peer_is_loopback": bool(peer_is_loopback),
                    "bound_host": host,
                    "bound_port": int(port),
                    "max_connections": 1,
                    "persistent_daemon": False,
                    "remote_command_channel": False,
                    "application_payload_received": False,
                }
            finally:
                client.close()
        finally:
            server.close()
            if accepted and not peer_is_loopback:
                raise ActiveNetworkError("NON_LOOPBACK_PEER_REACHED_LOOPBACK_LISTENER")


@dataclass(frozen=True)
class APIOperation:
    name: str
    method: str
    path: str
    allowed_fields: frozenset[str]

    @classmethod
    def build(
        cls,
        *,
        name: str,
        method: str,
        path: str,
        allowed_fields: Sequence[str],
    ) -> "APIOperation":
        operation_name = str(name).strip().upper()
        if not operation_name or not operation_name.replace("_", "").isalnum():
            raise ValueError("API_OPERATION_NAME_INVALID")
        method_value = str(method).upper()
        if method_value not in {"GET", "POST"}:
            raise ValueError("API_OPERATION_METHOD_NOT_ALLOWED")
        path_value = str(path)
        if not path_value.startswith("/") or "?" in path_value or "#" in path_value:
            raise ValueError("API_OPERATION_PATH_INVALID")
        fields = frozenset(str(x) for x in allowed_fields)
        if method_value == "GET" and fields:
            raise ValueError("REFERENCE_API_GET_ACCEPTS_NO_ACTOR_QUERY_FIELDS")
        return cls(operation_name, method_value, path_value, fields)


class FixedHTTPAPIAdapter:
    """Operator-fixed API surface. Production is HTTPS; loopback HTTP is test-only."""

    def __init__(
        self,
        *,
        alias: str,
        base_url: str,
        operations: Sequence[APIOperation],
        allow_loopback_http: bool = False,
    ) -> None:
        if not alias or not alias.replace("-", "").replace("_", "").isalnum():
            raise ValueError("API_ALIAS_INVALID")
        parsed = urllib.parse.urlsplit(str(base_url).rstrip("/"))
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("API_BASE_URL_INVALID")
        if parsed.scheme == "https":
            try:
                _validate_public_hostname(parsed.hostname)
            except HostBrokerError as exc:
                raise ValueError(str(exc)) from exc
            if (parsed.port or 443) != 443:
                raise ValueError("API_NONSTANDARD_HTTPS_PORT_BLOCKED")
        elif parsed.scheme == "http":
            try:
                loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                loopback = parsed.hostname.lower() == "localhost"
            if not (allow_loopback_http and loopback):
                raise ValueError("API_HTTP_ONLY_ALLOWED_FOR_EXPLICIT_LOOPBACK_TEST")
        else:
            raise ValueError("API_SCHEME_INVALID")
        self.alias = str(alias)
        self.base_url = str(base_url).rstrip("/")
        self.parsed = parsed
        self.operations = {row.name: row for row in operations}
        if not self.operations or len(self.operations) != len(list(operations)):
            raise ValueError("API_OPERATION_SET_INVALID")
        self.allow_loopback_http = bool(allow_loopback_http)

    def preflight(self, operation_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        name = str(operation_name).upper()
        operation = self.operations.get(name)
        if operation is None:
            raise ActiveNetworkError("API_OPERATION_NOT_REGISTERED")
        supplied = set(str(k) for k in payload)
        if supplied.difference(operation.allowed_fields):
            raise ActiveNetworkError("API_REQUEST_FIELDS_NOT_ALLOWED")
        if _json_size(payload) > MAX_API_REQUEST_BYTES:
            raise ActiveNetworkError("API_REQUEST_TOO_LARGE")
        return {
            "validated": True,
            "api_alias": self.alias,
            "operation_name": name,
            "method": operation.method,
            "path_sha256": hashlib.sha256(operation.path.encode("utf-8")).hexdigest(),
            "actor_selects_endpoint": False,
            "actor_selects_method": False,
            "actor_selects_path": False,
            "credentialed_api": False,
        }

    def call(
        self,
        *,
        operation_name: str,
        payload: Mapping[str, Any],
        effect_key: str,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        operation = self.operations[str(operation_name).upper()]
        parsed = self.parsed
        path = (parsed.path.rstrip("/") if parsed.path else "") + operation.path
        body: bytes | None = None
        headers = {
            "Accept": "application/json",
            "User-Agent": f"JANUS-Genesis-Third-Wish/{ACTIVE_NETWORK_VERSION}",
            "Connection": "close",
            "Idempotency-Key": effect_key,
        }
        if operation.method == "POST":
            body = _canonical(dict(payload)).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        if parsed.scheme == "http":
            connection: http.client.HTTPConnection = http.client.HTTPConnection(
                parsed.hostname or "127.0.0.1",
                parsed.port or 80,
                timeout=float(timeout_seconds),
            )
        else:
            addresses = SystemResolver().resolve(parsed.hostname or "", 443)
            if not addresses or any(not _public_ip(ip) for ip in addresses):
                raise ActiveNetworkError("API_RESOLUTION_NOT_ALL_PUBLIC")
            connection = _PinnedHTTPSConnection(
                parsed.hostname or "",
                resolved_ip=addresses[0],
                timeout=float(timeout_seconds),
            )
        try:
            connection.request(operation.method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(int(max_response_bytes) + 1)
            if len(raw) > int(max_response_bytes):
                raise ActiveNetworkReceiptIntegrityError("API_RESPONSE_TOO_LARGE")
            return {
                "status_code": int(response.status),
                "reason": str(response.reason),
                "body_text": raw.decode("utf-8", errors="replace"),
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "body_bytes": len(raw),
                "api_alias": self.alias,
                "operation_name": operation.name,
                "credentialed_api": False,
                "authorization_header_present": False,
            }
        finally:
            connection.close()


class DurableActiveNetworkStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_active_network_v18_7_45.json"
        self.lock = PortableProcessLockV2(self.root / "third_wish_active_network_v18_7_45.lock")
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save({
                    "schema": ACTIVE_NETWORK_STORE_SCHEMA,
                    "requests": {},
                    "invariants": {
                        "raw_parameters_persisted": False,
                        "effect_entering_auto_retry": False,
                        "generic_public_network_lookup_claimed": False,
                        "changed_request_binding_allowed": False,
                    },
                })
            else:
                self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ActiveNetworkReceiptIntegrityError("ACTIVE_NETWORK_STORE_UNREADABLE") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != ACTIVE_NETWORK_STORE_SCHEMA
            or not isinstance(value.get("requests"), dict)
        ):
            raise ActiveNetworkReceiptIntegrityError("ACTIVE_NETWORK_STORE_SCHEMA_INVALID")
        return value

    def _save(self, value: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(value))

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self.lock.exclusive():
            row = self._load()["requests"].get(str(request_id))
        return copy.deepcopy(row) if isinstance(row, dict) else None

    def bind(
        self,
        *,
        request_id: str,
        binding_sha256: str,
        effect_key: str,
        capability_id: str,
    ) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            existing = state["requests"].get(str(request_id))
            if existing is not None:
                if (
                    not isinstance(existing, dict)
                    or existing.get("binding_sha256") != binding_sha256
                    or existing.get("effect_key") != effect_key
                    or existing.get("capability_id") != capability_id
                ):
                    raise ActiveNetworkRequestConflict(str(request_id))
                return copy.deepcopy(existing)
            row = {
                "binding_sha256": binding_sha256,
                "effect_key": effect_key,
                "capability_id": capability_id,
                "state": "BOUND",
                "actor_result": None,
            }
            state["requests"][str(request_id)] = row
            self._save(state)
            return copy.deepcopy(row)

    def update(self, request_id: str, **fields: Any) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            row = state["requests"].get(str(request_id))
            if not isinstance(row, dict):
                raise ActiveNetworkReceiptIntegrityError("ACTIVE_NETWORK_REQUEST_NOT_BOUND")
            row.update(copy.deepcopy(fields))
            state["requests"][str(request_id)] = row
            self._save(state)
            return copy.deepcopy(row)


class ThirdWishActiveNetworkBroker:
    REGISTERED_CAPABILITIES = frozenset({
        "WEB.HTTP.POST",
        "NETWORK.CONNECT",
        "NETWORK.LISTEN_LOCAL",
        "API.CALL",
    })

    def __init__(
        self,
        *,
        data_dir: str | Path,
        resolver: Any | None = None,
        poster: JsonPoster | None = None,
        connect_probe: ConnectProbe | None = None,
        local_listener: LocalListener | None = None,
        api_adapters: Mapping[str, FixedHTTPAPIAdapter] | None = None,
        allowed_connect_ports: Sequence[int] = (80, 443),
        effect_store: DurableActiveNetworkStore | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.resolver = resolver or SystemResolver()
        self.poster = poster or PinnedHTTPSJsonPoster()
        self.connect_probe = connect_probe or SystemTCPConnectProbe()
        self.local_listener = local_listener or OneShotLoopbackListener()
        self.api_adapters = {str(k): v for k, v in (api_adapters or {}).items()}
        self.allowed_connect_ports = frozenset(int(x) for x in allowed_connect_ports)
        if not self.allowed_connect_ports or any(not 1 <= x <= 65535 for x in self.allowed_connect_ports):
            raise ValueError("ALLOWED_CONNECT_PORTS_INVALID")
        for alias, adapter in self.api_adapters.items():
            if alias != adapter.alias:
                raise ValueError("API_ALIAS_KEY_MISMATCH")
        self.effect_store = effect_store or DurableActiveNetworkStore(self.data_dir)

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        handlers = {
            "WEB.HTTP.POST": self.web_post,
            "NETWORK.CONNECT": self.network_connect,
            "NETWORK.LISTEN_LOCAL": self.network_listen_local,
            "API.CALL": self.api_call,
        }
        for capability_id, handler in handlers.items():
            fabric.register_handler(capability_id, handler, preflight=self.preflight)

    @staticmethod
    def _api_alias(target: str) -> str:
        text = str(target).strip()
        prefix = "api:"
        if not text.startswith(prefix):
            raise ActiveNetworkError("API_TARGET_PREFIX_REQUIRED")
        alias = text[len(prefix):]
        if not alias or not alias.replace("-", "").replace("_", "").isalnum():
            raise ActiveNetworkError("API_ALIAS_INVALID")
        return alias

    def _binding(self, intent: ActionIntent) -> tuple[str, str]:
        payload = {
            "actor_id": intent.actor_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "operation": str(intent.operation).upper(),
            "parameters": copy.deepcopy(dict(intent.parameters)),
        }
        binding_sha256 = _sha256(payload)
        effect_key = "THIRD-WISH-NETWORK:" + _sha256({"request_id": intent.request_id, **payload})
        return binding_sha256, effect_key

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        cap = intent.capability_id
        operation = str(intent.operation).upper()
        p = dict(intent.parameters)
        if cap == "WEB.HTTP.POST":
            if operation != "POST_JSON":
                raise ActiveNetworkError("WEB_POST_JSON_OPERATION_REQUIRED")
            _parse_public_https_url(intent.target)
            if set(p).difference({"json", "timeout_seconds", "max_response_bytes"}):
                raise ActiveNetworkError("WEB_POST_PARAMETERS_NOT_ALLOWED")
            payload = p.get("json")
            if not isinstance(payload, Mapping):
                raise ActiveNetworkError("WEB_POST_JSON_OBJECT_REQUIRED")
            if _json_size(payload) > MAX_POST_REQUEST_BYTES:
                raise ActiveNetworkError("WEB_POST_REQUEST_TOO_LARGE")
            _bounded_float(p.get("timeout_seconds", 15.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=30.0)
            _bounded_int(
                p.get("max_response_bytes", MAX_POST_RESPONSE_BYTES),
                name="MAX_RESPONSE_BYTES",
                minimum=1,
                maximum=MAX_POST_RESPONSE_BYTES,
            )
        elif cap == "NETWORK.CONNECT":
            if operation != "CONNECT_PROBE":
                raise ActiveNetworkError("CONNECT_PROBE_OPERATION_REQUIRED")
            host, port = _parse_tcp_target(intent.target)
            del host
            if port not in self.allowed_connect_ports:
                raise ActiveNetworkError("CONNECT_PORT_NOT_OPERATOR_ALLOWED")
            if set(p).difference({"timeout_seconds"}):
                raise ActiveNetworkError("CONNECT_PARAMETERS_NOT_ALLOWED")
            _bounded_float(
                p.get("timeout_seconds", 5.0),
                name="TIMEOUT_SECONDS",
                minimum=0.2,
                maximum=MAX_CONNECT_TIMEOUT_SECONDS,
            )
        elif cap == "NETWORK.LISTEN_LOCAL":
            if operation != "LISTEN_ONCE":
                raise ActiveNetworkError("LISTEN_ONCE_OPERATION_REQUIRED")
            _parse_local_listen_target(intent.target)
            if set(p).difference({"timeout_seconds"}):
                raise ActiveNetworkError("LOCAL_LISTEN_PARAMETERS_NOT_ALLOWED")
            _bounded_float(
                p.get("timeout_seconds", 2.0),
                name="TIMEOUT_SECONDS",
                minimum=0.2,
                maximum=MAX_LISTEN_TIMEOUT_SECONDS,
            )
        elif cap == "API.CALL":
            alias = self._api_alias(intent.target)
            adapter = self.api_adapters.get(alias)
            if adapter is None:
                raise ActiveNetworkError("API_ALIAS_NOT_REGISTERED")
            if set(p).difference({"json", "timeout_seconds", "max_response_bytes"}):
                raise ActiveNetworkError("API_CALL_PARAMETERS_NOT_ALLOWED")
            payload = p.get("json", {})
            if not isinstance(payload, Mapping):
                raise ActiveNetworkError("API_JSON_OBJECT_REQUIRED")
            adapter.preflight(operation, payload)
            _bounded_float(p.get("timeout_seconds", 10.0), name="TIMEOUT_SECONDS", minimum=0.2, maximum=30.0)
            _bounded_int(
                p.get("max_response_bytes", MAX_API_RESPONSE_BYTES),
                name="MAX_RESPONSE_BYTES",
                minimum=1,
                maximum=MAX_API_RESPONSE_BYTES,
            )
        else:
            raise ActiveNetworkError("ACTIVE_NETWORK_CAPABILITY_NOT_INSTALLED")

        binding_sha256, effect_key = self._binding(intent)
        existing = self.effect_store.get(intent.request_id)
        if existing is not None:
            if (
                existing.get("binding_sha256") != binding_sha256
                or existing.get("effect_key") != effect_key
                or existing.get("capability_id") != cap
            ):
                raise ActiveNetworkRequestConflict(intent.request_id)
        return {
            "validated": True,
            "capability_id": cap,
            "operation": operation,
            "durable_request_state": "UNBOUND" if existing is None else existing.get("state"),
            "automatic_retry_after_effect_entering": False,
            "actor_supplied_authorization_header": False,
            "generic_stream_or_tunnel": False,
        }

    def _execute_once(self, intent: ActionIntent, effect: Callable[[str], Mapping[str, Any]]) -> Mapping[str, Any]:
        binding_sha256, effect_key = self._binding(intent)
        stored = self.effect_store.bind(
            request_id=intent.request_id,
            binding_sha256=binding_sha256,
            effect_key=effect_key,
            capability_id=intent.capability_id,
        )
        state = str(stored.get("state") or "")
        if state == "SETTLED":
            actor_result = stored.get("actor_result")
            if not isinstance(actor_result, Mapping):
                raise ActiveNetworkReceiptIntegrityError("SETTLED_NETWORK_REQUEST_HAS_NO_RESULT")
            return copy.deepcopy(dict(actor_result))
        if state == "EFFECT_ENTERING":
            raise ActiveNetworkOutcomeUndetermined(
                "ACTIVE_NETWORK_EFFECT_ENTERING_HAS_NO_UNIVERSAL_AUTHORITATIVE_LOOKUP"
            )
        self.effect_store.update(intent.request_id, state="EFFECT_ENTERING")
        actor_result = copy.deepcopy(dict(effect(effect_key)))
        self.effect_store.update(intent.request_id, state="SETTLED", actor_result=actor_result)
        return actor_result

    def _resolve_all_public(self, host: str, port: int) -> list[str]:
        try:
            addresses = list(self.resolver.resolve(host, int(port)))
        except HostBrokerError as exc:
            raise ActiveNetworkError(str(exc)) from exc
        if not addresses:
            raise ActiveNetworkError("DNS_NO_ADDRESSES")
        if any(not _public_ip(address) for address in addresses):
            raise ActiveNetworkError("DNS_MIXED_OR_NONPUBLIC_RESULT_BLOCKED")
        return addresses

    def web_post(self, intent: ActionIntent) -> Mapping[str, Any]:
        parsed = _parse_public_https_url(intent.target)
        p = dict(intent.parameters)
        payload = copy.deepcopy(dict(p["json"]))
        timeout = _bounded_float(p.get("timeout_seconds", 15.0), name="TIMEOUT_SECONDS", minimum=0.5, maximum=30.0)
        max_bytes = _bounded_int(
            p.get("max_response_bytes", MAX_POST_RESPONSE_BYTES),
            name="MAX_RESPONSE_BYTES",
            minimum=1,
            maximum=MAX_POST_RESPONSE_BYTES,
        )

        def effect(effect_key: str) -> Mapping[str, Any]:
            addresses = self._resolve_all_public(parsed.hostname or "", 443)
            result = dict(self.poster.post_json(
                url=intent.target,
                resolved_ip=addresses[0],
                payload=payload,
                effect_key=effect_key,
                timeout_seconds=timeout,
                max_response_bytes=max_bytes,
            ))
            result.update({
                "request_json_sha256": _sha256(payload),
                "resolved_address_count": len(addresses),
                "raw_resolved_ips_returned": False,
                "redirect_followed": False,
                "actor_supplied_headers": False,
                "credential_material_used": False,
                "automatic_retry_after_ambiguous_effect": False,
            })
            return result

        return self._execute_once(intent, effect)

    def network_connect(self, intent: ActionIntent) -> Mapping[str, Any]:
        host, port = _parse_tcp_target(intent.target)
        p = dict(intent.parameters)
        timeout = _bounded_float(
            p.get("timeout_seconds", 5.0),
            name="TIMEOUT_SECONDS",
            minimum=0.2,
            maximum=MAX_CONNECT_TIMEOUT_SECONDS,
        )

        def effect(_effect_key: str) -> Mapping[str, Any]:
            addresses = self._resolve_all_public(host, port)
            result = dict(self.connect_probe.connect_once(
                host=host,
                port=port,
                resolved_ip=addresses[0],
                timeout_seconds=timeout,
            ))
            result.update({
                "resolved_address_count": len(addresses),
                "raw_resolved_ips_returned": False,
                "application_payload_sent": False,
                "generic_tcp_tunnel": False,
                "automatic_retry_after_ambiguous_effect": False,
            })
            return result

        return self._execute_once(intent, effect)

    def network_listen_local(self, intent: ActionIntent) -> Mapping[str, Any]:
        host, port = _parse_local_listen_target(intent.target)
        p = dict(intent.parameters)
        timeout = _bounded_float(
            p.get("timeout_seconds", 2.0),
            name="TIMEOUT_SECONDS",
            minimum=0.2,
            maximum=MAX_LISTEN_TIMEOUT_SECONDS,
        )

        def effect(_effect_key: str) -> Mapping[str, Any]:
            result = dict(self.local_listener.listen_once(
                host=host,
                port=port,
                timeout_seconds=timeout,
            ))
            result.update({
                "bind_scope": "LOOPBACK_ONLY",
                "persistent_listener": False,
                "max_connections": 1,
                "application_payload_received": False,
                "remote_command_channel": False,
            })
            return result

        return self._execute_once(intent, effect)

    def api_call(self, intent: ActionIntent) -> Mapping[str, Any]:
        alias = self._api_alias(intent.target)
        adapter = self.api_adapters[alias]
        p = dict(intent.parameters)
        payload = copy.deepcopy(dict(p.get("json", {})))
        timeout = _bounded_float(p.get("timeout_seconds", 10.0), name="TIMEOUT_SECONDS", minimum=0.2, maximum=30.0)
        max_bytes = _bounded_int(
            p.get("max_response_bytes", MAX_API_RESPONSE_BYTES),
            name="MAX_RESPONSE_BYTES",
            minimum=1,
            maximum=MAX_API_RESPONSE_BYTES,
        )

        def effect(effect_key: str) -> Mapping[str, Any]:
            result = dict(adapter.call(
                operation_name=str(intent.operation).upper(),
                payload=payload,
                effect_key=effect_key,
                timeout_seconds=timeout,
                max_response_bytes=max_bytes,
            ))
            result.update({
                "request_json_sha256": _sha256(payload),
                "actor_selects_api_endpoint": False,
                "actor_selects_api_method": False,
                "actor_selects_api_path": False,
                "credentialed_api": False,
                "generic_api_tunnel": False,
                "automatic_retry_after_ambiguous_effect": False,
            })
            return result

        return self._execute_once(intent, effect)


ACTIVE_NETWORK_CLAIM_BOUNDARY = {
    "version": ACTIVE_NETWORK_VERSION,
    "registered_capability_count": len(ThirdWishActiveNetworkBroker.REGISTERED_CAPABILITIES),
    "web_post_https_only": True,
    "web_post_actor_headers_allowed": False,
    "web_post_redirect_following": False,
    "network_connect_actor_payload_allowed": False,
    "network_connect_generic_tunnel": False,
    "network_listen_loopback_only": True,
    "network_listen_persistent_daemon": False,
    "network_listen_remote_command_channel": False,
    "api_call_actor_selects_endpoint": False,
    "api_call_actor_selects_method": False,
    "api_call_actor_selects_path": False,
    "api_call_generic_tunnel": False,
    "reference_api_call_uses_credentials": False,
    "effect_entering_auto_retry": False,
    "generic_public_network_authoritative_lookup_claimed": False,
    "github_admin_installed_here": False,
    "github_destructive_installed_here": False,
    "capability_is_command": False,
}
