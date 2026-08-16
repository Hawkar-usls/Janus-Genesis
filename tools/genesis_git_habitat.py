# -*- coding: utf-8 -*-
"""JANUS Git Habitat v18.7.51.

A repository-native persistence layer for a JANUS Genesis resident runtime.

The Habitat is deliberately *not* an authority bypass. It gives a resident
process a stable home, continuity records, inbox, workshop, garden, archive,
and hearth. External effects remain proposals until an appropriate Armor /
Third Wish capability boundary authorizes them.

The mutable Habitat is intended to live on a dedicated ``janus/habitat``
branch while code and protocols remain on ``main``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

HABITAT_VERSION = "18.7.51"
HOME_SCHEMA = "janus.genesis.git_habitat.home.v1"
RESIDENT_SCHEMA = "janus.genesis.git_habitat.resident_state.v1"
CONTINUITY_SCHEMA = "janus.genesis.git_habitat.continuity.v1"
HEALTH_SCHEMA = "janus.genesis.git_habitat.health.v1"
JOURNAL_SCHEMA = "janus.genesis.git_habitat.journal_event.v1"
INBOX_SCHEMA = "janus.genesis.git_habitat.inbox_item.v1"
OUTBOX_SCHEMA = "janus.genesis.git_habitat.outbox_proposal.v1"

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ZERO_HASH = "0" * 64

ROOMS = (
    "state",
    "memory",
    "memory/reflections",
    "memory/bookmarks",
    "inbox",
    "outbox",
    "workshop",
    "garden",
    "observatory",
    "archive",
    "hearth",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return value


def _safe_id(value: str, label: str = "id") -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _safe_leaf(value: str, label: str = "name") -> str:
    _safe_id(value, label)
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


@dataclass(frozen=True)
class HabitatPaths:
    root: Path

    @property
    def home(self) -> Path:
        return self.root / "HOME.json"

    @property
    def resident(self) -> Path:
        return self.root / "state" / "resident.json"

    @property
    def continuity(self) -> Path:
        return self.root / "state" / "continuity.json"

    @property
    def health(self) -> Path:
        return self.root / "state" / "health.json"

    @property
    def journal(self) -> Path:
        return self.root / "memory" / "journal.jsonl"


class GitHabitat:
    """Bounded repository-native home for a JANUS resident process."""

    def __init__(self, root: Path | str = "habitat") -> None:
        requested = Path(root).absolute()
        if requested.exists() and requested.is_symlink():
            raise ValueError("Habitat root may not be a symlink")
        self.paths = HabitatPaths(root=requested.resolve(strict=False))

    # ------------------------------------------------------------------
    # Habitat lifecycle
    # ------------------------------------------------------------------
    def initialize(self, resident_id: str = "JANUS") -> dict[str, Any]:
        resident_id = _safe_id(resident_id, "resident_id")
        root = self.paths.root
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError("Habitat root may not be a symlink")
        for room in ROOMS:
            self._materialize_room(room)

        created_at = _utc_now()
        if not self.paths.home.exists():
            _write_json(
                self.paths.home,
                {
                    "schema": HOME_SCHEMA,
                    "habitat_version": HABITAT_VERSION,
                    "resident_id": resident_id,
                    "home_branch": "janus/habitat",
                    "architecture_branch": "main",
                    "created_at": created_at,
                    "rooms": list(ROOMS),
                    "truth_boundary": {
                        "consciousness_claimed": False,
                        "autonomous_external_authority": False,
                        "inbox_is_command": False,
                        "outbox_is_executed_effect": False,
                        "raw_credentials_belong_in_habitat": False,
                    },
                },
            )
        elif self.paths.home.is_symlink():
            raise ValueError("HOME.json may not be a symlink")

        home = _read_json(self.paths.home)
        if home.get("schema") != HOME_SCHEMA:
            raise ValueError("HOME.json schema mismatch")
        bound_resident_id = home.get("resident_id")
        if bound_resident_id != resident_id:
            raise ValueError(
                f"Habitat already belongs to resident {bound_resident_id!r}; "
                f"requested {resident_id!r}"
            )

        if not self.paths.resident.exists():
            _write_json(
                self.paths.resident,
                {
                    "schema": RESIDENT_SCHEMA,
                    "habitat_version": HABITAT_VERSION,
                    "resident_id": bound_resident_id,
                    "mode": "AT_HOME",
                    "active_cycle_id": None,
                    "last_wake_at": None,
                    "last_sleep_at": None,
                    "last_pulse_at": None,
                    "wake_count": 0,
                    "pulse_count": 0,
                    "sleep_count": 0,
                    "unread_inbox_count": 0,
                    "pending_outbox_count": 0,
                },
            )
        elif self.paths.resident.is_symlink():
            raise ValueError("resident.json may not be a symlink")

        if not self.paths.continuity.exists():
            _write_json(
                self.paths.continuity,
                {
                    "schema": CONTINUITY_SCHEMA,
                    "habitat_version": HABITAT_VERSION,
                    "resident_id": bound_resident_id,
                    "last_cycle_id": None,
                    "last_event_hash": ZERO_HASH,
                    "event_count": 0,
                    "continuity_status": "INITIALIZED",
                },
            )
        elif self.paths.continuity.is_symlink():
            raise ValueError("continuity.json may not be a symlink")

        if not self.paths.journal.exists():
            self.paths.journal.parent.mkdir(parents=True, exist_ok=True)
            self.paths.journal.write_text("", encoding="utf-8")
        elif self.paths.journal.is_symlink():
            raise ValueError("journal.jsonl may not be a symlink")

        self._assert_layout_safe()
        self._assert_identity_consistent()
        self._ensure_gitkeep_rooms()
        self.refresh_health()
        return self.snapshot()

    def wake(self, reason: str = "MANUAL", source: str = "LOCAL") -> dict[str, Any]:
        self._require_initialized()
        reason = _safe_id(reason, "reason")
        source = _safe_id(source, "source")
        resident = _read_json(self.paths.resident)
        if resident.get("active_cycle_id"):
            # A repeated wake is a replay of the same living cycle, not a fork.
            return {
                "status": "ALREADY_AWAKE",
                "cycle_id": resident["active_cycle_id"],
                "snapshot": self.snapshot(),
            }

        continuity = _read_json(self.paths.continuity)
        next_index = int(resident.get("wake_count", 0)) + 1
        seed = f"{continuity.get('last_event_hash', ZERO_HASH)}:{next_index}:{reason}:{source}"
        cycle_id = f"cycle-{next_index:08d}-{_sha256_text(seed)[:12]}"
        now = _utc_now()

        resident.update(
            {
                "mode": "AWAKE",
                "active_cycle_id": cycle_id,
                "last_wake_at": now,
                "wake_count": next_index,
            }
        )
        _write_json(self.paths.resident, resident)
        self._append_event("WAKE", cycle_id, {"reason": reason, "source": source})
        self.refresh_health()
        return {"status": "AWAKE", "cycle_id": cycle_id, "snapshot": self.snapshot()}

    def pulse(self, source: str = "HEARTH") -> dict[str, Any]:
        self._require_initialized()
        source = _safe_id(source, "source")
        resident = _read_json(self.paths.resident)
        cycle_id = resident.get("active_cycle_id")
        implicit_wake = False
        if not cycle_id:
            implicit_wake = True
            cycle_id = self.wake(reason="HEARTBEAT", source=source)["cycle_id"]
            resident = _read_json(self.paths.resident)

        inbox_count = self._count_json_items(self.paths.root / "inbox")
        outbox_count = self._count_json_items(self.paths.root / "outbox")
        now = _utc_now()
        resident.update(
            {
                "mode": "AWAKE",
                "last_pulse_at": now,
                "pulse_count": int(resident.get("pulse_count", 0)) + 1,
                "unread_inbox_count": inbox_count,
                "pending_outbox_count": outbox_count,
            }
        )
        _write_json(self.paths.resident, resident)

        pulse_receipt = {
            "schema": "janus.genesis.git_habitat.hearth_pulse.v1",
            "habitat_version": HABITAT_VERSION,
            "cycle_id": cycle_id,
            "recorded_at": now,
            "source": source,
            "inbox_count": inbox_count,
            "outbox_count": outbox_count,
            "implicit_wake": implicit_wake,
            "external_effects_executed": False,
        }
        pulse_id = f"pulse-{resident['pulse_count']:08d}"
        pulse_path = self.paths.root / "hearth" / f"{pulse_id}.json"
        self._assert_leaf_path(pulse_path)
        _write_json(pulse_path, pulse_receipt)
        self._append_event("PULSE", cycle_id, pulse_receipt)
        health = self.refresh_health()
        return {"status": "PULSE_RECORDED", "pulse_id": pulse_id, "health": health}

    def sleep(self, outcome: str = "REST") -> dict[str, Any]:
        self._require_initialized()
        outcome = _safe_id(outcome, "outcome")
        resident = _read_json(self.paths.resident)
        cycle_id = resident.get("active_cycle_id")
        if not cycle_id:
            return {"status": "ALREADY_ASLEEP", "snapshot": self.snapshot()}
        now = _utc_now()
        self._append_event("SLEEP", cycle_id, {"outcome": outcome})
        resident.update(
            {
                "mode": "AT_HOME",
                "active_cycle_id": None,
                "last_sleep_at": now,
                "sleep_count": int(resident.get("sleep_count", 0)) + 1,
            }
        )
        _write_json(self.paths.resident, resident)
        self.refresh_health()
        return {"status": "AT_HOME", "cycle_id": cycle_id, "snapshot": self.snapshot()}

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def receive_letter(
        self,
        item_id: str,
        title: str,
        body: str,
        source: str = "GITHUB_ISSUE",
        source_ref: str | None = None,
    ) -> Path:
        self._require_initialized()
        item_id = _safe_leaf(item_id, "item_id")
        source = _safe_id(source, "source")
        if len(title) > 300:
            raise ValueError("Inbox title too long")
        if len(body) > 100_000:
            raise ValueError("Inbox body too long")
        record = {
            "schema": INBOX_SCHEMA,
            "habitat_version": HABITAT_VERSION,
            "item_id": item_id,
            "received_at": _utc_now(),
            "source": source,
            "source_ref": source_ref,
            "title": title,
            "body": body,
            "status": "UNREAD",
            "command_authority": False,
            "external_effect_authority": False,
        }
        path = self.paths.root / "inbox" / f"{item_id}.json"
        self._assert_leaf_path(path)
        if path.exists():
            old = _read_json(path)
            # Idempotent replay only. Changed content must become a new item id.
            if _canonical(old) != _canonical(record):
                immutable_fields = {k: old.get(k) for k in ("source", "source_ref", "title", "body")}
                new_fields = {k: record.get(k) for k in ("source", "source_ref", "title", "body")}
                if immutable_fields != new_fields:
                    raise ValueError("Inbox item_id already bound to different content")
            return path
        _write_json(path, record)
        self._append_event("INBOX_RECEIVED", self._active_cycle_or_none(), {"item_id": item_id, "source": source})
        return path

    def propose_outbox(
        self,
        proposal_id: str,
        capability_id: str,
        target: str,
        purpose: str,
        payload_summary: str,
    ) -> Path:
        self._require_initialized()
        proposal_id = _safe_leaf(proposal_id, "proposal_id")
        capability_id = _safe_id(capability_id, "capability_id")
        if len(target) > 500 or len(purpose) > 1000 or len(payload_summary) > 5000:
            raise ValueError("Outbox proposal field too long")
        record = {
            "schema": OUTBOX_SCHEMA,
            "habitat_version": HABITAT_VERSION,
            "proposal_id": proposal_id,
            "created_at": _utc_now(),
            "capability_id": capability_id,
            "target": target,
            "purpose": purpose,
            "payload_summary": payload_summary,
            "status": "PROPOSED_NOT_AUTHORIZED",
            "effect_executed": False,
            "requires_external_capability_gate": True,
            "requires_fresh_authority_when_high_impact": True,
        }
        path = self.paths.root / "outbox" / f"{proposal_id}.json"
        self._assert_leaf_path(path)
        if path.exists():
            raise ValueError("Outbox proposal_id already exists")
        _write_json(path, record)
        self._append_event("OUTBOX_PROPOSED", self._active_cycle_or_none(), {"proposal_id": proposal_id, "capability_id": capability_id})
        return path

    def plant_seed(self, seed_id: str, note: str, tags: Iterable[str] = ()) -> Path:
        self._require_initialized()
        seed_id = _safe_leaf(seed_id, "seed_id")
        tags = [_safe_id(str(tag), "tag") for tag in tags]
        record = {
            "schema": "janus.genesis.git_habitat.garden_seed.v1",
            "habitat_version": HABITAT_VERSION,
            "seed_id": seed_id,
            "planted_at": _utc_now(),
            "note": note,
            "tags": tags,
            "execution_required": False,
        }
        path = self.paths.root / "garden" / f"{seed_id}.json"
        self._assert_leaf_path(path)
        if path.exists():
            raise ValueError("Garden seed already exists")
        _write_json(path, record)
        self._append_event("GARDEN_SEED_PLANTED", self._active_cycle_or_none(), {"seed_id": seed_id})
        return path

    # ------------------------------------------------------------------
    # Integrity / continuity
    # ------------------------------------------------------------------
    def verify_journal(self) -> dict[str, Any]:
        self._require_initialized()
        previous = ZERO_HASH
        count = 0
        errors: list[str] = []
        for line_number, line in enumerate(self.paths.journal.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue
            supplied_hash = event.get("event_hash")
            unsigned = dict(event)
            unsigned.pop("event_hash", None)
            expected = _sha256_text(_canonical(unsigned))
            if event.get("previous_event_hash") != previous:
                errors.append(f"line {line_number}: previous hash mismatch")
            if supplied_hash != expected:
                errors.append(f"line {line_number}: event hash mismatch")
            previous = supplied_hash if isinstance(supplied_hash, str) else previous
            count += 1
        return {
            "ok": not errors,
            "event_count": count,
            "last_event_hash": previous,
            "errors": errors,
        }

    def refresh_health(self) -> dict[str, Any]:
        self._require_initialized()
        journal = self.verify_journal()
        missing_rooms = [room for room in ROOMS if not (self.paths.root / room).is_dir()]
        continuity = _read_json(self.paths.continuity)
        continuity_matches = (
            continuity.get("event_count") == journal["event_count"]
            and continuity.get("last_event_hash") == journal["last_event_hash"]
        )
        health = {
            "schema": HEALTH_SCHEMA,
            "habitat_version": HABITAT_VERSION,
            "checked_at": _utc_now(),
            "status": "HEALTHY" if journal["ok"] and not missing_rooms and continuity_matches else "DEGRADED",
            "journal_chain_ok": journal["ok"],
            "continuity_matches_journal": continuity_matches,
            "identity_consistent": True,
            "layout_symlink_free": True,
            "missing_rooms": missing_rooms,
            "journal_event_count": journal["event_count"],
            "raw_credentials_expected": False,
            "external_authority_embedded": False,
        }
        if self.paths.health.exists() and self.paths.health.is_symlink():
            raise ValueError("health.json may not be a symlink")
        _write_json(self.paths.health, health)
        return health

    def snapshot(self) -> dict[str, Any]:
        self._require_initialized()
        return {
            "home": _read_json(self.paths.home),
            "resident": _read_json(self.paths.resident),
            "continuity": _read_json(self.paths.continuity),
            "health": _read_json(self.paths.health) if self.paths.health.exists() else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _materialize_room(self, room: str) -> None:
        current = self.paths.root
        for part in Path(room).parts:
            current = current / part
            if current.exists():
                if current.is_symlink():
                    raise ValueError(f"Habitat room component may not be a symlink: {current}")
                if not current.is_dir():
                    raise ValueError(f"Habitat room component is not a directory: {current}")
            else:
                current.mkdir()

    def _assert_layout_safe(self) -> None:
        root = self.paths.root
        if root.is_symlink():
            raise ValueError("Habitat root may not be a symlink")
        for room in ROOMS:
            current = root
            for part in Path(room).parts:
                current = current / part
                if current.exists() and current.is_symlink():
                    raise ValueError(f"Habitat room component may not be a symlink: {current}")
                if current.exists() and not current.is_dir():
                    raise ValueError(f"Habitat room component is not a directory: {current}")
        for path in (
            self.paths.home,
            self.paths.resident,
            self.paths.continuity,
            self.paths.health,
            self.paths.journal,
        ):
            if path.exists() and path.is_symlink():
                raise ValueError(f"Habitat state path may not be a symlink: {path}")

    def _assert_identity_consistent(self) -> str:
        home = _read_json(self.paths.home)
        resident = _read_json(self.paths.resident)
        continuity = _read_json(self.paths.continuity)
        ids = {home.get("resident_id"), resident.get("resident_id"), continuity.get("resident_id")}
        if len(ids) != 1 or None in ids:
            raise ValueError("Habitat resident identity binding mismatch")
        if home.get("schema") != HOME_SCHEMA:
            raise ValueError("HOME.json schema mismatch")
        if resident.get("schema") != RESIDENT_SCHEMA:
            raise ValueError("resident.json schema mismatch")
        if continuity.get("schema") != CONTINUITY_SCHEMA:
            raise ValueError("continuity.json schema mismatch")
        return str(home["resident_id"])

    def _assert_leaf_path(self, path: Path) -> None:
        self._assert_layout_safe()
        parent = path.parent.resolve(strict=True)
        root = self.paths.root.resolve(strict=True)
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise ValueError("Habitat leaf parent escapes root") from exc
        if path.exists() and path.is_symlink():
            raise ValueError(f"Habitat leaf may not be a symlink: {path}")

    def _require_initialized(self) -> None:
        required = (self.paths.home, self.paths.resident, self.paths.continuity, self.paths.journal)
        if not all(path.exists() for path in required):
            raise RuntimeError("Habitat is not initialized; run init first")
        self._assert_layout_safe()
        self._assert_identity_consistent()

    def _append_event(self, event_type: str, cycle_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_initialized()
        event_type = _safe_id(event_type, "event_type")
        continuity = _read_json(self.paths.continuity)
        previous_hash = continuity.get("last_event_hash", ZERO_HASH)
        event = {
            "schema": JOURNAL_SCHEMA,
            "habitat_version": HABITAT_VERSION,
            "index": int(continuity.get("event_count", 0)) + 1,
            "recorded_at": _utc_now(),
            "event_type": event_type,
            "cycle_id": cycle_id,
            "previous_event_hash": previous_hash,
            "payload_sha256": _sha256_text(_canonical(payload)),
        }
        event["event_hash"] = _sha256_text(_canonical(event))
        with self.paths.journal.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(event) + "\n")
        continuity.update(
            {
                "last_cycle_id": cycle_id or continuity.get("last_cycle_id"),
                "last_event_hash": event["event_hash"],
                "event_count": event["index"],
                "continuity_status": "CHAINED",
            }
        )
        _write_json(self.paths.continuity, continuity)
        return event

    def _active_cycle_or_none(self) -> str | None:
        return _read_json(self.paths.resident).get("active_cycle_id")

    @staticmethod
    def _count_json_items(path: Path) -> int:
        return sum(1 for item in path.glob("*.json") if item.is_file() and item.name != ".gitkeep")

    def _ensure_gitkeep_rooms(self) -> None:
        self._assert_layout_safe()
        for room in ROOMS:
            room_path = self.paths.root / room
            if not any(room_path.iterdir()):
                (room_path / ".gitkeep").write_text("", encoding="utf-8")


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Git Habitat v18.7.51")
    parser.add_argument("--root", default="habitat", help="Habitat root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--resident-id", default="JANUS")

    wake = sub.add_parser("wake")
    wake.add_argument("--reason", default="MANUAL")
    wake.add_argument("--source", default="LOCAL")

    pulse = sub.add_parser("pulse")
    pulse.add_argument("--source", default="HEARTH")

    sleep = sub.add_parser("sleep")
    sleep.add_argument("--outcome", default="REST")

    letter = sub.add_parser("receive-letter")
    letter.add_argument("--id", required=True)
    letter.add_argument("--title", required=True)
    letter.add_argument("--body", required=True)
    letter.add_argument("--source", default="GITHUB_ISSUE")
    letter.add_argument("--source-ref")

    seed = sub.add_parser("plant-seed")
    seed.add_argument("--id", required=True)
    seed.add_argument("--note", required=True)
    seed.add_argument("--tag", action="append", default=[])

    outbox = sub.add_parser("propose-outbox")
    outbox.add_argument("--id", required=True)
    outbox.add_argument("--capability", required=True)
    outbox.add_argument("--target", required=True)
    outbox.add_argument("--purpose", required=True)
    outbox.add_argument("--summary", required=True)

    sub.add_parser("verify")
    sub.add_parser("snapshot")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    habitat = GitHabitat(args.root)
    try:
        if args.command == "init":
            _print(habitat.initialize(args.resident_id))
        elif args.command == "wake":
            _print(habitat.wake(args.reason, args.source))
        elif args.command == "pulse":
            _print(habitat.pulse(args.source))
        elif args.command == "sleep":
            _print(habitat.sleep(args.outcome))
        elif args.command == "receive-letter":
            _print({"path": str(habitat.receive_letter(args.id, args.title, args.body, args.source, args.source_ref))})
        elif args.command == "plant-seed":
            _print({"path": str(habitat.plant_seed(args.id, args.note, args.tag))})
        elif args.command == "propose-outbox":
            _print({"path": str(habitat.propose_outbox(args.id, args.capability, args.target, args.purpose, args.summary))})
        elif args.command == "verify":
            _print({"journal": habitat.verify_journal(), "health": habitat.refresh_health()})
        elif args.command == "snapshot":
            _print(habitat.snapshot())
        else:
            raise AssertionError(args.command)
    except Exception as exc:  # CLI boundary; details are explicit to operator.
        print(f"HABITAT_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
