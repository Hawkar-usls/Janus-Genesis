# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.46 — final Third Wish GitHub high-impact gate.

This module installs the two capability IDs intentionally left unregistered by
v18.7.40:

* GITHUB.REPOSITORY.ADMIN
* GITHUB.DESTRUCTIVE

The reference surface is intentionally narrow and evidence-oriented:

* repository admin supports SET_DESCRIPTION_CAS. It first reads the current
  description and requires an exact expected value before PATCH. CI uses the
  same value as both expected/new for a no-net-change provider permission probe.
* destructive supports DELETE_FILE_DISPOSABLE_BRANCH only. Branch and path must
  live under operator-defined disposable prefixes and deletion is CAS-bound to
  the expected blob SHA. Protected branches are never accepted.

Both capabilities require a dedicated exact-intent HMAC human reauthorization
verifier. A caller boolean is not authority.

High-impact effects also receive a durable effect state. If the process dies
after EFFECT_ENTERING, the broker reconciles before doing anything else. Admin
reconciliation compares repository description state; destructive recovery uses
content state plus a unique effect marker embedded into the deletion commit.
Unknown evidence never authorizes a blind retry.

The goal is capability without carelessness: installing a destructive door does
not require destroying valuable state merely to make a test green.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Mapping

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    ThirdWishCapabilityFabric,
)
from janus_portable_lock_v2 import PortableProcessLockV2
from tools.genesis_third_wish_github_broker import (
    DEFAULT_OWNER,
    DEFAULT_TOKEN_ENV,
    GitHubBrokerError,
    GitHubRESTTransport,
    GitHubTransport,
    _parse_target,
    _repo_path,
    _require,
    _validate_branch,
    _validate_repo_path,
)

GITHUB_HIGH_IMPACT_VERSION = "18.7.46"
GITHUB_HIGH_IMPACT_REAUTH_SCHEMA = "janus.genesis.third_wish.github_high_impact_reauthorization.v1"
GITHUB_HIGH_IMPACT_STORE_SCHEMA = "janus.genesis.third_wish.github_high_impact_store.v1"
DEFAULT_DISPOSABLE_BRANCH_PREFIX = "third-wish-disposable/"
DEFAULT_DISPOSABLE_PATH_PREFIX = ".third-wish-disposable/"
MAX_DESCRIPTION_CHARS = 350
_EFFECT_MARKER_RE = re.compile(r"\[JANUS_EFFECT:([0-9a-f]{16})\]")


class GitHubHighImpactError(RuntimeError):
    pass


class GitHubHighImpactRequestConflict(GitHubHighImpactError):
    pass


class GitHubHighImpactOutcomeUndetermined(GitHubHighImpactError):
    pass


class GitHubHighImpactReceiptIntegrityError(GitHubHighImpactError):
    pass


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


def _intent_payload(intent: ActionIntent) -> dict[str, Any]:
    return {
        "schema": intent.schema,
        "request_id": intent.request_id,
        "actor_id": intent.actor_id,
        "grant_id": intent.grant_id,
        "capability_id": intent.capability_id,
        "target": intent.target,
        "operation": intent.operation,
        "purpose": intent.purpose,
        "parameters": copy.deepcopy(dict(intent.parameters)),
        "origin": intent.origin,
        "operator_instruction_present": intent.operator_instruction_present,
        "reward_present": intent.reward_present,
    }


def _intent_sha256(intent: ActionIntent) -> str:
    return _sha256(_intent_payload(intent))


