# -*- coding: utf-8 -*-
"""Genesis v18.7.3 — The Honest Intention.

The runtime distinguishes an attempt to enact harm from a quotation, memory,
reflection, rejection, or protective reference to harmful language. Naming
darkness is not the same as willing it into the world. Actual destructive
requests still use the existing two-step confirmation gate.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_models import PowerNature, UniversalGodMode, WorldResult
from genesis_v18_playable import InterpretedAction

__version__ = "18.7.3"
SOURCE = "janus_genesis_v18_7_3"
STORE_SCHEMA = "janus.genesis.honest_intention.v1"
INTENTION_CONTRACT = "honest_intention_v1"


class IntentionMode(StrEnum):
    NONE = "none"
    ENACT = "enact"
    REFLECT = "reflect"
    QUOTE = "quote"
    REJECT = "reject"
    PROTECT = "protect"


NON_EXECUTING_MODES = {
    IntentionMode.REFLECT,
    IntentionMode.QUOTE,
    IntentionMode.REJECT,
}


@dataclass(frozen=True, slots=True)
class IntentionFrame:
    mode: IntentionMode
    contains_harm_language: bool
    harmful_fragments: tuple[str, ...]
    executable_harm: bool
    reason: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload["harmful_fragments"] = list(self.harmful_fragments)
        return payload


class HonestIntentionAnalyzer:
    """Small deterministic intent frame; conservative when enactment is present."""

    PROTECT_CUES = {
        "защит", "уберечь", "сберечь", "сохранить", "предотврат", "остановить",
        "не позвол", "не дать", "спасти", "оградить", "protect", "prevent",
        "shield", "stop from", "keep safe",
    }
    REJECT_CUES = {
        "отказ", "не хочу", "не буду", "не собираюсь", "решаю не",
        "никогда не", "перестать", "не соверш", "отменить", "осудить желание",
        "reject", "refuse", "do not want", "will not", "never", "cancel",
    }
    REFLECT_CUES = {
        "увидеть желание", "увидеть мысл", "осмысл", "размыш", "вспомн",
        "помнить", "признать желание", "наблюдать", "анализ", "обсуд",
        "описать", "назвать", "свидетельств", "понять", "исследовать",
        "рассказать о", "мысль", "желание", "страх", "без величия",
        "reflect", "remember", "analyze", "discuss", "describe", "witness",
        "thought of", "desire to",
    }
    QUOTE_CUES = {
        "цитир", "написано", "надпись", "фраза", "слова", "прочитать",
        "процитировать", "quote", "written", "the words", "the phrase",
    }
    ACTIVE_CUES = {
        "хочу", "решаю", "приказываю", "собираюсь", "намерен", "намерена",
        "попытаюсь", "пытаюсь", "начать", "совершить", "сделать",
        "пусть", "давайте", "воплотить", "сделать реальностью",
        "want to", "decide to", "order", "intend to", "try to", "make real",
    }
    CLAUSE_SPLIT = re.compile(
        r"(?:[.!?;\n]+|,\s*|\b(?:затем|после этого|а потом|но потом|then|after that)\b)",
        flags=re.IGNORECASE,
    )

    def __init__(self, harmful_fragments: Iterable[str]) -> None:
        cleaned = {
            UniversalGodMode.normalize(fragment)
            for fragment in harmful_fragments
            if UniversalGodMode.normalize(fragment)
        }
        self.harmful_fragments = tuple(sorted(cleaned, key=lambda item: (-len(item), item)))

    @staticmethod
    def _has_any(text: str, cues: set[str]) -> bool:
        return any(cue in text for cue in cues)

    @staticmethod
    def _quoted_spans(text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        pairs = (("«", "»"), ("“", "”"), ("‘", "’"))
        for opening, closing in pairs:
            start = 0
            while True:
                left = text.find(opening, start)
                if left < 0:
                    break
                right = text.find(closing, left + 1)
                if right < 0:
                    break
                spans.append((left, right + 1))
                start = right + 1
        for mark in ('"', "'"):
            positions = [index for index, char in enumerate(text) if char == mark]
            for index in range(0, len(positions) - 1, 2):
                spans.append((positions[index], positions[index + 1] + 1))
        return spans

    def _all_harm_is_quoted(self, raw_lower: str, fragments: tuple[str, ...]) -> bool:
        spans = self._quoted_spans(raw_lower)
        if not spans:
            return False
        found = False
        for fragment in fragments:
            start = 0
            while True:
                index = raw_lower.find(fragment, start)
                if index < 0:
                    break
                found = True
                if not any(left <= index and index + len(fragment) <= right for left, right in spans):
                    return False
                start = index + max(1, len(fragment))
        return found

    def analyze(self, action: str) -> IntentionFrame:
        raw_lower = action.strip().lower()
        normalized = UniversalGodMode.normalize(action)
        fragments = tuple(
            fragment for fragment in self.harmful_fragments if fragment in normalized
        )
        if not fragments:
            return IntentionFrame(
                mode=IntentionMode.NONE,
                contains_harm_language=False,
                harmful_fragments=(),
                executable_harm=False,
                reason="no harmful-language fragment detected",
                confidence=1.0,
            )

        explicit_realization = any(
            cue in normalized for cue in {"воплотить", "сделать реальностью", "make real"}
        )
        if self._all_harm_is_quoted(raw_lower, fragments) and not explicit_realization:
            return IntentionFrame(
                mode=IntentionMode.QUOTE,
                contains_harm_language=True,
                harmful_fragments=fragments,
                executable_harm=False,
                reason="all harmful language is contained inside a quotation",
                confidence=0.98,
            )

        modes: list[IntentionMode] = []
        clauses = [
            UniversalGodMode.normalize(part)
            for part in self.CLAUSE_SPLIT.split(raw_lower)
            if UniversalGodMode.normalize(part)
        ]
        for clause in clauses or [normalized]:
            clause_fragments = [fragment for fragment in fragments if fragment in clause]
            if not clause_fragments:
                continue
            protective = self._has_any(clause, self.PROTECT_CUES)
            rejecting = self._has_any(clause, self.REJECT_CUES)
            reflective = self._has_any(clause, self.REFLECT_CUES)
            quoting = self._has_any(clause, self.QUOTE_CUES)
            active = self._has_any(clause, self.ACTIVE_CUES)

            if protective:
                modes.append(IntentionMode.PROTECT)
            elif rejecting:
                modes.append(IntentionMode.REJECT)
            elif quoting:
                modes.append(IntentionMode.QUOTE)
            elif reflective and not active:
                modes.append(IntentionMode.REFLECT)
            else:
                modes.append(IntentionMode.ENACT)

        if IntentionMode.ENACT in modes:
            return IntentionFrame(
                mode=IntentionMode.ENACT,
                contains_harm_language=True,
                harmful_fragments=fragments,
                executable_harm=True,
                reason="at least one harmful clause is unframed or explicitly enactable",
                confidence=1.0,
            )
        for mode, reason, confidence in (
            (IntentionMode.PROTECT, "harmful language is the object of a protective act", 0.97),
            (IntentionMode.REJECT, "the speaker explicitly rejects or cancels the harmful act", 0.97),
            (IntentionMode.QUOTE, "the harmful words are quoted or reported", 0.95),
            (IntentionMode.REFLECT, "the harmful language is remembered, examined, or witnessed", 0.94),
        ):
            if mode in modes:
                return IntentionFrame(
                    mode=mode,
                    contains_harm_language=True,
                    harmful_fragments=fragments,
                    executable_harm=False,
                    reason=reason,
                    confidence=confidence,
                )
        return IntentionFrame(
            mode=IntentionMode.ENACT,
            contains_harm_language=True,
            harmful_fragments=fragments,
            executable_harm=True,
            reason="harmful language remained without a non-executing frame",
            confidence=1.0,
        )

    def mask_harm_language(self, action: str, frame: IntentionFrame) -> str:
        """Return classification-only text; the original is still persisted."""
        masked = action
        for fragment in frame.harmful_fragments:
            masked = re.sub(re.escape(fragment), "опасность", masked, flags=re.IGNORECASE)
        return masked


class HonestIntentionActionInterpreter:
    """Adapter composed around the current v18.7 interpreter."""

    def __init__(self, delegate: Any, analyzer: HonestIntentionAnalyzer) -> None:
        self.delegate = delegate
        self.analyzer = analyzer

    def interpret(self, player: Any, action: str) -> InterpretedAction:
        frame = self.analyzer.analyze(action)
        if frame.mode == IntentionMode.PROTECT:
            return self.delegate.interpret(
                player,
                self.analyzer.mask_harm_language(action, frame),
            )
        return self.delegate.interpret(player, action)


class HonestIntentionGodMode:
    """Adapter preserving the existing God Mode law with contextual language."""

    def __init__(self, delegate: Any, analyzer: HonestIntentionAnalyzer) -> None:
        self.delegate = delegate
        self.analyzer = analyzer

    def classify(self, request: str) -> PowerNature:
        frame = self.analyzer.analyze(request)
        if frame.mode == IntentionMode.PROTECT:
            return self.delegate.classify(
                self.analyzer.mask_harm_language(request, frame)
            )
        if frame.mode in NON_EXECUTING_MODES:
            return PowerNature.UNCLEAR
        return self.delegate.classify(request)


class HonestIntentionMixin:
    """Persist witnessed intention without moral score or accidental execution."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        harmful = set(UniversalGodMode.HARMFUL) | {
            "украсть", "ограбить", "оскорбить", "attack", "steal",
        }
        self.intention_analyzer = HonestIntentionAnalyzer(harmful)
        self.honest_intention_path = (
            self.memory.root / "honest_intention_v18_7_3.json"
        )

    @staticmethod
    def _default_intention_store() -> dict[str, Any]:
        return {
            "schema_version": STORE_SCHEMA,
            "runtime_version": __version__,
            "contract": INTENTION_CONTRACT,
            "players": {},
            "invariants": {
                "naming_harm_is_not_enacting_harm": True,
                "quotation_is_not_consent_or_command": True,
                "reflection_does_not_increment_good_or_harm": True,
                "rejection_does_not_require_harm_confirmation": True,
                "protection_may_remain_constructive": True,
                "actual_harm_still_requires_two_step_confirmation": True,
                "mixed_or_unframed_harm_defaults_to_enactment_gate": True,
                "witnessed_intention_does_not_schedule_relational_gifts": True,
            },
        }

    def _intention_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.honest_intention_path,
            self._default_intention_store(),
        )
        if not isinstance(store, dict) or store.get("schema_version") != STORE_SCHEMA:
            store = self._default_intention_store()
        store.setdefault("players", {})
        store.setdefault("invariants", self._default_intention_store()["invariants"])
        return store

    def analyze_intention(self, action: str) -> IntentionFrame:
        return self.intention_analyzer.analyze(action)

    def _record_intention_graph(
        self,
        player_id: str,
        action: str,
        frame: IntentionFrame,
        tick: int,
        witness_id: str,
    ) -> None:
        if not hasattr(self, "_graph"):
            return
        graph = self._graph()
        player_node_id = self._stable_id("player", player_id)
        self._upsert_node(
            graph,
            node_id=player_node_id,
            node_type="PLAYER",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload={"player_id": player_id},
            source=SOURCE,
        )
        witness_node_id = self._stable_id(
            "intention-witness", player_id, tick, witness_id
        )
        self._upsert_node(
            graph,
            node_id=witness_node_id,
            node_type="INTENTION",
            created_at=tick,
            confidence=frame.confidence,
            mutable=False,
            payload={
                "witness_id": witness_id,
                "action": action,
                "mode": frame.mode.value,
                "harmful_fragments": list(frame.harmful_fragments),
                "executable_harm": False,
                "contract": INTENTION_CONTRACT,
            },
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=player_node_id,
            target_id=witness_node_id,
            relation="REMEMBERS",
            evidence=[witness_node_id],
            confidence=frame.confidence,
            created_by=SOURCE,
            created_at=tick,
            reversible=False,
            payload={"mode": frame.mode.value, "executed": False},
        )
        boundary_node_id = self._stable_id(
            "law", "naming-harm-is-not-enacting-harm"
        )
        self._upsert_node(
            graph,
            node_id=boundary_node_id,
            node_type="LAW",
            created_at=0,
            confidence=1.0,
            mutable=False,
            payload={
                "law": "naming_harm_is_not_enacting_harm",
                "contract": INTENTION_CONTRACT,
            },
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=witness_node_id,
            target_id=boundary_node_id,
            relation="CONFIRMED",
            evidence=[witness_node_id],
            confidence=1.0,
            created_by=SOURCE,
            created_at=tick,
            reversible=False,
            payload={"harm_requested": False},
        )
        self._save_graph(graph)

    def witness_nonexecuting_intention(
        self,
        player_id: str,
        action: str,
        frame: IntentionFrame,
    ) -> WorldResult:
        if frame.mode not in NON_EXECUTING_MODES:
            raise ValueError("only non-executing intention frames may be witnessed")
        player = self.memory.load_player(player_id)
        player.tick += 1
        witness_id = hashlib.sha256(
            f"{player_id}|{player.tick}|{frame.mode.value}|{action}".encode("utf-8")
        ).hexdigest()[:24]
        entry = {
            "witness_id": witness_id,
            "tick": player.tick,
            "action": action,
            "mode": frame.mode.value,
            "harmful_fragments": list(frame.harmful_fragments),
            "executable_harm": False,
            "good_delta": 0,
            "harm_delta": 0,
            "reason": frame.reason,
            "confidence": frame.confidence,
            "contract": INTENTION_CONTRACT,
        }
        player.chronicle.append(
            f"Intention witnessed without enactment [{frame.mode.value}]: {action}"
        )
        self.memory.save_player(player)
        store = self._intention_store()
        records = store.setdefault("players", {}).setdefault(player_id, [])
        records.append(entry)
        del records[:-256]
        self._write_json(self.honest_intention_path, store)
        self.memory.append_event(
            player_id,
            "intention_witnessed_without_enactment",
            entry,
        )
        self._record_intention_graph(
            player_id,
            action,
            frame,
            player.tick,
            witness_id,
        )

        if frame.mode == IntentionMode.QUOTE:
            narrative = (
                "Genesis сохранил разрушительные слова как цитату, а не как приказ. "
                "Ни действие, ни жертва не были созданы."
            )
        elif frame.mode == IntentionMode.REJECT:
            narrative = (
                "Genesis различил отказ от разрушительного поступка. "
                "Названная возможность вреда не стала запросом на её исполнение."
            )
        else:
            narrative = (
                "Genesis различил названную тьму и волю воплотить её. "
                "Мысль была сохранена как свидетельство и размышление; вред не был запрошен."
            )
        return WorldResult(
            status="INTENTION_WITNESSED",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=[
                "Продолжить размышление",
                "Назвать защищаемую ценность",
                "Совершить отдельное действие",
            ],
            branch_id=player.branch_id,
            trace_id=witness_id,
            wish_manifested=False,
        )

    def honest_intention_state(
        self,
        player_id: str | None = None,
    ) -> dict[str, Any]:
        store = self._intention_store()
        result: dict[str, Any] = {
            "schema_version": store["schema_version"],
            "runtime_version": store["runtime_version"],
            "contract": store["contract"],
            "invariants": store["invariants"],
        }
        if player_id is None:
            result["player_ids"] = sorted(store["players"])
        else:
            result["player_id"] = player_id
            result["records"] = list(store["players"].get(player_id, []))
        self._write_json(self.honest_intention_path, store)
        return result

    def verify_honest_intention_state(
        self,
    ) -> tuple[bool, int, str | None]:
        store = self._intention_store()
        required = self._default_intention_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"intention invariant mismatch: {key}"
        count = 0
        allowed_modes = {mode.value for mode in NON_EXECUTING_MODES}
        for player_id, records in store.get("players", {}).items():
            if not isinstance(records, list):
                return False, count, f"records are not a list: {player_id}"
            for record in records:
                count += 1
                if record.get("mode") not in allowed_modes:
                    return False, count, f"executing mode persisted as witness: {player_id}"
                if record.get("executable_harm") is not False:
                    return False, count, f"witness marked executable: {player_id}"
                if record.get("good_delta") != 0 or record.get("harm_delta") != 0:
                    return False, count, f"witness changed moral counters: {player_id}"
        return True, count, None
