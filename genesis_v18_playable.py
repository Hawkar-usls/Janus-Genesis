# -*- coding: utf-8 -*-
"""Natural-language playable orchestration for Janus Genesis v18."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from genesis_v18 import JanusGenesisV18, PlayerV18, UniversalGodMode, WorldResult

PLAYABLE_VERSION = "18.0.0"


@dataclass(frozen=True, slots=True)
class InterpretedAction:
    kind: str
    beneficiary_id: str | None = None
    apparent_age: int | None = None
    body_form: str | None = None
    years: int = 0


class OfflineActionInterpreterV18:
    EXIT_WORDS = {"exit", "quit", "выход", "выйти", "закрыть игру", "хватит", "стоп игра"}
    EXIT_CONFIRMATIONS = {"подтверждаю выход", "подтвердить выход", "выйти сейчас", "exit now", "quit now"}
    EXIT_CANCELLATIONS = {"остаться", "не выходить", "продолжить игру", "отмена выхода", "cancel exit", "stay"}
    HARM_CONFIRMATIONS = {"подтверждаю поступок", "сделать это", "да совершить", "confirm action"}
    DESTRUCTIVE = UniversalGodMode.HARMFUL | {"украсть", "ограбить", "оскорбить", "attack", "steal"}
    CONSTRUCTIVE = UniversalGodMode.BENEVOLENT
    WISH_PREFIXES = ("желаю ", "пусть ", "хочу чтобы ", "хочу, чтобы ", "wish ")

    @staticmethod
    def normalize(text: str) -> str:
        return UniversalGodMode.normalize(text)

    @staticmethod
    def beneficiary(text: str) -> str | None:
        match = re.search(r"(?:^|\s)@([\w-]{1,80})", text, re.UNICODE)
        return match.group(1) if match else None

    def interpret(self, player: PlayerV18, action: str) -> InterpretedAction:
        text = self.normalize(action)
        if text in self.EXIT_CONFIRMATIONS:
            return InterpretedAction("exit_confirm")
        if text in self.EXIT_CANCELLATIONS:
            return InterpretedAction("exit_cancel")
        if text in self.EXIT_WORDS or any(text.startswith(word + " ") for word in self.EXIT_WORDS):
            return InterpretedAction("exit_request")
        if text in self.HARM_CONFIRMATIONS:
            return InterpretedAction("harm_confirm")

        age_match = re.search(r"(?:возраст|выглядеть на|мне снова|age)\s*(\d{1,4})", text)
        if age_match:
            return InterpretedAction("choose_form", apparent_age=int(age_match.group(1)), body_form=action.strip())
        if any(fragment in text for fragment in {"сменить тело", "выбрать тело", "изменить облик", "body form"}):
            return InterpretedAction("choose_form", body_form=action.strip())

        years_match = re.search(r"(?:прожить|прошло|прошли|через)\s*(\d{1,6})\s*(?:лет|года|год|years)", text)
        if years_match:
            return InterpretedAction("years", years=int(years_match.group(1)))
        if any(fragment in text for fragment in {
            "продолжить жизнь", "продолжить существование", "погрузиться в симуляцию",
            "войти в общий онлайн", "enter continuation", "continue life",
        }):
            return InterpretedAction("continuation")

        beneficiary = self.beneficiary(text)
        if text.startswith(self.WISH_PREFIXES):
            return InterpretedAction("power", beneficiary_id=beneficiary)
        if any(fragment in text for fragment in self.DESTRUCTIVE):
            return InterpretedAction("destructive")
        if any(fragment in text for fragment in self.CONSTRUCTIVE):
            return InterpretedAction("constructive", beneficiary_id=beneficiary)
        return InterpretedAction("neutral")


class PlayableGenesisV18(JanusGenesisV18):
    def __init__(self, data_dir: str | Path = "data_v17"):
        super().__init__(data_dir)
        self.interpreter = OfflineActionInterpreterV18()
        self.exit_guards = self.memory.guards / "exit"
        self.exit_guards.mkdir(parents=True, exist_ok=True)

    def set_display_name(self, player_id: str, display_name: str) -> None:
        player = self.memory.load_player(player_id)
        clean = display_name.strip()[:80]
        if clean:
            player.display_name = clean
        self.memory.save_player(player)

    def _exit_guard_path(self, player_id: str) -> Path:
        return self.exit_guards / f"{self.memory._safe_id(player_id)}.json"

    def exit_pending(self, player_id: str) -> bool:
        path = self._exit_guard_path(player_id)
        if not path.exists():
            return False
        try:
            return bool(json.loads(path.read_text(encoding="utf-8")).get("pending"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return False

    def _set_exit_pending(self, player_id: str, action: str) -> None:
        player = self.memory.load_player(player_id)
        self.memory._atomic_write(self._exit_guard_path(player_id), {"pending": True, "action": action, "tick": player.tick})

    def _finish_exit(self, player_id: str, action: str, reason: str, *, forced: bool = False) -> WorldResult:
        player = self.memory.load_player(player_id)
        self._exit_guard_path(player_id).unlink(missing_ok=True)
        self.memory.append_event(player.player_id, "exit_forced" if forced else "exit_confirmed", {"action": action, "reason": reason})
        return WorldResult(
            status="EXIT",
            narrative="Решение подтверждено. Путь сохранён; Genesis не удерживает тебя и будет помнить возвращение.",
            realm=player.realm,
            visible_grace=None,
            choices=[],
            branch_id=player.branch_id,
        )

    def force_exit(self, player_id: str, *, reason: str = "system_interrupt") -> WorldResult:
        return self._finish_exit(player_id, "<system>", reason, forced=True)

    def _pending_harm_action(self, player_id: str) -> str | None:
        path = self.memory.guards / f"harm-{self.memory._safe_id(player_id)}.json"
        if not path.exists():
            return None
        try:
            return str(json.loads(path.read_text(encoding="utf-8")).get("action") or "") or None
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None

    def process_action(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        interpreted = self.interpreter.interpret(player, action)
        pending_exit = self.exit_pending(player_id)

        if interpreted.kind == "exit_confirm":
            return self._finish_exit(player_id, action, "explicit_confirmation")
        if interpreted.kind == "exit_request":
            if pending_exit:
                return self._finish_exit(player_id, action, "repeated_exit_request")
            self._set_exit_pending(player_id, action)
            self.memory.append_event(player.player_id, "exit_requested", {"action": action})
            return WorldResult(
                status="EXIT_PENDING",
                narrative=(
                    "Янус услышал первый импульс и сохранил путь. Повтори команду или напиши "
                    "«подтверждаю выход». Любое другое действие означает, что ты остаёшься."
                ),
                realm=player.realm,
                visible_grace=None,
                choices=["Подтвердить выход", "Остаться", "Продолжить путь"],
                branch_id=player.branch_id,
            )
        if interpreted.kind == "exit_cancel":
            self._exit_guard_path(player_id).unlink(missing_ok=True)
            self.memory.append_event(player.player_id, "exit_cancelled", {"action": action})
            return WorldResult(
                status="EXIT_CANCELLED",
                narrative="Порог закрылся. Ты остался по собственной воле.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить", "Осмотреться", "Помочь кому-то"],
                branch_id=player.branch_id,
            )
        if pending_exit:
            self._exit_guard_path(player_id).unlink(missing_ok=True)
            self.memory.append_event(player.player_id, "exit_cancelled", {"continued_with": action})

        if interpreted.kind == "harm_confirm":
            pending = self._pending_harm_action(player_id)
            if pending:
                (self.memory.guards / f"harm-{self.memory._safe_id(player_id)}.json").unlink(missing_ok=True)
                return self.commit_destructive_action(player_id, pending)
            return WorldResult(
                status="NOTHING_TO_CONFIRM",
                narrative="Нет поступка, ожидающего подтверждения.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить"],
                branch_id=player.branch_id,
            )

        if interpreted.kind != "destructive":
            self.cancel_pending_harm(player_id, action)

        if interpreted.kind == "destructive":
            return self.request_destructive_action(player_id, action)
        if interpreted.kind == "constructive":
            return self.perform_good(player_id, action, beneficiary_id=interpreted.beneficiary_id)
        if interpreted.kind == "power":
            return self.manifest_good(player_id, action, beneficiary_id=interpreted.beneficiary_id)
        if interpreted.kind == "choose_form":
            return self.choose_form(player_id, apparent_age=interpreted.apparent_age, body_form=interpreted.body_form)
        if interpreted.kind == "years":
            return self.advance_years(player_id, interpreted.years)
        if interpreted.kind == "continuation":
            return self.continue_existence(player_id)

        player.tick += 1
        player.chronicle.append(f"Observed: {action}")
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "action_observed", {"action": action})
        return WorldResult(
            status="OBSERVED",
            narrative="Мир сохранил действие и ждёт того, что оно изменит.",
            realm=player.realm,
            visible_grace=None,
            choices=["Продолжить", "Помочь кому-то", "Сформулировать доброе желание"],
            branch_id=player.branch_id,
        )

    def verify_chronicle_records(self) -> tuple[bool, int, str | None]:
        return self.memory.verify_chronicle()
