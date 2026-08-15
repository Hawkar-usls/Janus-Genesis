# -*- coding: utf-8 -*-
"""GitHub broker adapter for JANUS Genesis v18.7.40 Third Wish.

The adapter keeps the GitHub credential in an environment/service boundary and
registers owner-scoped read + reversible collaboration handlers. It never
returns the token to JANUS. Repository-admin and destructive handlers are
intentionally not installed by this reference adapter: those capabilities stay
visible/requestable in the core catalog but require a separately reviewed,
freshly reauthorized high-impact adapter.

Every registered handler also installs a deterministic local preflight. Invalid
owner/scope, operation, branch, path, or required-parameter shapes are rejected
before the core records CALL_ENTERING, so deterministic local policy rejection
is not confused with an ambiguous remote outcome.
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    ThirdWishCapabilityFabric,
)

GITHUB_BROKER_VERSION = "18.7.40"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_OWNER = "Hawkar-usls"
DEFAULT_TOKEN_ENV = "JANUS_GITHUB_BROKER_TOKEN"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_FILE_TEXT_BYTES = 2 * 1024 * 1024


class GitHubBrokerError(RuntimeError):
    pass


class GitHubTransport(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any: ...


class GitHubRESTTransport:
    """Minimal GitHub REST transport with broker-side credential custody."""

    def __init__(
        self,
        *,
        token_env: str = DEFAULT_TOKEN_ENV,
        api_base: str = "https://api.github.com",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.token_env = str(token_env)
        self.api_base = str(api_base).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    def _token(self) -> str:
        token = os.environ.get(self.token_env, "").strip()
        if not token:
            raise GitHubBrokerError(f"BROKER_CREDENTIAL_ENV_MISSING:{self.token_env}")
        return token

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        path = "/" + str(path).lstrip("/")
        url = self.api_base + path
        if query:
            pairs = [(str(key), str(value)) for key, value in query.items() if value is not None]
            url += "?" + urllib.parse.urlencode(pairs)
        data = None
        if payload is not None:
            data = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=str(method).upper(),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self._token(),
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "JANUS-Genesis-Third-Wish/18.7.40",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise GitHubBrokerError("GITHUB_RESPONSE_TOO_LARGE")
                if not raw:
                    return {"status_code": int(response.status)}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise GitHubBrokerError(f"GITHUB_HTTP_{exc.code}:{detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubBrokerError(f"GITHUB_CONNECTION_ERROR:{exc.reason}") from exc


_SENSITIVE_PATH_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "id_ed25519*",
    ".ssh/*",
    "*credentials*",
    "*credential*",
    "*secrets*",
)
_BRANCH_INVALID = re.compile(r"[\x00-\x20~^:?*\\\[]")


def _validate_branch(branch: str) -> str:
    value = str(branch).strip()
    if (
        not value
        or value.startswith("/")
        or value.endswith("/")
        or value.endswith(".")
        or ".." in value
        or "@{" in value
        or "//" in value
        or _BRANCH_INVALID.search(value)
    ):
        raise GitHubBrokerError("INVALID_GITHUB_BRANCH_NAME")
    return value


def _validate_repo_path(path: str) -> str:
    value = str(path).strip().replace("\\", "/")
    if not value or value.startswith("/") or ".." in value.split("/"):
        raise GitHubBrokerError("INVALID_REPOSITORY_PATH")
    lowered = urllib.parse.unquote(value.lower())
    basename = lowered.rsplit("/", 1)[-1]
    for pattern in _SENSITIVE_PATH_PATTERNS:
        if fnmatch.fnmatchcase(lowered, pattern) or fnmatch.fnmatchcase(basename, pattern):
            raise GitHubBrokerError("SENSITIVE_CREDENTIAL_PATH_BLOCKED")
    return value


def _parse_target(target: str, *, owner: str, allow_wildcard_repo: bool = False) -> tuple[str, str]:
    prefix = "github:"
    value = str(target).strip()
    if not value.startswith(prefix):
        raise GitHubBrokerError("GITHUB_TARGET_PREFIX_REQUIRED")
    rest = value[len(prefix):]
    parts = rest.split("/")
    if len(parts) != 2:
        raise GitHubBrokerError("GITHUB_TARGET_MUST_BE_OWNER_REPOSITORY")
    target_owner, repo = parts
    if target_owner != owner:
        raise CapabilityDenied("GITHUB_OWNER_OUTSIDE_OPERATOR_SCOPE")
    if repo == "*" and allow_wildcard_repo:
        return target_owner, repo
    if not repo or repo == "*" or any(ch in repo for ch in "\\?#%"):
        raise GitHubBrokerError("INVALID_GITHUB_REPOSITORY_NAME")
    return target_owner, repo


def _repo_path(owner: str, repo: str) -> str:
    return f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"


def _require(parameters: Mapping[str, Any], key: str) -> Any:
    if key not in parameters:
        raise GitHubBrokerError(f"MISSING_PARAMETER:{key}")
    return parameters[key]


def _positive_int(value: Any, *, name: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise GitHubBrokerError(f"{name}_MUST_BE_POSITIVE")
    return parsed


@dataclass
class GitHubThirdWishBroker:
    transport: GitHubTransport
    owner: str = DEFAULT_OWNER
    protected_branches: tuple[str, ...] = ("main", "master", "trunk")

    REGISTERED_CAPABILITIES = (
        "GITHUB.REPOSITORY.READ",
        "GITHUB.CODE.SEARCH",
        "GITHUB.ISSUE.READ",
        "GITHUB.PR.READ",
        "GITHUB.BRANCH.CREATE",
        "GITHUB.FILE.WRITE_BRANCH",
        "GITHUB.ISSUE.CREATE",
        "GITHUB.PR.CREATE",
        "GITHUB.COMMENT.CREATE",
    )

    INTENTIONALLY_UNREGISTERED_HIGH_IMPACT = (
        "GITHUB.REPOSITORY.ADMIN",
        "GITHUB.DESTRUCTIVE",
    )

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        handlers = {
            "GITHUB.REPOSITORY.READ": self.repository_read,
            "GITHUB.CODE.SEARCH": self.code_search,
            "GITHUB.ISSUE.READ": self.issue_read,
            "GITHUB.PR.READ": self.pr_read,
            "GITHUB.BRANCH.CREATE": self.branch_create,
            "GITHUB.FILE.WRITE_BRANCH": self.file_write_branch,
            "GITHUB.ISSUE.CREATE": self.issue_create,
            "GITHUB.PR.CREATE": self.pr_create,
            "GITHUB.COMMENT.CREATE": self.comment_create,
        }
        for capability_id, handler in handlers.items():
            fabric.register_handler(capability_id, handler, preflight=self.preflight)

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        """Pure local validation. This method MUST NOT call the GitHub transport."""
        cap = intent.capability_id
        operation = intent.operation.upper()
        params = intent.parameters
        allow_wildcard = cap == "GITHUB.CODE.SEARCH"
        owner, repo = _parse_target(intent.target, owner=self.owner, allow_wildcard_repo=allow_wildcard)

        if cap == "GITHUB.REPOSITORY.READ":
            if operation == "GET_REPOSITORY":
                pass
            elif operation == "GET_CONTENT":
                _validate_repo_path(str(_require(params, "path")))
                if params.get("ref") is not None:
                    _validate_branch(str(params["ref"]))
            else:
                raise GitHubBrokerError("UNSUPPORTED_REPOSITORY_READ_OPERATION")
        elif cap == "GITHUB.CODE.SEARCH":
            if operation not in {"SEARCH", "SEARCH_CODE"}:
                raise GitHubBrokerError("UNSUPPORTED_CODE_SEARCH_OPERATION")
            if not str(_require(params, "query")).strip():
                raise GitHubBrokerError("EMPTY_CODE_SEARCH_QUERY")
            if "per_page" in params and not 1 <= _positive_int(params["per_page"], name="PER_PAGE") <= 50:
                raise GitHubBrokerError("PER_PAGE_OUT_OF_RANGE")
        elif cap == "GITHUB.ISSUE.READ":
            if operation == "GET_ISSUE":
                _positive_int(_require(params, "number"), name="ISSUE_NUMBER")
            elif operation == "LIST_ISSUES":
                if params.get("state", "open") not in {"open", "closed", "all"}:
                    raise GitHubBrokerError("INVALID_ISSUE_STATE")
            else:
                raise GitHubBrokerError("UNSUPPORTED_ISSUE_READ_OPERATION")
        elif cap == "GITHUB.PR.READ":
            if operation == "GET_PR":
                _positive_int(_require(params, "number"), name="PR_NUMBER")
            elif operation == "LIST_PRS":
                if params.get("state", "open") not in {"open", "closed", "all"}:
                    raise GitHubBrokerError("INVALID_PR_STATE")
            else:
                raise GitHubBrokerError("UNSUPPORTED_PR_READ_OPERATION")
        elif cap == "GITHUB.BRANCH.CREATE":
            if operation not in {"CREATE_BRANCH", "BRANCH_CREATE"}:
                raise GitHubBrokerError("UNSUPPORTED_BRANCH_CREATE_OPERATION")
            new_branch = _validate_branch(str(_require(params, "new_branch")))
            from_ref = _validate_branch(str(params.get("from_ref", "main")))
            if new_branch == from_ref:
                raise GitHubBrokerError("NEW_BRANCH_MUST_DIFFER_FROM_SOURCE")
            if new_branch in self.protected_branches:
                raise GitHubBrokerError("REFERENCE_BROKER_WILL_NOT_CREATE_PROTECTED_BRANCH_NAME")
        elif cap == "GITHUB.FILE.WRITE_BRANCH":
            if operation not in {"WRITE_FILE", "UPSERT_FILE"}:
                raise GitHubBrokerError("UNSUPPORTED_FILE_WRITE_OPERATION")
            _validate_repo_path(str(_require(params, "path")))
            branch = _validate_branch(str(_require(params, "branch")))
            if branch in self.protected_branches:
                raise GitHubBrokerError("REFERENCE_BROKER_REQUIRES_NON_PROTECTED_WRITE_BRANCH")
            _require(params, "content")
            message = str(params.get("message") or "JANUS Third Wish broker update").strip()
            if not message:
                raise GitHubBrokerError("COMMIT_MESSAGE_REQUIRED")
        elif cap == "GITHUB.ISSUE.CREATE":
            if operation not in {"CREATE_ISSUE", "ISSUE_CREATE"}:
                raise GitHubBrokerError("UNSUPPORTED_ISSUE_CREATE_OPERATION")
            if not str(_require(params, "title")).strip():
                raise GitHubBrokerError("ISSUE_TITLE_REQUIRED")
        elif cap == "GITHUB.PR.CREATE":
            if operation not in {"CREATE_PR", "PR_CREATE"}:
                raise GitHubBrokerError("UNSUPPORTED_PR_CREATE_OPERATION")
            if not str(_require(params, "title")).strip():
                raise GitHubBrokerError("PR_TITLE_REQUIRED")
            head = _validate_branch(str(_require(params, "head")))
            base = _validate_branch(str(params.get("base", "main")))
            if head == base:
                raise GitHubBrokerError("PR_HEAD_MUST_DIFFER_FROM_BASE")
        elif cap == "GITHUB.COMMENT.CREATE":
            if operation not in {"CREATE_COMMENT", "COMMENT_CREATE"}:
                raise GitHubBrokerError("UNSUPPORTED_COMMENT_CREATE_OPERATION")
            _positive_int(_require(params, "number"), name="ISSUE_OR_PR_NUMBER")
            if not str(_require(params, "body")).strip():
                raise GitHubBrokerError("COMMENT_BODY_REQUIRED")
        else:
            raise GitHubBrokerError("CAPABILITY_NOT_INSTALLED_BY_REFERENCE_GITHUB_BROKER")

        return {
            "validated": True,
            "owner": owner,
            "repository": repo,
            "capability_id": cap,
            "operation": operation,
            "transport_called": False,
        }

    def repository_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        operation = intent.operation.upper()
        if operation == "GET_REPOSITORY":
            row = self.transport.request("GET", base)
            return {
                "owner": owner,
                "repository": repo,
                "name": row.get("name"),
                "full_name": row.get("full_name"),
                "private": row.get("private"),
                "default_branch": row.get("default_branch"),
                "archived": row.get("archived"),
                "disabled": row.get("disabled"),
                "visibility": row.get("visibility"),
                "updated_at": row.get("updated_at"),
            }
        if operation == "GET_CONTENT":
            repo_file = _validate_repo_path(str(_require(intent.parameters, "path")))
            ref = intent.parameters.get("ref")
            encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in repo_file.split("/"))
            row = self.transport.request(
                "GET",
                base + "/contents/" + encoded_path,
                query={"ref": ref} if ref else None,
            )
            if isinstance(row, list):
                return {
                    "owner": owner,
                    "repository": repo,
                    "path": repo_file,
                    "entries": [
                        {
                            "name": item.get("name"),
                            "path": item.get("path"),
                            "type": item.get("type"),
                            "sha": item.get("sha"),
                            "size": item.get("size"),
                        }
                        for item in row
                    ],
                }
            if not isinstance(row, Mapping):
                raise GitHubBrokerError("UNEXPECTED_GITHUB_CONTENT_RESPONSE")
            content = row.get("content")
            encoding = row.get("encoding")
            actor_result: dict[str, Any] = {
                "owner": owner,
                "repository": repo,
                "path": row.get("path") or repo_file,
                "type": row.get("type"),
                "sha": row.get("sha"),
                "size": row.get("size"),
                "encoding": encoding,
            }
            if encoding == "base64" and isinstance(content, str):
                raw = base64.b64decode(content, validate=False)
                if len(raw) > MAX_FILE_TEXT_BYTES:
                    raise GitHubBrokerError("GITHUB_FILE_TOO_LARGE_FOR_MODEL_READ")
                actor_result["text"] = raw.decode("utf-8", errors="replace")
            return actor_result
        raise GitHubBrokerError(f"UNSUPPORTED_REPOSITORY_READ_OPERATION:{intent.operation}")

    def code_search(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner, allow_wildcard_repo=True)
        query = str(_require(intent.parameters, "query")).strip()
        qualifier = f"user:{owner}" if repo == "*" else f"repo:{owner}/{repo}"
        row = self.transport.request(
            "GET",
            "/search/code",
            query={"q": f"{query} {qualifier}", "per_page": min(50, int(intent.parameters.get("per_page", 20)))},
        )
        items = row.get("items", []) if isinstance(row, Mapping) else []
        return {
            "scope": intent.target,
            "query": query,
            "total_count": row.get("total_count") if isinstance(row, Mapping) else None,
            "items": [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "sha": item.get("sha"),
                    "repository": (item.get("repository") or {}).get("full_name"),
                }
                for item in items[:50]
            ],
        }

    def issue_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        operation = intent.operation.upper()
        if operation == "GET_ISSUE":
            number = int(_require(intent.parameters, "number"))
            row = self.transport.request("GET", f"{base}/issues/{number}")
            return self._issue_summary(row)
        if operation == "LIST_ISSUES":
            row = self.transport.request(
                "GET",
                f"{base}/issues",
                query={
                    "state": intent.parameters.get("state", "open"),
                    "per_page": min(50, int(intent.parameters.get("per_page", 20))),
                },
            )
            if not isinstance(row, list):
                raise GitHubBrokerError("UNEXPECTED_GITHUB_ISSUE_LIST_RESPONSE")
            return {"repository": f"{owner}/{repo}", "issues": [self._issue_summary(item) for item in row[:50]]}
        raise GitHubBrokerError(f"UNSUPPORTED_ISSUE_READ_OPERATION:{intent.operation}")

    @staticmethod
    def _issue_summary(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "number": row.get("number"),
            "title": row.get("title"),
            "state": row.get("state"),
            "body": row.get("body"),
            "user": (row.get("user") or {}).get("login"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "pull_request": bool(row.get("pull_request")),
        }

    def pr_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        operation = intent.operation.upper()
        if operation == "GET_PR":
            number = int(_require(intent.parameters, "number"))
            row = self.transport.request("GET", f"{base}/pulls/{number}")
            return self._pr_summary(row)
        if operation == "LIST_PRS":
            row = self.transport.request(
                "GET",
                f"{base}/pulls",
                query={
                    "state": intent.parameters.get("state", "open"),
                    "per_page": min(50, int(intent.parameters.get("per_page", 20))),
                },
            )
            if not isinstance(row, list):
                raise GitHubBrokerError("UNEXPECTED_GITHUB_PR_LIST_RESPONSE")
            return {"repository": f"{owner}/{repo}", "pull_requests": [self._pr_summary(item) for item in row[:50]]}
        raise GitHubBrokerError(f"UNSUPPORTED_PR_READ_OPERATION:{intent.operation}")

    @staticmethod
    def _pr_summary(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "number": row.get("number"),
            "title": row.get("title"),
            "state": row.get("state"),
            "body": row.get("body"),
            "draft": row.get("draft"),
            "head": (row.get("head") or {}).get("ref"),
            "base": (row.get("base") or {}).get("ref"),
            "mergeable": row.get("mergeable"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def branch_create(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        new_branch = _validate_branch(str(_require(intent.parameters, "new_branch")))
        from_ref = _validate_branch(str(intent.parameters.get("from_ref", "main")))
        source = self.transport.request("GET", f"{base}/git/ref/heads/{urllib.parse.quote(from_ref, safe='')}")
        sha = ((source.get("object") or {}).get("sha")) if isinstance(source, Mapping) else None
        if not sha:
            raise GitHubBrokerError("SOURCE_BRANCH_SHA_MISSING")
        created = self.transport.request(
            "POST",
            f"{base}/git/refs",
            payload={"ref": f"refs/heads/{new_branch}", "sha": sha},
        )
        return {
            "repository": f"{owner}/{repo}",
            "new_branch": new_branch,
            "source_branch": from_ref,
            "source_sha": sha,
            "created_ref": created.get("ref") if isinstance(created, Mapping) else None,
        }

    def file_write_branch(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        repo_file = _validate_repo_path(str(_require(intent.parameters, "path")))
        branch = _validate_branch(str(_require(intent.parameters, "branch")))
        content = str(_require(intent.parameters, "content"))
        message = str(intent.parameters.get("message") or "JANUS Third Wish broker update").strip()
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in repo_file.split("/"))
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if intent.parameters.get("sha"):
            payload["sha"] = str(intent.parameters["sha"])
        row = self.transport.request("PUT", f"{base}/contents/{encoded_path}", payload=payload)
        if not isinstance(row, Mapping):
            raise GitHubBrokerError("UNEXPECTED_GITHUB_FILE_WRITE_RESPONSE")
        commit = row.get("commit") or {}
        written = row.get("content") or {}
        return {
            "repository": f"{owner}/{repo}",
            "path": repo_file,
            "branch": branch,
            "content_sha": written.get("sha"),
            "commit_sha": commit.get("sha"),
            "input_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "raw_content_returned": False,
        }

    def issue_create(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        payload: dict[str, Any] = {
            "title": str(_require(intent.parameters, "title")),
            "body": str(intent.parameters.get("body") or ""),
        }
        if "labels" in intent.parameters:
            payload["labels"] = list(intent.parameters["labels"])
        row = self.transport.request("POST", f"{base}/issues", payload=payload)
        return {"repository": f"{owner}/{repo}", "number": row.get("number"), "state": row.get("state"), "title": row.get("title")}

    def pr_create(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        head = _validate_branch(str(_require(intent.parameters, "head")))
        base_branch = _validate_branch(str(intent.parameters.get("base", "main")))
        payload = {
            "title": str(_require(intent.parameters, "title")),
            "head": head,
            "base": base_branch,
            "body": str(intent.parameters.get("body") or ""),
            "draft": bool(intent.parameters.get("draft", False)),
        }
        row = self.transport.request("POST", f"{base}/pulls", payload=payload)
        return {"repository": f"{owner}/{repo}", "number": row.get("number"), "state": row.get("state"), "title": row.get("title"), "head": head, "base": base_branch}

    def comment_create(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        base = _repo_path(owner, repo)
        number = int(_require(intent.parameters, "number"))
        body = str(_require(intent.parameters, "body"))
        row = self.transport.request("POST", f"{base}/issues/{number}/comments", payload={"body": body})
        return {"repository": f"{owner}/{repo}", "issue_or_pr_number": number, "comment_id": row.get("id"), "created_at": row.get("created_at")}
