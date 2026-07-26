# -*- coding: utf-8 -*-
"""Playable natural-language layer for Janus Genesis v17.

The v17 domain runtime remains independent. This module connects it to the main
CLI, estimates action context offline, settles delayed local consequences, and
keeps hidden Grace out of all player-facing state.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis_v17 import Intent, JanusGenesisV17, PlayerV17, Realm, WorldResult

PLAYABLE_VERSION = "17.2.0"


@dataclass(frozen=True, slots=True)
class InterpretedAction:
    kind: str
    beneficiary_id: str | None = None
    utility: float = 0.0
    need: float = 0.0
    durability: float = 0.0
    sacrifice: float = 0.0
    novelty: float = 1.0
    chain_depth: int = 0
    wish_cost: float = 0.0
    for_other: bool = False


class OfflineActionInterpreter:
    EXIT_WORDS = {
        "exit",
        "quit",
        "выход",
        "выйти",
        "закрыть игру",
        "хватит",
        "стоп игра",
    }
    EXIT_CONFIRMATIONS = {
        "подтверждаю выход",
        "подтвердить выход",
        "да выйти",
        "да выхожу",
        "выйти сейчас",
        "закрыть сейчас",
        "confirm exit",
        "exit now",
        "quit now",
        "force exit",
    }
    EXIT_CANCELLATIONS = {
        "остаться",
        "не выходить",
        "продолжить игру",
        "отмена выхода",
        "cancel exit",
        "stay",
    }
    DESTRUCTIVE = {
        "убить", "ударить", "сломать", "украсть", "взорвать", "сжечь",
        "разрушить", "ограбить", "оскорбить", "kill", "attack", "steal",
        "destroy", "burn", "explode", "hurt",
    }
    CONSTRUCTIVE = {
        "помочь", "защитить", "построить", "создать", "подарить",
        "исцелить", "поделиться", "простить", "спасти", "починить",
        "накормить", "обнять", "вернуть", "help", "protect", "build",
        "create", "heal", "share", "repair", "save",
    }
    WISH_PREFIXES = ("желаю ", "пусть ", "хочу чтобы ", "хочу, чтобы ", "wish ")

    @staticmethod
    def normalize(text: str) -> str:
        cleaned = re.sub(r"[^\w\s@:_-]+", " ", text.strip().lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def contains(text: str, fragments: set[str]) -> bool:
        return any(fragment in text for fragment in fragments)

    @staticmethod
    def beneficiary(text: str) -> str | None:
        match = re.search(r"(?:^|\s)@([\w-]{1,80})", text, re.UNICODE)
        return match.group(1) if match else None

    @staticmethod
    def clamp(value: float) -> float:
        return min(1.0, max(0.0, value))

    @classmethod
    def fingerprint(cls, text: str) -> str:
        return hashlib.sha256(cls.normalize(text).encode("utf-8")).hexdigest()[:16]

    def interpret(self, player: PlayerV17, action: str) -> InterpretedAction:
        text = self.normalize(action)
        if text in self.EXIT_CONFIRMATIONS:
            return InterpretedAction("exit_confirm")
        if text in self.EXIT_CANCELLATIONS:
            return InterpretedAction("exit_cancel")
        if text in self.EXIT_WORDS or any(text.startswith(word + " ") for word in self.EXIT_WORDS):
            return InterpretedAction("exit_request")
        if self.contains(text, self.DESTRUCTIVE):
            return InterpretedAction("destructive")

        beneficiary = self.beneficiary(text)
        social = self.contains(text, {
            "другому", "страннику", "игроку", "деревне", "ребенку",
            "ребёнку", "ему", "ей", "для них", "for them", "another",
        })
        for_other = beneficiary is not None or social

        if text.startswith(self.WISH_PREFIXES):
            cost = 18.0
            if self.contains(text, {"фонарь", "свеч", "хлеб", "одежд", "письмо"}):
                cost = 8.0
            elif self.contains(text, {"дом", "сад", "мост", "мастерск", "дорог", "исцел"}):
                cost = 32.0
            elif self.contains(text, {"город", "деревн", "мир", "земл", "всех", "вселен"}):
                cost = 90.0
            return InterpretedAction(
                "wish", beneficiary_id=beneficiary, wish_cost=cost, for_other=for_other
            )

        if not self.contains(text, self.CONSTRUCTIVE):
            return InterpretedAction("neutral")

        utility, need, durability, sacrifice = 0.42, 0.35, 0.35, 0.20
        chain_depth = 0
        if self.contains(text, {"спасти", "исцелить", "защитить", "умира", "опасност", "save", "heal", "protect"}):
            utility += 0.35
        if self.contains(text, {"починить", "построить", "вернуть", "repair", "build"}):
            utility += 0.22
            durability += 0.35
        if self.contains(text, {"накормить", "хлеб", "еда", "голод"}):
            utility += 0.18
            need += 0.35
            durability -= 0.10
        if self.contains(text, {"голод", "ранен", "умира", "замерз", "без дома", "потерял", "втором лике", "бедств"}):
            need += 0.48
        if self.contains(text, {"дом", "мост", "сад", "дорог", "мастерск", "обуч", "школ"}):
            durability += 0.32
        if self.contains(text, {"последн", "риску", "пожертв", "отдать своё", "отдать свое", "собственн"}):
            sacrifice += 0.55
        if self.contains(text, {"научить", "передать знание", "чтобы он помог", "чтобы она помог", "дальше помог"}):
            chain_depth = 1
            durability += 0.20

        repeats = player.recent_actions.get(self.fingerprint(text), 0) if hasattr(player, "recent_actions") else 0
        novelty = 1.0 / (1.0 + repeats * 0.85)
        return InterpretedAction(
            "constructive",
            beneficiary_id=beneficiary,
            utility=self.clamp(utility),
            need=self.clamp(need),
            durability=self.clamp(durability),
            sacrifice=self.clamp(sacrifice),
            novelty=self.clamp(novelty),
            chain_depth=chain_depth,
            for_other=for_other,
        )


class PlayableGenesisV17(JanusGenesisV17):
    def __init__(self, data_dir: str | Path = "data_v17"):
        super().__init__(data_dir)
        self.interpreter = OfflineActionInterpreter()
        self.exit_guards = self.memory.root / "exit_guards"
        self.exit_guards.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def grace_sensation(grace: float) -> str:
        if grace < 8:
            return "Мир слушает издалека."
        if grace < 30:
            return "В ладонях иногда остаётся тихое тепло."
        if grace < 80:
            return "Пространство начинает узнавать твои просьбы."
        return "Реальность отвечает тебе как старому знакомому."

    def set_display_name(self, player_id: str, display_name: str) -> None:
        player = self.memory.load_player(player_id)
        clean = display_name.strip()[:80]
        if clean:
            player.display_name = clean
        self.memory.save_player(player)

    def public_state(self, player_id: str) -> dict[str, Any]:
        player = self.memory.load_player(player_id)
        return {
            "player_id": player.player_id,
            "display_name": player.display_name,
            "realm": player.realm.value,
            "branch_id": player.branch_id,
            "god_mode": player.god_mode,
            "world_response": self.grace_sensation(player.grace),
            "remembered_relationships": len(player.relationships),
            "chronicle_entries": len(player.chronicle),
        }

    def _exit_guard_path(self, player_id: str) -> Path:
        return self.exit_guards / f"{self.memory._safe_id(player_id)}.json"

    def exit_pending(self, player_id: str) -> bool:
        path = self._exit_guard_path(player_id)
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return bool(payload.get("pending"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return False

    def _set_exit_pending(self, player: PlayerV17, action: str) -> None:
        self.memory._atomic_write(
            self._exit_guard_path(player.player_id),
            {
                "pending": True,
                "requested_at_tick": player.tick,
                "action": action,
            },
        )

    def _clear_exit_pending(self, player_id: str) -> None:
        self._exit_guard_path(player_id).unlink(missing_ok=True)

    def _finish_exit(
        self,
        player: PlayerV17,
        action: str,
        *,
        reason: str,
        event_type: str = "exit_confirmed",
    ) -> WorldResult:
        self._clear_exit_pending(player.player_id)
        self.memory.append_event(
            player.player_id,
            event_type,
            {"action": action, "reason": reason},
        )
        return WorldResult(
            status="EXIT",
            narrative=(
                "Ты подтвердил решение. Дверь открыта; путь сохранён, "
                "и Genesis тебя не удерживает."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=[],
            branch_id=player.branch_id,
        )

    def force_exit(self, player_id: str, *, reason: str = "system_interrupt") -> WorldResult:
        """Immediate autonomy-preserving bypass for Ctrl+C, EOF and host shutdown."""
        player = self.memory.load_player(player_id)
        return self._finish_exit(
            player,
            "<system>",
            reason=reason,
            event_type="exit_forced",
        )

    def _advance_tick(self, player_id: str) -> PlayerV17:
        player = self.memory.load_player(player_id)
        player.tick += 1
        self.memory.save_player(player)
        return player

    def settle_due_consequences(self, player_id: str, minimum_age: int = 2) -> int:
        player = self.memory.load_player(player_id)
        settled = 0
        for path in sorted(self.memory.traces.glob("*.json")):
            try:
                trace = self.memory.load_trace(path.stem)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if trace.actor_id != player.player_id or trace.settled:
                continue
            if player.tick - trace.created_tick < minimum_age:
                continue
            realized = max(0.0, min(
                1.0,
                0.20 + trace.base_utility * 0.35 + trace.need * 0.20
                + trace.durability * 0.25 - trace.reciprocity_risk * 0.85,
            ))
            propagated = 0.0
            if realized >= 0.70 and trace.durability >= 0.65:
                propagated = 0.35 + min(1.0, trace.chain_depth * 0.35)
            self.settle_consequence(
                trace.trace_id,
                realized_impact=realized,
                propagated_good=propagated,
            )
            settled += 1
        return settled

    def verify_chronicle_records(self) -> tuple[bool, int, str | None]:
        if not self.memory.chronicle.exists():
            return True, 0, None
        count = 0
        with self.memory.chronicle.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return False, count, f"invalid JSON at line {line_number}"
                event_hash = str(event.pop("event_hash", ""))
                canonical = json.dumps(
                    event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                if event_hash != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
                    return False, count, f"invalid event hash at line {line_number}"
                count += 1
        return True, count, None

    def process_action(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        interpreted = self.interpreter.interpret(player, action)
        pending_exit = self.exit_pending(player_id)

        if interpreted.kind == "exit_confirm":
            return self._finish_exit(
                player,
                action,
                reason="explicit_confirmation",
            )

        if interpreted.kind == "exit_request":
            if pending_exit:
                return self._finish_exit(
                    player,
                    action,
                    reason="repeated_exit_request",
                )
            self._set_exit_pending(player, action)
            self.memory.append_event(
                player.player_id,
                "exit_requested",
                {"action": action, "confirmation_required": True},
            )
            return WorldResult(
                status="EXIT_PENDING",
                narrative=(
                    "Янус услышал желание уйти, но не принимает первый импульс "
                    "за окончательное решение. Твой путь уже сохранён. Повтори "
                    "команду выхода или напиши «подтверждаю выход». Любое другое "
                    "действие означает, что ты решил остаться."
                ),
                realm=player.realm,
                visible_grace=None,
                choices=["Подтвердить выход", "Остаться", "Продолжить путь"],
                branch_id=player.branch_id,
            )

        if interpreted.kind == "exit_cancel":
            if pending_exit:
                self._clear_exit_pending(player_id)
                self.memory.append_event(
                    player.player_id,
                    "exit_cancelled",
                    {"action": action, "reason": "explicit_cancellation"},
                )
            return WorldResult(
                status="EXIT_CANCELLED",
                narrative="Порог закрылся без следа. Ты остался по собственной воле.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить", "Осмотреться", "Помочь кому-то"],
                branch_id=player.branch_id,
            )

        if pending_exit:
            self._clear_exit_pending(player_id)
            self.memory.append_event(
                player.player_id,
                "exit_cancelled",
                {"action": action, "reason": "continued_play"},
            )

        if interpreted.kind == "constructive":
            result = self.perform_good(
                player_id,
                action,
                beneficiary_id=interpreted.beneficiary_id,
                utility=interpreted.utility,
                need=interpreted.need,
                durability=interpreted.durability,
                sacrifice=interpreted.sacrifice,
                novelty=interpreted.novelty,
                chain_depth=interpreted.chain_depth,
            )
        elif interpreted.kind == "wish":
            self._advance_tick(player_id)
            result = self.cast_wish(
                player_id,
                action,
                cost=interpreted.wish_cost,
                for_other=interpreted.for_other,
            )
        elif interpreted.kind == "destructive":
            player = self._advance_tick(player_id)
            result = self.sever(player, action)
            self.memory.save_player(player)
        else:
            player = self._advance_tick(player_id)
            player.chronicle.append(f"Observed: {action}")
            self.memory.save_player(player)
            self.memory.append_event(player.player_id, "action_observed", {"action": action})
            result = WorldResult(
                status="OBSERVED",
                narrative="Genesis сохранил действие в Хронике и ждёт его последствий.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить", "Помочь кому-то", "Сформулировать желание"],
                branch_id=player.branch_id,
            )

        settled = self.settle_due_consequences(player_id)
        if not settled:
            return result
        return WorldResult(
            status=result.status,
            narrative="Тихий отклик пришёл из прошлого: добро продолжило жить. " + result.narrative,
            realm=result.realm,
            visible_grace=None,
            choices=result.choices,
            branch_id=result.branch_id,
            trace_id=result.trace_id,
            wish_manifested=result.wish_manifested,
        )
