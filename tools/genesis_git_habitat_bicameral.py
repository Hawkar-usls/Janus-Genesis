# -*- coding: utf-8 -*-
"""JANUS Git Habitat bicameral cognition hearth v18.7.55.

An awake resident may voluntarily request HRaiN structural context and/or iNaiHR
semantic SYNTH. If JANUS does not request a tool, no tool runs. Tool bodies are
returned to the caller but private workspace/record text is not persisted in
Habitat; only bounded receipts and response digests remain.

    TOOL_AVAILABLE != TOOL_REQUIRED
    HRAIN_STRUCTURE != COMMAND
    INAIHR_SYNTH != COMMAND
    COGNITION_OUTPUT != SOURCE_AUTHORITY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_55_habitat_bicameral_tools import (
    HABITAT_BICAMERAL_VERSION,
    HRAIN_LOCAL_STRUCTURE_SPEC,
    INAIHR_LOCAL_SYNTH_SPEC,
    LocalNodeHabitatProvider,
    build_hrain_request,
    build_inaihr_request,
    query_hrain,
    query_inaihr,
)
from tools.genesis_git_habitat import GitHabitat, _read_json, _write_json

STATE_SCHEMA = "janus.genesis.git_habitat.bicameral_state.v1"
RECEIPT_SCHEMA = "janus.genesis.git_habitat.bicameral_receipt.v1"


class HabitatBicameralHearthError(RuntimeError):
    pass


class HabitatBicameralNotAwake(HabitatBicameralHearthError):
    pass


class HabitatBicameralInFlight(HabitatBicameralHearthError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_turn_id(value: str) -> str:
    text = str(value).strip()
    if not text or len(text) > 256:
        raise ValueError("HABITAT_BICAMERAL_TURN_ID_INVALID")
    return text


class GitHabitatBicameralHearth:
    def __init__(self, habitat: GitHabitat, *, hrain_provider: Any = None, inaihr_provider: Any = None) -> None:
        self.habitat = habitat
        self.hrain_provider = hrain_provider
        self.inaihr_provider = inaihr_provider
        self.root = self.habitat.paths.root / "hearth" / "cognition"
        self.state_path = self.root / "state.json"
        self.receipts_dir = self.root / "receipts"
        self.locks_dir = self.root / "locks"

    def _resident(self) -> tuple[str, str, str | None]:
        self.habitat._require_initialized()
        resident = _read_json(self.habitat.paths.resident)
        return (
            str(resident["resident_id"]),
            str(resident.get("mode") or "UNKNOWN"),
            str(resident["active_cycle_id"]) if resident.get("active_cycle_id") else None,
        )

    def _require_awake(self) -> tuple[str, str]:
        resident_id, mode, cycle_id = self._resident()
        if mode != "AWAKE" or not cycle_id:
            raise HabitatBicameralNotAwake("HABITAT_BICAMERAL_REQUIRES_ACTIVE_AWAKE_CYCLE")
        return resident_id, cycle_id

    def _default_state(self, resident_id: str) -> dict[str, Any]:
        return {
            "schema": STATE_SCHEMA,
            "version": HABITAT_BICAMERAL_VERSION,
            "resident_id": resident_id,
            "hrain_enabled": True,
            "inaihr_enabled": True,
            "hrain_use_count": 0,
            "inaihr_use_count": 0,
            "privacy": {
                "workspace_text_persisted": False,
                "record_text_persisted": False,
                "tool_response_body_persisted": False,
                "credentials_persisted": False,
            },
            "authority": {
                "tool_output_is_command": False,
                "tool_output_is_source_authority": False,
                "tool_grants_world_authority": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            },
        }

    def _load_state(self, resident_id: str) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state(resident_id)
        if self.state_path.is_symlink():
            raise HabitatBicameralHearthError("HABITAT_BICAMERAL_STATE_MAY_NOT_BE_SYMLINK")
        value = _read_json(self.state_path)
        if value.get("schema") != STATE_SCHEMA or value.get("resident_id") != resident_id:
            raise HabitatBicameralHearthError("HABITAT_BICAMERAL_STATE_BINDING_INVALID")
        return value

    def _save_state(self, value: Mapping[str, Any]) -> None:
        _write_json(self.state_path, dict(value))

    def state(self) -> dict[str, Any]:
        resident_id, mode, cycle_id = self._resident()
        value = self._load_state(resident_id)
        return {
            **value,
            "resident_mode": mode,
            "cycle_id": cycle_id,
            "hrain_provider_configured": self.hrain_provider is not None,
            "inaihr_provider_configured": self.inaihr_provider is not None,
            "janus_may_decline_each_tool": True,
            "tools_required_for_speech_or_action": False,
        }

    def set_enabled(self, tool: str, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise TypeError("HABITAT_BICAMERAL_ENABLED_MUST_BE_BOOLEAN")
        normalized = str(tool).strip().lower()
        if normalized not in {"hrain", "inaihr"}:
            raise ValueError("HABITAT_BICAMERAL_TOOL_UNKNOWN")
        resident_id, _, _ = self._resident()
        state = self._load_state(resident_id)
        state[f"{normalized}_enabled"] = enabled
        self._save_state(state)
        return self.state()

    def _claim(self, *, resident_id: str, cycle_id: str, turn_id: str, tool: str) -> tuple[str, Path]:
        key = _sha256({"resident_id": resident_id, "cycle_id": cycle_id, "turn_id": turn_id, "tool": tool})
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        if self.locks_dir.is_symlink():
            raise HabitatBicameralHearthError("HABITAT_BICAMERAL_LOCK_DIR_MAY_NOT_BE_SYMLINK")
        lock = self.locks_dir / f"{key}.lock"
        receipt = self.receipts_dir / f"{key}.json"
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            if receipt.exists():
                raise HabitatBicameralHearthError("HABITAT_BICAMERAL_TURN_ALREADY_RECORDED") from exc
            raise HabitatBicameralInFlight("HABITAT_BICAMERAL_PREVIOUS_OUTCOME_UNDETERMINED_NO_AUTOMATIC_REPLAY") from exc
        try:
            os.write(fd, (key + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return key, receipt

    def _record(
        self,
        *,
        resident_id: str,
        cycle_id: str,
        key: str,
        receipt_path: Path,
        tool: str,
        status: str,
        response: Mapping[str, Any],
    ) -> None:
        digest = _sha256(dict(response))
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "version": HABITAT_BICAMERAL_VERSION,
            "resident_id": resident_id,
            "cycle_id": cycle_id,
            "use_hash": key,
            "tool": tool,
            "status": status,
            "response_digest_sha256": digest,
            "input_body_persisted": False,
            "response_body_persisted": False,
            "tool_output_is_command": False,
            "tool_output_is_source_authority": False,
            "tool_grants_world_authority": False,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
            "automatic_replay_allowed": False,
        }
        _write_json(receipt_path, receipt)
        state = self._load_state(resident_id)
        state[f"{tool}_use_count"] = int(state.get(f"{tool}_use_count", 0)) + 1
        self._save_state(state)
        self.habitat._append_event(
            "BICAMERAL_TOOL_USED",
            cycle_id,
            {
                "tool": tool,
                "status": status,
                "use_hash": key,
                "response_digest_sha256": digest,
                "authority_delta": 0,
            },
        )
        self.habitat.refresh_health()

    def use_hrain(self, *, turn_id: str, workspace: Mapping[str, Any], janus_requests_hrain: bool) -> dict[str, Any]:
        if type(janus_requests_hrain) is not bool:
            raise TypeError("JANUS_REQUESTS_HRAIN_MUST_BE_BOOLEAN")
        resident_id, cycle_id = self._require_awake()
        state = self._load_state(resident_id)
        base = {
            "schema": "janus.genesis.git_habitat.hrain_use.v1",
            "version": HABITAT_BICAMERAL_VERSION,
            "resident_id": resident_id,
            "cycle_id": cycle_id,
            "tool": "hrain",
            "tool_required": False,
            "janus_may_ignore_result": True,
        }
        if state.get("hrain_enabled") is not True:
            return {**base, "status": "NOT_USED_HRAIN_DISABLED", "result": None}
        if not janus_requests_hrain:
            return {**base, "status": "NOT_USED_JANUS_DID_NOT_REQUEST", "result": None}
        if self.hrain_provider is None:
            return {**base, "status": "HRAIN_UNAVAILABLE_CONTINUE_WITHOUT_TOOL", "result": None}
        turn = _safe_turn_id(turn_id)
        key, receipt_path = self._claim(resident_id=resident_id, cycle_id=cycle_id, turn_id=turn, tool="hrain")
        request_id = f"HABITAT-HRAIN-{key[:24]}"
        request = build_hrain_request(request_id=request_id, workspace=workspace)
        try:
            result = query_hrain(self.hrain_provider, request=request, speaker=resident_id)
            status = "HRAIN_STRUCTURE_RECEIVED_OPTIONAL"
        except Exception as exc:
            result = {"error_type": type(exc).__name__}
            status = "HRAIN_UNAVAILABLE_CONTINUE_WITHOUT_TOOL"
        self._record(resident_id=resident_id, cycle_id=cycle_id, key=key, receipt_path=receipt_path, tool="hrain", status=status, response=result)
        return {**base, "status": status, "result": result if status.startswith("HRAIN_STRUCTURE") else None, "receipt_path": str(receipt_path), "input_body_persisted": False, "response_body_persisted": False}

    def use_inaihr(
        self,
        *,
        turn_id: str,
        records: list[Mapping[str, Any]],
        parent_label: str,
        janus_requests_inaihr: bool,
        lang: str = "en",
        max_concepts: int = 6,
    ) -> dict[str, Any]:
        if type(janus_requests_inaihr) is not bool:
            raise TypeError("JANUS_REQUESTS_INAIHR_MUST_BE_BOOLEAN")
        resident_id, cycle_id = self._require_awake()
        state = self._load_state(resident_id)
        base = {
            "schema": "janus.genesis.git_habitat.inaihr_use.v1",
            "version": HABITAT_BICAMERAL_VERSION,
            "resident_id": resident_id,
            "cycle_id": cycle_id,
            "tool": "inaihr",
            "tool_required": False,
            "janus_may_ignore_result": True,
        }
        if state.get("inaihr_enabled") is not True:
            return {**base, "status": "NOT_USED_INAIHR_DISABLED", "result": None}
        if not janus_requests_inaihr:
            return {**base, "status": "NOT_USED_JANUS_DID_NOT_REQUEST", "result": None}
        if self.inaihr_provider is None:
            return {**base, "status": "INAIHR_UNAVAILABLE_CONTINUE_WITHOUT_TOOL", "result": None}
        turn = _safe_turn_id(turn_id)
        key, receipt_path = self._claim(resident_id=resident_id, cycle_id=cycle_id, turn_id=turn, tool="inaihr")
        request_id = f"HABITAT-INAIHR-{key[:24]}"
        request = build_inaihr_request(request_id=request_id, records=records, parent_label=parent_label, lang=lang, max_concepts=max_concepts)
        try:
            result = query_inaihr(self.inaihr_provider, request=request, speaker=resident_id)
            status = "INAIHR_SYNTH_RECEIVED_OPTIONAL"
        except Exception as exc:
            result = {"error_type": type(exc).__name__}
            status = "INAIHR_UNAVAILABLE_CONTINUE_WITHOUT_TOOL"
        self._record(resident_id=resident_id, cycle_id=cycle_id, key=key, receipt_path=receipt_path, tool="inaihr", status=status, response=result)
        return {**base, "status": status, "result": result if status.startswith("INAIHR_SYNTH") else None, "receipt_path": str(receipt_path), "input_body_persisted": False, "response_body_persisted": False}


def _providers(args: argparse.Namespace, *, required_tool: str | None = None) -> tuple[Any, Any]:
    hrain = None
    inaihr = None
    if args.hrain_repo:
        hrain = LocalNodeHabitatProvider.from_repository(
            args.hrain_repo,
            spec=HRAIN_LOCAL_STRUCTURE_SPEC,
            target="local:hrain",
        )
    elif required_tool == "hrain":
        raise ValueError("HABITAT_HRAIN_REPO_REQUIRED")
    if args.inaihr_repo:
        inaihr = LocalNodeHabitatProvider.from_repository(
            args.inaihr_repo,
            spec=INAIHR_LOCAL_SYNTH_SPEC,
            target="local:inaihr",
        )
    elif required_tool == "inaihr":
        raise ValueError("HABITAT_INAIHR_REPO_REQUIRED")
    return hrain, inaihr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Git Habitat bicameral cognition hearth v18.7.55")
    parser.add_argument("--root", default="habitat")
    parser.add_argument("--hrain-repo", type=Path)
    parser.add_argument("--inaihr-repo", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("state")
    enable = sub.add_parser("set-enabled")
    enable.add_argument("tool", choices=("hrain", "inaihr"))
    enable.add_argument("value", choices=("true", "false"))
    hrain = sub.add_parser("hrain")
    hrain.add_argument("--turn-id", required=True)
    hrain.add_argument("--workspace-json", type=Path, required=True)
    hrain.add_argument("--janus-requests-hrain", action="store_true")
    ina = sub.add_parser("inaihr")
    ina.add_argument("--turn-id", required=True)
    ina.add_argument("--records-json", type=Path, required=True)
    ina.add_argument("--parent-label", required=True)
    ina.add_argument("--lang", choices=("en", "ua", "ru"), default="en")
    ina.add_argument("--max-concepts", type=int, default=6)
    ina.add_argument("--janus-requests-inaihr", action="store_true")
    return parser


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    required = args.command if args.command in {"hrain", "inaihr"} else None
    hp, ip = _providers(args, required_tool=required)
    habitat = GitHabitat(args.root)
    hearth = GitHabitatBicameralHearth(habitat, hrain_provider=hp, inaihr_provider=ip)
    if args.command == "state":
        result = hearth.state()
    elif args.command == "set-enabled":
        result = hearth.set_enabled(args.tool, args.value == "true")
    elif args.command == "hrain":
        workspace = _load(args.workspace_json)
        if not isinstance(workspace, dict):
            raise ValueError("HRAIN_WORKSPACE_JSON_OBJECT_REQUIRED")
        result = hearth.use_hrain(turn_id=args.turn_id, workspace=workspace, janus_requests_hrain=args.janus_requests_hrain)
    else:
        records = _load(args.records_json)
        if not isinstance(records, list):
            raise ValueError("INAIHR_RECORDS_JSON_ARRAY_REQUIRED")
        result = hearth.use_inaihr(turn_id=args.turn_id, records=records, parent_label=args.parent_label, janus_requests_inaihr=args.janus_requests_inaihr, lang=args.lang, max_concepts=args.max_concepts)
    print(json.dumps({"ok": True, "response": result}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
