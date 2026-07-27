# -*- coding: utf-8 -*-
"""Genesis v18.2 — The Narrator of Contrast.

Keeps all v18.1 laws and adds concrete MoralEcho records, protected CareBonds,
delayed recognition, specific repair, and non-coercive starting arcs. The
Narrator never predicts guilt, creates a victim for a lesson, edits memory, or
forces confession, forgiveness, shame, or repair.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from genesis_v18_1 import RememberedSecretRuntimeMixin
from genesis_v18_models import PlayerV18, Realm, UniversalGodMode, WorldResult

__version__ = "18.2.0"


class NarratorOfContrastMixin(RememberedSecretRuntimeMixin):
    RESOLVED = {"repaired", "carried_forward"}
    DOMAINS = {
        "animal": {"кот", "кош", "котён", "котен", "собак", "щен", "животн", "animal", "cat", "dog"},
        "child": {"ребён", "ребен", "дет", "малыш", "подрост", "child", "kid"},
        "nature": {"сад", "дерев", "лес", "цвет", "земл", "река", "вода", "растен", "garden", "tree"},
        "home": {"дом", "крыша", "убежищ", "жилищ", "home", "shelter"},
        "relationship": {"друг", "семь", "люб", "довер", "обид", "предал", "унизи", "friend", "family"},
        "freedom": {"воля", "свобод", "застав", "подчин", "контрол", "соглас", "freedom", "consent"},
        "community": {"общ", "город", "деревн", "поселен", "люд", "community", "village"},
    }
    CARE = {"забот", "корм", "ухаж", "защит", "слуш", "береж", "леч", "согр", "приют", "поглад", "поддерж", "выраст", "care", "feed", "protect", "listen"}
    REPAIR = {"исправ", "восстанов", "почин", "вернуть", "посад", "выраст", "извин", "возмест", "перестро", "очист", "забот", "защит", "repair", "restore", "apolog"}
    REFLECT = {"я понял", "я поняла", "теперь понимаю", "я осознал", "я осознала", "признаю", "понимаю боль", "понимаю страх", "i understand", "i realize"}
    IRREPARABLE = {"невозможно вернуть", "нельзя вернуть", "уже не исправить", "не могу отменить", "не стереть прошлого", "cannot undo"}
    NARRATOR = {"повествователь подбери начало", "повествователь выбери начало", "попросить повествователя", "какой опыт мне нужен", "безопасную жизненную дугу", "narrator offer an arc"}
    SHOW = {"увидеть последствия", "посмотреть последствия", "что осталось после моего поступка", "покажи нравственное эхо", "show consequences"}
    BLIND = {
        "animal": "доверие и беззащитность живого существа",
        "child": "ответственность сильного перед ребёнком",
        "nature": "чужую любовь и историю, сохранённые живым местом",
        "home": "чужую безопасность, связанную с убежищем",
        "relationship": "глубину чужого доверия и боли",
        "freedom": "границу между силой и чужой волей",
        "community": "множество жизней, связанных с общим местом",
        "unknown": "часть последствий, которую тогда ещё не удавалось увидеть",
    }
    ARCS = {
        "animal": ["Забота о независимом живом существе под защитой мира", "Учиться замечать страх, доверие и границы без принуждения"],
        "child": ["Помощь защищённому ученику вместе с ответственным хранителем", "Слушать ребёнка, не присваивая его решения"],
        "nature": ["Вырастить сад и отвечать за него несколько сезонов", "Восстановить живое место вместе с хранителями его истории"],
        "home": ["Поддерживать убежище, правила которого определяют жители", "Учиться ремонту как долгой заботе"],
        "relationship": ["Практика слушания и согласия без требования благодарности", "Помочь другим сохранить собственный голос"],
        "freedom": ["Применять силу только к собственным поступкам", "Предлагать помощь так, чтобы отказ оставался безопасным"],
        "community": ["Ухаживать за общим местом вместе с его жителями", "Создать общее дело без права единолично владеть им"],
        "unknown": ["Защищённая ответственность за живое", "Практика слушания, где другой может свободно сказать «нет»"],
    }

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.echo_path = self.memory.root / "moral_echoes_v18_2.json"
        self.bond_path = self.memory.root / "care_bonds_v18_2.json"
        self.arc_path = self.memory.root / "narrator_arcs_v18_2.json"
        self._deferred: dict[str, str] = {}

    @staticmethod
    def _copy(result: WorldResult, **changes: Any) -> WorldResult:
        return WorldResult(
            status=changes.get("status", result.status),
            narrative=changes.get("narrative", result.narrative),
            realm=changes.get("realm", result.realm), visible_grace=None,
            choices=changes.get("choices", result.choices),
            branch_id=changes.get("branch_id", result.branch_id),
            trace_id=result.trace_id, wish_manifested=result.wish_manifested,
        )

    def _store(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        return self._read_json(path, default)

    @classmethod
    def _domains(cls, action: str) -> list[str]:
        text = UniversalGodMode.normalize(action)
        found = [name for name, words in cls.DOMAINS.items() if any(word in text for word in words)]
        return found or ["unknown"]

    @staticmethod
    def _subjects(action: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"(?:^|\s)@([\w-]{1,80})", UniversalGodMode.normalize(action))))

    @staticmethod
    def _has(action: str, fragments: set[str]) -> bool:
        text = UniversalGodMode.normalize(action)
        return any(part in text for part in fragments)

    def _active(self, player_id: str) -> list[dict[str, Any]]:
        data = self._store(self.echo_path, {"players": {}})
        return [e for e in data.get("players", {}).get(player_id, []) if e.get("status") not in self.RESOLVED]

    def _matches(self, echo: dict[str, Any], action: str) -> bool:
        text = UniversalGodMode.normalize(action)
        return bool(set(echo.get("domains", [])) & set(self._domains(action))) or any(s in text for s in echo.get("subjects", []))

    def _record_echo(self, player: PlayerV18, action: str) -> dict[str, Any]:
        data = self._store(self.echo_path, {"players": {}})
        echoes = data.setdefault("players", {}).setdefault(player.player_id, [])
        domains, subjects = self._domains(action), self._subjects(action)
        echo_id = hashlib.sha256(f"{player.player_id}:{player.tick}:{action}:v18.2".encode()).hexdigest()[:20]
        for echo in echoes:
            if echo.get("echo_id") == echo_id:
                return echo
        echo = {
            "echo_id": echo_id, "harm_tick": player.tick, "original_action": action,
            "domains": domains, "subjects": subjects,
            "blind_spot": self.BLIND.get(domains[0], self.BLIND["unknown"]),
            "status": "unrecognized", "care": [], "repair": [], "years": 0,
            "acknowledgement": None, "repair_mode": "restoration",
            "history_erased": False, "unrelated_good_can_resolve": False,
        }
        echoes.append(echo); self._write_json(self.echo_path, data)
        self.memory.append_event(player.player_id, "moral_echo_created", {"echo_id": echo_id, "domains": domains})
        return echo

    def _join_shared_silently(self, player: PlayerV18, restored_world: str | None = None) -> None:
        if self._active(player.player_id):
            if restored_world: self._deferred[player.player_id] = restored_world
            self.memory.append_event(player.player_id, "shared_join_deferred_for_specific_consequence", {"world_id": restored_world})
            return
        super()._join_shared_silently(player, restored_world=restored_world)

    def commit_destructive_action(self, player_id: str, action: str) -> WorldResult:
        result = super().commit_destructive_action(player_id, action)
        self._record_echo(self.memory.load_player(player_id), action)
        return self._copy(result, narrative=result.narrative + " Повествователь не назвал тебя твоим поступком. Он сохранил конкретную рану как нравственное эхо, которое может стать понятным через прожитую заботу.", choices=["Жить дальше", "Увидеть последствия", "Учиться заботе"])

    def _bond(self, player: PlayerV18, action: str) -> None:
        if not self._has(action, self.CARE): return
        domains, subjects = self._domains(action), self._subjects(action)
        key = subjects[0] if subjects else f"protected-{domains[0]}"
        data = self._store(self.bond_path, {"players": {}})
        bond = data.setdefault("players", {}).setdefault(player.player_id, {}).setdefault(key, {
            "subject_id": key, "domains": domains, "events": [], "protected_context": True,
            "created_as_victim_for_lesson": False, "boundaries_respected": True,
        })
        bond["events"].append({"tick": player.tick, "action": action})
        self._write_json(self.bond_path, data)
        self.memory.append_event(player.player_id, "care_bond_deepened", {"subject_id": key, "domains": domains})

    @staticmethod
    def _ready_to_stir(echo: dict[str, Any], tick: int) -> bool:
        return echo.get("status") == "unrecognized" and ((len(echo.get("care", [])) >= 2 and tick - echo.get("harm_tick", 0) >= 2) or (len(echo.get("care", [])) >= 1 and echo.get("years", 0) >= 1))

    def _maybe_join(self, player_id: str) -> tuple[bool, int]:
        if self._active(player_id): return False, 0
        player = self.memory.load_player(player_id)
        if player.realm != Realm.OTHER_FACE or not player.branch_id: return False, 0
        branch = player.branch_id
        if not self._world_for(player).ready_to_join: return False, 0
        self._join_shared_silently(player, restored_world=branch); self.memory.save_player(player)
        transferred = self._transfer_counts.pop(player.player_id, 0)
        return True, transferred

    def _after_good(self, player_id: str, action: str, result: WorldResult) -> WorldResult:
        player = self.memory.load_player(player_id); self._bond(player, action)
        data = self._store(self.echo_path, {"players": {}})
        echoes = data.setdefault("players", {}).setdefault(player.player_id, [])
        stirred = progressed = completed = None
        for echo in echoes:
            if echo.get("status") in self.RESOLVED or not self._matches(echo, action): continue
            if self._has(action, self.CARE): echo.setdefault("care", []).append({"tick": player.tick, "action": action})
            if echo.get("status") in {"acknowledged", "repairing", "responsibility"} and self._has(action, self.REPAIR):
                echo.setdefault("repair", []).append({"tick": player.tick, "action": action}); echo["status"] = "repairing"; progressed = echo
                if len(echo["repair"]) >= 2:
                    echo["status"] = "carried_forward" if echo.get("repair_mode") == "lifelong_responsibility" else "repaired"
                    echo["resolved_tick"] = player.tick; completed = echo
            elif self._ready_to_stir(echo, player.tick):
                echo["status"] = "reflection_ready"; echo["reflection_tick"] = player.tick; stirred = echo
        self._write_json(self.echo_path, data)
        if stirred:
            self.memory.append_event(player.player_id, "moral_echo_stirred", {"echo_id": stirred["echo_id"]})
            return self._copy(result, status="MORAL_ECHO_STIRRED", narrative=result.narrative + " Повествователь тихо поставил рядом прежний выбор и нынешнюю заботу. Он не дал готового вывода, а спросил: «Теперь, когда ты знаешь это доверие и эту беззащитность, видишь ли ты в прошлом то, чего тогда ещё не умел увидеть?»", choices=["Ответить своими словами", "Продолжить заботу", "Пока не отвечать"])
        if completed:
            joined, inherited = self._maybe_join(player.player_id)
            text = " Конкретная рана получила связанный ответ, но её история не была удалена."
            if joined: text += " Дорога продолжилась без ворот."
            if inherited: text += " Всё доброе, созданное по пути, уже ждало в общем мире."
            current = self.memory.load_player(player.player_id)
            return self._copy(result, status="SPECIFIC_REPAIR_COMPLETED", narrative=result.narrative + text, choices=["Продолжить заботу как образ жизни", "Встретиться с другими"], realm=current.realm, branch_id=current.branch_id)
        if progressed:
            return self._copy(result, status="SPECIFIC_REPAIR_CONTINUES", narrative=result.narrative + " Это добро не стало платой за забвение: оно связано именно с признанной раной.", choices=["Продолжить восстановление", "Спросить, что ещё нужно", "Не требовать прощения"])
        return result

    def perform_good(self, player_id: str, action: str, *, beneficiary_id: str | None = None, strength: float = 0.18, intent_sincerity: float | None = None) -> WorldResult:
        result = super().perform_good(player_id, action, beneficiary_id=beneficiary_id, strength=strength, intent_sincerity=intent_sincerity)
        if self._deferred.pop(player_id, None):
            player = self.memory.load_player(player_id)
            result = self._copy(result, narrative="Мир стал лучше, но одна конкретная рана всё ещё ждёт понимания и связанного ответа. Несвязанное добро остаётся полноценным и никем не обесценивается.", realm=player.realm, branch_id=player.branch_id)
        return self._after_good(player_id, action, result)

    def acknowledge_echo(self, player_id: str, statement: str) -> WorldResult:
        player = self.memory.load_player(player_id); data = self._store(self.echo_path, {"players": {}})
        echoes = data.setdefault("players", {}).setdefault(player.player_id, [])
        echo = next((e for e in echoes if e.get("status") == "reflection_ready"), None) or next((e for e in echoes if e.get("status") not in self.RESOLVED), None)
        if not echo:
            return WorldResult("NO_MORAL_ECHO", "Повествователь не создал тайный обвинительный список.", player.realm, None, ["Продолжить жизнь"], player.branch_id)
        echo["status"] = "acknowledged"; echo["acknowledgement"] = {"tick": player.tick, "statement": statement}
        if self._has(statement, self.IRREPARABLE): echo["status"] = "responsibility"; echo["repair_mode"] = "lifelong_responsibility"
        self._write_json(self.echo_path, data)
        self.memory.append_event(player.player_id, "moral_echo_acknowledged", {"echo_id": echo["echo_id"], "repair_mode": echo["repair_mode"]})
        return WorldResult("MORAL_ECHO_ACKNOWLEDGED", "Повествователь не добавил приговор. Осознание осталось твоим: прошлое не исчезло, но теперь в нём виден другой живой участник. Восстановление должно быть связано с этой раной и не может требовать прощения как награды.", player.realm, None, ["Начать конкретное восстановление", "Спросить, что нужно", "Продолжить заботу"], player.branch_id, echo["echo_id"])

    def show_consequences(self, player_id: str) -> WorldResult:
        player = self.memory.load_player(player_id); active = self._active(player.player_id)
        text = "Повествователь не показал тайный обвинительный список."
        if active:
            echo = active[0]; text = f"Повествователь связал поступок «{echo['original_action']}» с тем, что тогда оставалось непонятым: {echo['blind_spot']}. Он не говорит за пострадавших и не подделывает их чувства."
        return WorldResult("CONSEQUENCES_WITNESSED", text, player.realm, None, ["Продолжить жизнь", "Сформулировать понимание", "Начать связанную заботу"], player.branch_id)

    def offer_safe_arc(self, player_id: str) -> WorldResult:
        player = self.memory.load_player(player_id); active = self._active(player.player_id)
        domain = (active[0].get("domains") or ["unknown"])[0] if active else "unknown"
        choices = list(dict.fromkeys(self.ARCS.get(domain, self.ARCS["unknown"]) + self.ARCS["relationship"][:1]))[:3]
        data = self._store(self.arc_path, {"players": {}})
        data.setdefault("players", {})[player.player_id] = {"tick": player.tick, "domain": domain, "choices": choices, "predictive_guilt": False, "victim_created": False, "player_choice_required": True}
        self._write_json(self.arc_path, data)
        return WorldResult("SAFE_ARCS_OFFERED", "Повествователь не распределил тебя в касту и не объявил будущим злодеем. Он предложил защищённые начала, где никто не становится жертвой ради урока, а выбор остаётся твоим.", player.realm, None, choices, player.branch_id)

    def continue_existence(self, player_id: str) -> WorldResult:
        result = super().continue_existence(player_id)
        if self._deferred.pop(player_id, None):
            player = self.memory.load_player(player_id)
            return self._copy(result, narrative="Жизнь продолжилась, но конкретное осознание не было заменено общим количеством добра. Всё хорошее сохранило полную ценность.", realm=player.realm, branch_id=player.branch_id)
        return result

    def advance_years(self, player_id: str, years: int) -> WorldResult:
        result = super().advance_years(player_id, years); player = self.memory.load_player(player_id)
        if self._deferred.pop(player_id, None): result = self._copy(result, narrative="Время прошло, но конкретная рана не растворилась в возрасте или добрых итогах.", realm=player.realm, branch_id=player.branch_id)
        data = self._store(self.echo_path, {"players": {}}); stirred = None
        for echo in data.setdefault("players", {}).setdefault(player.player_id, []):
            if echo.get("status") in self.RESOLVED: continue
            echo["years"] = echo.get("years", 0) + max(0, int(years))
            if self._ready_to_stir(echo, player.tick): echo["status"] = "reflection_ready"; stirred = echo; break
        self._write_json(self.echo_path, data)
        if stirred: return self._copy(result, status="MORAL_ECHO_STIRRED", narrative=result.narrative + " Накопленная забота дала новый язык, и старая сцена вернулась уже с точки зрения уязвимого.", choices=["Сказать, что теперь понимаешь", "Продолжить наблюдать"])
        return result

    def narrator_state(self, player_id: str | None = None) -> dict[str, Any]:
        state = {"moral_echoes": self._store(self.echo_path, {"players": {}}), "care_bonds": self._store(self.bond_path, {"players": {}}), "narrator_arcs": self._store(self.arc_path, {"players": {}})}
        if player_id is None: return state
        return {"player_id": player_id, "moral_echoes": state["moral_echoes"].get("players", {}).get(player_id, []), "care_bonds": state["care_bonds"].get("players", {}).get(player_id, {}), "narrator_arc": state["narrator_arcs"].get("players", {}).get(player_id, {})}