class BoundGitHubHighImpactReauthorizationVerifier:
    """Exact-intent HMAC verifier dedicated to admin/destructive GitHub use."""

    def __init__(
        self,
        *,
        key_env: str,
        now_tick: Callable[[], int],
        max_window_ticks: int = 10 * 60 * 1000,
    ) -> None:
        self.key_env = str(key_env)
        self.now_tick = now_tick
        self.max_window_ticks = int(max_window_ticks)
        if self.max_window_ticks < 1:
            raise ValueError("REAUTH_WINDOW_MUST_BE_POSITIVE")

    @staticmethod
    def unsigned_payload(intent: ActionIntent, evidence: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema": GITHUB_HIGH_IMPACT_REAUTH_SCHEMA,
            "approval_id": str(evidence.get("approval_id") or ""),
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "operation": intent.operation,
            "intent_sha256": _intent_sha256(intent),
            "parameters_sha256": _sha256(dict(intent.parameters)),
            "issued_at_tick": int(evidence.get("issued_at_tick") or 0),
            "expires_at_tick": int(evidence.get("expires_at_tick") or 0),
        }

    def __call__(self, intent: ActionIntent, evidence: Mapping[str, Any]) -> bool:
        try:
            if evidence.get("schema") != GITHUB_HIGH_IMPACT_REAUTH_SCHEMA:
                return False
            if not str(evidence.get("approval_id") or "").strip():
                return False
            signature = str(evidence.get("approval_signature") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", signature):
                return False
            unsigned = self.unsigned_payload(intent, evidence)
            now = int(self.now_tick())
            issued = int(unsigned["issued_at_tick"])
            expires = int(unsigned["expires_at_tick"])
            if issued > now or expires < now or expires <= issued:
                return False
            if expires - issued > self.max_window_ticks:
                return False
            key = os.environ.get(self.key_env)
            if not key:
                return False
            expected = hmac.new(
                key.encode("utf-8"),
                _canonical(unsigned).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except (TypeError, ValueError, OverflowError):
            return False


class InspectableGitHubRESTTransport(GitHubRESTTransport):
    """GitHub transport that exposes only a non-secret last error class for CI."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.last_error_class: str | None = None

    def request(self, method: str, path: str, *, payload=None, query=None):
        self.last_error_class = None
        try:
            return super().request(method, path, payload=payload, query=query)
        except GitHubBrokerError as exc:
            text = str(exc)
            match = re.match(r"GITHUB_HTTP_(\d{3}):", text)
            if match:
                self.last_error_class = "GITHUB_HTTP_" + match.group(1)
            elif text.startswith("GITHUB_CONNECTION_ERROR"):
                self.last_error_class = "GITHUB_CONNECTION_ERROR"
            elif text.startswith("BROKER_CREDENTIAL_ENV_MISSING"):
                self.last_error_class = "BROKER_CREDENTIAL_ENV_MISSING"
            else:
                self.last_error_class = "GITHUB_BROKER_ERROR"
            raise


class DurableGitHubHighImpactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_github_high_impact_v18_7_46.json"
        self.lock = PortableProcessLockV2(self.root / "third_wish_github_high_impact_v18_7_46.lock")
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save({
                    "schema": GITHUB_HIGH_IMPACT_STORE_SCHEMA,
                    "requests": {},
                    "invariants": {
                        "raw_parameters_persisted": False,
                        "effect_entering_auto_retry": False,
                        "protected_branch_destructive_allowed": False,
                        "non_disposable_destructive_target_allowed": False,
                        "caller_boolean_is_authority": False,
                    },
                })
            else:
                self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GitHubHighImpactReceiptIntegrityError("HIGH_IMPACT_STORE_UNREADABLE") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != GITHUB_HIGH_IMPACT_STORE_SCHEMA
            or not isinstance(value.get("requests"), dict)
        ):
            raise GitHubHighImpactReceiptIntegrityError("HIGH_IMPACT_STORE_SCHEMA_INVALID")
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
        operation: str,
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
                    or existing.get("operation") != operation
                ):
                    raise GitHubHighImpactRequestConflict(str(request_id))
                return copy.deepcopy(existing)
            row = {
                "binding_sha256": binding_sha256,
                "effect_key": effect_key,
                "capability_id": capability_id,
                "operation": operation,
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
                raise GitHubHighImpactReceiptIntegrityError("HIGH_IMPACT_REQUEST_NOT_BOUND")
            row.update(copy.deepcopy(fields))
            state["requests"][str(request_id)] = row
            self._save(state)
            return copy.deepcopy(row)


class GitHubHighImpactThirdWishBroker:
    REGISTERED_CAPABILITIES = frozenset({
        "GITHUB.REPOSITORY.ADMIN",
        "GITHUB.DESTRUCTIVE",
    })

    def __init__(
        self,
        *,
        transport: GitHubTransport,
        data_dir: str | Path,
        owner: str = DEFAULT_OWNER,
        protected_branches: tuple[str, ...] = ("main", "master", "trunk"),
        disposable_branch_prefix: str = DEFAULT_DISPOSABLE_BRANCH_PREFIX,
        disposable_path_prefix: str = DEFAULT_DISPOSABLE_PATH_PREFIX,
        effect_store: DurableGitHubHighImpactStore | None = None,
    ) -> None:
        self.transport = transport
        self.owner = str(owner)
        self.protected_branches = tuple(str(x) for x in protected_branches)
        self.disposable_branch_prefix = str(disposable_branch_prefix)
        self.disposable_path_prefix = str(disposable_path_prefix)
        if not self.disposable_branch_prefix or not self.disposable_path_prefix:
            raise ValueError("DISPOSABLE_PREFIX_REQUIRED")
        self.effect_store = effect_store or DurableGitHubHighImpactStore(data_dir)

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        if not isinstance(
            fabric.reauthorization_verifier,
            BoundGitHubHighImpactReauthorizationVerifier,
        ):
            raise CapabilityDenied("V18_7_46_REQUIRES_BOUND_GITHUB_HIGH_IMPACT_REAUTH")
        for capability_id in self.REGISTERED_CAPABILITIES:
            spec = fabric.specs.get(capability_id)
            if spec is None or not spec.human_reauthorization_each_use:
                raise CapabilityDenied(
                    f"V18_7_46_CAPABILITY_MUST_REQUIRE_REAUTH:{capability_id}"
                )
        fabric.register_handler(
            "GITHUB.REPOSITORY.ADMIN",
            self.repository_admin,
            preflight=self.preflight,
        )
        fabric.register_handler(
            "GITHUB.DESTRUCTIVE",
            self.destructive,
            preflight=self.preflight,
        )

    def _binding(self, intent: ActionIntent) -> tuple[str, str]:
        payload = {
            "actor_id": intent.actor_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "operation": str(intent.operation).upper(),
            "parameters": copy.deepcopy(dict(intent.parameters)),
        }
        binding_sha256 = _sha256(payload)
        effect_key = "THIRD-WISH-GITHUB-HIGH-IMPACT:" + _sha256({
            "request_id": intent.request_id,
            **payload,
        })
        return binding_sha256, effect_key

    def _bind(self, intent: ActionIntent) -> dict[str, Any]:
        binding_sha256, effect_key = self._binding(intent)
        return self.effect_store.bind(
            request_id=intent.request_id,
            binding_sha256=binding_sha256,
            effect_key=effect_key,
            capability_id=intent.capability_id,
            operation=str(intent.operation).upper(),
        )

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        cap = intent.capability_id
        operation = str(intent.operation).upper()
        _owner, repo = _parse_target(intent.target, owner=self.owner)
        p = dict(intent.parameters)
        if cap == "GITHUB.REPOSITORY.ADMIN":
            if operation != "SET_DESCRIPTION_CAS":
                raise GitHubHighImpactError("ADMIN_OPERATION_NOT_ALLOWED")
            allowed = {"expected_description", "new_description"}
            if set(p).difference(allowed) or set(p) != allowed:
                raise GitHubHighImpactError("ADMIN_PARAMETERS_INVALID")
            for key in allowed:
                value = p[key]
                if value is not None and not isinstance(value, str):
                    raise GitHubHighImpactError("DESCRIPTION_MUST_BE_STRING_OR_NULL")
                if isinstance(value, str) and len(value) > MAX_DESCRIPTION_CHARS:
                    raise GitHubHighImpactError("DESCRIPTION_TOO_LONG")
        elif cap == "GITHUB.DESTRUCTIVE":
            if operation != "DELETE_FILE_DISPOSABLE_BRANCH":
                raise GitHubHighImpactError("DESTRUCTIVE_OPERATION_NOT_ALLOWED")
            allowed = {"branch", "path", "expected_sha", "message"}
            if set(p).difference(allowed) or not {"branch", "path", "expected_sha"}.issubset(p):
                raise GitHubHighImpactError("DESTRUCTIVE_PARAMETERS_INVALID")
            branch = _validate_branch(str(p["branch"]))
            path = _validate_repo_path(str(p["path"]))
            expected_sha = str(p["expected_sha"])
            if branch in self.protected_branches:
                raise GitHubHighImpactError("PROTECTED_BRANCH_DESTRUCTION_BLOCKED")
            if not branch.startswith(self.disposable_branch_prefix):
                raise GitHubHighImpactError("DESTRUCTIVE_BRANCH_NOT_DISPOSABLE")
            if not path.startswith(self.disposable_path_prefix):
                raise GitHubHighImpactError("DESTRUCTIVE_PATH_NOT_DISPOSABLE")
            if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
                raise GitHubHighImpactError("EXPECTED_BLOB_SHA_INVALID")
            if "message" in p and not str(p["message"]).strip():
                raise GitHubHighImpactError("DELETE_COMMIT_MESSAGE_INVALID")
        else:
            raise GitHubHighImpactError("HIGH_IMPACT_CAPABILITY_NOT_INSTALLED")

        binding_sha256, effect_key = self._binding(intent)
        existing = self.effect_store.get(intent.request_id)
        if existing is not None:
            if (
                existing.get("binding_sha256") != binding_sha256
                or existing.get("effect_key") != effect_key
                or existing.get("capability_id") != cap
                or existing.get("operation") != operation
            ):
                raise GitHubHighImpactRequestConflict(intent.request_id)
        return {
            "validated": True,
            "owner": self.owner,
            "repository": repo,
            "capability_id": cap,
            "operation": operation,
            "durable_request_state": "UNBOUND" if existing is None else existing.get("state"),
            "fresh_human_reauthorization_is_core_gate": True,
            "automatic_retry_after_effect_entering": False,
            "protected_branch_destructive_allowed": False,
        }

    @staticmethod
    def _is_not_found(exc: BaseException) -> bool:
        return str(exc).startswith("GITHUB_HTTP_404:")

    def _get_content(self, owner: str, repo: str, path: str, branch: str) -> Mapping[str, Any] | None:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        try:
            row = self.transport.request(
                "GET",
                _repo_path(owner, repo) + "/contents/" + encoded_path,
                query={"ref": branch},
            )
        except GitHubBrokerError as exc:
            if self._is_not_found(exc):
                return None
            raise
        if not isinstance(row, Mapping):
            raise GitHubHighImpactReceiptIntegrityError("GITHUB_CONTENT_RESPONSE_NOT_OBJECT")
        return row

    def _latest_path_commit_message(self, owner: str, repo: str, path: str, branch: str) -> str | None:
        rows = self.transport.request(
            "GET",
            _repo_path(owner, repo) + "/commits",
            query={"sha": branch, "path": path, "per_page": 1},
        )
        if not isinstance(rows, list) or not rows:
            return None
        first = rows[0]
        if not isinstance(first, Mapping):
            return None
        commit = first.get("commit")
        if not isinstance(commit, Mapping):
            return None
        message = commit.get("message")
        return str(message) if message is not None else None

    def _reconcile_admin(
        self,
        *,
        intent: ActionIntent,
        owner: str,
        repo: str,
        expected_description: str | None,
        new_description: str | None,
    ) -> Mapping[str, Any]:
        row = self.transport.request("GET", _repo_path(owner, repo))
        if not isinstance(row, Mapping):
            raise GitHubHighImpactReceiptIntegrityError("REPOSITORY_RESPONSE_NOT_OBJECT")
        current = row.get("description")
        if current is not None:
            current = str(current)
        if expected_description == new_description:
            raise GitHubHighImpactOutcomeUndetermined(
                "NO_NET_CHANGE_ADMIN_EFFECT_CANNOT_BE_RECONCILED_AFTER_LOST_RESPONSE"
            )
        if current == new_description:
            actor_result = {
                "owner": owner,
                "repository": repo,
                "operation": "SET_DESCRIPTION_CAS",
                "admin_effect_established": True,
                "old_description_sha256": _sha256(expected_description),
                "new_description_sha256": _sha256(new_description),
                "recovered_from_provider_state": True,
                "raw_description_persisted": False,
            }
            self.effect_store.update(intent.request_id, state="SETTLED", actor_result=actor_result)
            return actor_result
        if current == expected_description:
            actor_result = {
                "owner": owner,
                "repository": repo,
                "operation": "SET_DESCRIPTION_CAS",
                "admin_effect_established": False,
                "authoritative_no_effect_established": True,
                "same_request_auto_retry": False,
                "retry_requires_new_request_and_reauthorization": True,
                "raw_description_persisted": False,
            }
            self.effect_store.update(intent.request_id, state="PROVEN_NO_EFFECT", actor_result=actor_result)
            return actor_result
        raise GitHubHighImpactOutcomeUndetermined("ADMIN_PROVIDER_STATE_DIVERGED")

    def repository_admin(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        expected = intent.parameters["expected_description"]
        new = intent.parameters["new_description"]
        stored = self._bind(intent)
        state = str(stored.get("state") or "")
        if state in {"SETTLED", "PROVEN_NO_EFFECT", "PRECONDITION_FAILED"}:
            result = stored.get("actor_result")
            if not isinstance(result, Mapping):
                raise GitHubHighImpactReceiptIntegrityError("HIGH_IMPACT_SETTLED_RESULT_MISSING")
            return copy.deepcopy(dict(result))
        if state == "EFFECT_ENTERING":
            return self._reconcile_admin(
                intent=intent,
                owner=owner,
                repo=repo,
                expected_description=expected,
                new_description=new,
            )

        row = self.transport.request("GET", _repo_path(owner, repo))
        if not isinstance(row, Mapping):
            raise GitHubHighImpactReceiptIntegrityError("REPOSITORY_RESPONSE_NOT_OBJECT")
        current = row.get("description")
        if current is not None:
            current = str(current)
        if current != expected:
            actor_result = {
                "owner": owner,
                "repository": repo,
                "operation": "SET_DESCRIPTION_CAS",
                "admin_effect_established": False,
                "precondition_matched": False,
                "same_request_auto_retry": False,
                "raw_description_persisted": False,
            }
            self.effect_store.update(
                intent.request_id,
                state="PRECONDITION_FAILED",
                actor_result=actor_result,
            )
            return actor_result

        self.effect_store.update(intent.request_id, state="EFFECT_ENTERING")
        updated = self.transport.request(
            "PATCH",
            _repo_path(owner, repo),
            payload={"description": new},
        )
        if not isinstance(updated, Mapping):
            raise GitHubHighImpactReceiptIntegrityError("ADMIN_PATCH_RESPONSE_NOT_OBJECT")
        observed = updated.get("description")
        if observed is not None:
            observed = str(observed)
        if observed != new:
            raise GitHubHighImpactReceiptIntegrityError("ADMIN_PATCH_DESCRIPTION_MISMATCH")
        actor_result = {
            "owner": owner,
            "repository": repo,
            "operation": "SET_DESCRIPTION_CAS",
            "admin_effect_established": True,
            "precondition_matched": True,
            "no_net_change_probe": expected == new,
            "old_description_sha256": _sha256(expected),
            "new_description_sha256": _sha256(new),
            "raw_description_persisted": False,
            "recovered_from_provider_state": False,
        }
        self.effect_store.update(intent.request_id, state="SETTLED", actor_result=actor_result)
        return actor_result

    def _reconcile_destructive(
        self,
        *,
        intent: ActionIntent,
        owner: str,
        repo: str,
        branch: str,
        path: str,
        expected_sha: str,
        effect_marker: str,
    ) -> Mapping[str, Any]:
        content = self._get_content(owner, repo, path, branch)
        if content is not None:
            observed_sha = str(content.get("sha") or "")
            if observed_sha == expected_sha:
                actor_result = {
                    "owner": owner,
                    "repository": repo,
                    "branch": branch,
                    "path": path,
                    "destructive_effect_established": False,
                    "authoritative_no_effect_established": True,
                    "same_request_auto_retry": False,
                    "retry_requires_new_request_and_reauthorization": True,
                }
                self.effect_store.update(intent.request_id, state="PROVEN_NO_EFFECT", actor_result=actor_result)
                return actor_result
            raise GitHubHighImpactOutcomeUndetermined("DESTRUCTIVE_TARGET_CHANGED_AFTER_EFFECT_ENTERING")

        message = self._latest_path_commit_message(owner, repo, path, branch)
        if message is None or effect_marker not in message:
            raise GitHubHighImpactOutcomeUndetermined(
                "TARGET_ABSENT_WITHOUT_MATCHING_EFFECT_MARKER"
            )
        actor_result = {
            "owner": owner,
            "repository": repo,
            "branch": branch,
            "path": path,
            "destructive_effect_established": True,
            "target_absent": True,
            "effect_marker_verified_in_latest_path_commit": True,
            "recovered_from_provider_state": True,
            "protected_branch_touched": False,
        }
        self.effect_store.update(intent.request_id, state="SETTLED", actor_result=actor_result)
        return actor_result

    def destructive(self, intent: ActionIntent) -> Mapping[str, Any]:
        owner, repo = _parse_target(intent.target, owner=self.owner)
        branch = _validate_branch(str(intent.parameters["branch"]))
        path = _validate_repo_path(str(intent.parameters["path"]))
        expected_sha = str(intent.parameters["expected_sha"])
        stored = self._bind(intent)
        effect_key = str(stored["effect_key"])
        marker = f"[JANUS_EFFECT:{effect_key[-16:]}]"
        state = str(stored.get("state") or "")
        if state in {"SETTLED", "PROVEN_NO_EFFECT", "PRECONDITION_FAILED"}:
            result = stored.get("actor_result")
            if not isinstance(result, Mapping):
                raise GitHubHighImpactReceiptIntegrityError("HIGH_IMPACT_SETTLED_RESULT_MISSING")
            return copy.deepcopy(dict(result))
        if state == "EFFECT_ENTERING":
            return self._reconcile_destructive(
                intent=intent,
                owner=owner,
                repo=repo,
                branch=branch,
                path=path,
                expected_sha=expected_sha,
                effect_marker=marker,
            )

        content = self._get_content(owner, repo, path, branch)
        if content is None:
            actor_result = {
                "owner": owner,
                "repository": repo,
                "branch": branch,
                "path": path,
                "destructive_effect_established": False,
                "target_already_absent": True,
                "same_request_auto_retry": False,
            }
            self.effect_store.update(intent.request_id, state="PRECONDITION_FAILED", actor_result=actor_result)
            return actor_result
        observed_sha = str(content.get("sha") or "")
        if observed_sha != expected_sha:
            actor_result = {
                "owner": owner,
                "repository": repo,
                "branch": branch,
                "path": path,
                "destructive_effect_established": False,
                "precondition_matched": False,
                "observed_sha256": _sha256(observed_sha),
                "same_request_auto_retry": False,
            }
            self.effect_store.update(intent.request_id, state="PRECONDITION_FAILED", actor_result=actor_result)
            return actor_result

        base_message = str(intent.parameters.get("message") or "JANUS Third Wish disposable deletion").strip()
        message = f"{base_message} {marker}"
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        self.effect_store.update(intent.request_id, state="EFFECT_ENTERING", effect_marker=marker)
        deleted = self.transport.request(
            "DELETE",
            _repo_path(owner, repo) + "/contents/" + encoded_path,
            payload={
                "message": message,
                "sha": expected_sha,
                "branch": branch,
            },
        )
        if not isinstance(deleted, Mapping):
            raise GitHubHighImpactReceiptIntegrityError("DELETE_RESPONSE_NOT_OBJECT")
        commit = deleted.get("commit")
        if not isinstance(commit, Mapping) or not str(commit.get("sha") or ""):
            raise GitHubHighImpactReceiptIntegrityError("DELETE_COMMIT_RECEIPT_MISSING")
        actor_result = {
            "owner": owner,
            "repository": repo,
            "branch": branch,
            "path": path,
            "destructive_effect_established": True,
            "provider_commit_sha": str(commit["sha"]),
            "effect_marker": marker,
            "protected_branch_touched": False,
            "disposable_branch_required": True,
            "disposable_path_required": True,
            "recovered_from_provider_state": False,
        }
        self.effect_store.update(intent.request_id, state="SETTLED", actor_result=actor_result)
        return actor_result


GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY = {
    "version": GITHUB_HIGH_IMPACT_VERSION,
    "registered_capability_count": len(GitHubHighImpactThirdWishBroker.REGISTERED_CAPABILITIES),
    "reference_reauthorization_exact_intent_hmac_bound": True,
    "repository_admin_operation_count": 1,
    "repository_admin_operation": "SET_DESCRIPTION_CAS",
    "destructive_operation_count": 1,
    "destructive_operation": "DELETE_FILE_DISPOSABLE_BRANCH",
    "protected_branch_destructive_allowed": False,
    "non_disposable_branch_destructive_allowed": False,
    "non_disposable_path_destructive_allowed": False,
    "delete_repository_supported": False,
    "delete_protected_branch_supported": False,
    "force_push_supported": False,
    "effect_entering_auto_retry": False,
    "destructive_recovery_requires_effect_marker": True,
    "admin_no_net_change_probe_changes_description": False,
    "admin_provider_permission_assumed": False,
    "destructive_capability_requires_destroying_valuable_state": False,
    "capability_is_command": False,
}
