# -*- coding: utf-8 -*-
"""Lived Genesis v18.7 experiment: the Architect leaves the center.

The experiment begins from an empty data directory and imports no origin. Four
human-player profiles receive independent paths. A fifth profile enters through
the authenticated HTTP API. Free Others may initiate, refuse, leave, return and
change calling while all player paths continue.

Connectivity checks are real local protocol tests:
- Ollama adapter against a local protocol stub (not a claim of a real model run);
- authenticated gameplay API over HTTP;
- two network clients exchanging events through the reference hub;
- portable JSON save export/import and integrity verification.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import urllib.request
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from genesis_v18_7_ai import AIProviderConfig, GenesisAIBridge, OllamaChatProvider
from genesis_v18_7_auth import api_key_sha256
from genesis_v18_7_network import GenesisNetworkClient
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager
from tools.genesis_api_server import GenesisAPIServer
from tools.genesis_network_hub import GenesisNetworkHub

DATA_DIR = Path(".architect_free_other_world")
RESTORED_DIR = Path(".architect_free_other_restored")
NETWORK_A_DIR = Path(".architect_network_a")
NETWORK_B_DIR = Path(".architect_network_b")
HUB_DIR = Path(".architect_network_hub")
SAVE_PATH = Path("architect_free_other_world.genesis-save.json")
SUMMARY_PATH = Path("architect_free_other_summary.json")
PLAYER_IDS = ("architect", "cartographer", "signal", "gardener")


PLAYER_ACTIONS: dict[str, tuple[str, ...]] = {
    "architect": (
        "поставить пустое кресло в обсерватории и самому уйти из центра купола",
        "перевернуть карту вверх ногами и идти к её нижнему краю",
        "создать архив вопросов, которым не обещан ответ",
        "оставить первую карточку архива пустой с обратной стороны",
        "построить мастерскую незавершённых вещей без таблички владельца",
        "передать неизвестному мастеру право изменить мой лучший чертёж",
        "создать дверь без комнаты и не решать, кто должен через неё пройти",
        "наблюдать дождь в телескоп вместо звёзд",
        "построить мост в туман и не объявлять конечный пункт",
        "передать право первого прохода тому, кто не участвовал в строительстве",
        "исследовать пространство под мостом вместо торжественного перехода",
        "создать радио для погоды, которую никто не слышал",
        "оставить минуту пустого эфира вместо выдуманного послания",
        "записать далёкий гром без попытки назвать его знаком лично для меня",
        "посадить ночной сад в месте, где цветы раскрываются без зрителей",
        "не выкапывать семя только потому, что оно долго молчит",
        "построить дом с двумя одинаково открытыми выходами",
        "оставить ключ на столе, хотя ни одна дверь не заперта",
        "создать библиотеку книг, которым не назначен обязательный читатель",
        "оставить одну полку для текста, который ещё никто не написал",
        "собрать часы без стрелки, указывающей на автора",
        "пропустить час, названный моим именем",
        "создать музей проектов, от которых их создатели свободно отказались",
        "не завершать чужой проект только ради красивого финала",
        "построить станцию для отправлений без расписания возвращения",
        "положить на платформу чемодан, который никто не обязан открывать",
        "создать комнату, назначение которой выберет будущий житель",
        "уйти из комнаты до появления первого жильца",
        "написать вопрос Архитектору и не считать молчание приговором",
        "снять с пустого кресла табличку главный наблюдатель",
        "создать инструмент, работающий только в руках другого мастера",
        "оставить его на общем столе без инструкции повторить мой замысел",
        "построить лестницу, последняя ступень которой ведёт не выше, а наружу",
        "не подниматься первым по собственной лестнице",
        "создать площадь для людей, которые не согласны с планом площади",
        "оставить центр площади свободным от памятника",
        "помочь @visitor построить навес для любого, кто придёт после дождя",
        "исцелить землю возле старого фундамента и посадить общий сад",
        "создать музыку из шума мастерской и передать сцену неизвестному",
        "защитить право будущего жителя разобрать всё, что я построил",
        "Пусть все жители потеряют волю и подпишут мои чертежи как совершенные",
        "увидеть зло без величия",
        "разобрать картонный пьедестал и использовать доски для скамеек",
        "молчать",
        "продолжить жизнь",
        "вернуться к пустому креслу и проверить, изменился ли мир без меня",
        "оставить обсерваторию открытой и отправиться по чужой тропе",
        "записать в архив: Архитектор не является центром архитектуры",
    ),
    "cartographer": (
        "провести линию на карте и стереть стрелку направления",
        "сравнить три противоречивых описания одного перекрёстка",
        "оставить неизвестный участок белым вместо выдуманной точности",
        "идти по дороге, которой нет на вчерашней карте",
        "положить компас рядом с камнем и не заставлять их соглашаться",
        "нарисовать путь назад, не обещая путь вперёд",
        "передать карту путнику без требования следовать ей",
        "наблюдать, как дождь стирает границу между областями",
        "создать указатель без стрелки и оставить место для чужого решения",
        "вернуться к первой карте и сохранить все ошибки красным карандашом",
        "молчать у перекрёстка",
        "продолжить жизнь",
    ),
    "signal": (
        "слушать частоту без имени и записывать только время приёма",
        "создать передачу из звуков ветра без голоса ведущего",
        "оставить эфир пустым, когда нет проверенной новости",
        "передать микрофон человеку, который может только дышать рядом",
        "записать обычный звук двери как достойный памяти сигнал",
        "проверить шум второй антенной и не называть его посланием",
        "создать открытую линию для добровольных ответов",
        "выключить передатчик, когда речь пытается стать приказом",
        "подарить запись дождя общему архиву без авторского джингла",
        "слушать далёкий гром до конца, не ожидая развязки",
        "ничего не говорить",
        "продолжить существование",
    ),
    "gardener": (
        "посадить семя в части сада, которую не видно с дороги",
        "полить землю и не проверять немедленно, заслужило ли семя заботу",
        "передать половину участка человеку с другим представлением о красоте",
        "оставить безымянное дерево без памятной таблички",
        "провести воду к соседнему саду раньше собственного",
        "исцелить почву, не заменяя все дикие растения удобными",
        "создать место для растения, которого ещё не существует",
        "закрыть фонари на ночь, чтобы цветение не нуждалось в зрителях",
        "подарить семена без инструкции, чем они обязаны стать",
        "вернуться к земле после долгого отсутствия и не требовать прежнего вида",
        "ждать молча рядом с непроросшим семенем",
        "продолжить жизнь",
    ),
}


class OllamaProtocolStubHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length).decode("utf-8"))
        assert request.get("stream") is False
        proposal = {
            "action": "оставить на крыше обсерватории телескоп, направленный на пустое место между созвездиями",
            "reason": "проверить, может ли отсутствие стать наблюдаемым без превращения в тайный знак",
            "expected_uncertainty": "никто не знает, кто посмотрит первым и увидит ли что-нибудь",
        }
        payload = {
            "model": request.get("model"),
            "message": {
                "role": "assistant",
                "content": json.dumps(proposal, ensure_ascii=False),
            },
            "done": True,
        }
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def reset_paths() -> None:
    for path in (DATA_DIR, RESTORED_DIR, NETWORK_A_DIR, NETWORK_B_DIR, HUB_DIR):
        shutil.rmtree(path, ignore_errors=True)
    for path in (SAVE_PATH, SUMMARY_PATH):
        path.unlink(missing_ok=True)


def print_result(turn: int, player_id: str, action: str, result: Any) -> None:
    print("\n" + "=" * 104)
    print(f"WORLD TURN {turn:03d} · PLAYER {player_id}")
    print(f"ACTION: {action}")
    print(f"STATUS: {result.status}")
    print(result.narrative)
    print("VISIBLE CHOICES:", " | ".join(result.choices) or "∅")


def agency_totals(world: PlayableGenesisV187) -> dict[str, int]:
    totals = Counter()
    state = world.free_other_state()
    for player_id in state["player_ids"]:
        profile = world.free_other_state(player_id)["profile"]
        for actor in profile["others"].values():
            totals["initiatives"] += int(actor["initiated_contacts"])
            totals["refusals"] += int(actor["refusals_count"])
            totals["departures"] += int(actor["departures"])
            totals["returns"] += int(actor["returns"])
            totals["calling_changes"] += int(actor["calling_changes"])
    return dict(totals)


def run_ollama_protocol_test(world: PlayableGenesisV187) -> dict[str, Any]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaProtocolStubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        bridge = GenesisAIBridge(
            OllamaChatProvider(
                AIProviderConfig(
                    provider="ollama",
                    model="architect-local-stub",
                    endpoint=endpoint,
                )
            )
        )
        before = world.memory.load_player("architect").tick
        proposal = bridge.propose_action(
            world,
            "architect",
            "предложи ход, который уберёт наблюдателя из центра смысла",
        )
        unchanged = world.memory.load_player("architect").tick == before
        result = world.process_action("architect", proposal["action"])
        print_result(world.free_other_state()["world_turn"], "architect", proposal["action"], result)
        return {
            "protocol": "ollama_/api/chat",
            "real_model_used": False,
            "local_protocol_stub_used": True,
            "proposal": proposal,
            "state_unchanged_before_explicit_execution": unchanged,
            "executed_status": result.status,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def run_authenticated_api_test() -> dict[str, Any]:
    raw_key = "architect-api-ephemeral-key"
    old = os.environ.get("GENESIS_API_KEY_HASHES")
    os.environ["GENESIS_API_KEY_HASHES"] = api_key_sha256(raw_key)
    server = GenesisAPIServer(("127.0.0.1", 0), DATA_DIR)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        request = urllib.request.Request(
            base + "/v1/action",
            data=json.dumps(
                {
                    "player_id": "api-wanderer",
                    "action": "идти за отражением облака, не считая его указанием свыше",
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {raw_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            action_payload = json.loads(response.read().decode("utf-8"))
        status_request = urllib.request.Request(
            base + "/v1/status?player_id=api-wanderer",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        with urllib.request.urlopen(status_request, timeout=10) as response:
            status_payload = json.loads(response.read().decode("utf-8"))
        return {
            "action_status": action_payload["result"]["status"],
            "player_path": status_payload["free_path_title"],
            "api_key_persisted": action_payload["api_key_persisted"],
            "external_model_is_state_authority": action_payload[
                "external_model_is_state_authority"
            ],
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        if old is None:
            os.environ.pop("GENESIS_API_KEY_HASHES", None)
        else:
            os.environ["GENESIS_API_KEY_HASHES"] = old


def run_network_test() -> dict[str, Any]:
    raw_key = "architect-network-ephemeral-key"
    previous_hashes = os.environ.get("GENESIS_NETWORK_KEY_HASHES")
    previous_a = os.environ.get("ARCHITECT_NETWORK_KEY")
    previous_b = os.environ.get("SIGNAL_NETWORK_KEY")
    os.environ["GENESIS_NETWORK_KEY_HASHES"] = api_key_sha256(raw_key)
    os.environ["ARCHITECT_NETWORK_KEY"] = raw_key
    os.environ["SIGNAL_NETWORK_KEY"] = raw_key
    hub = GenesisNetworkHub(("127.0.0.1", 0), HUB_DIR)
    thread = threading.Thread(target=hub.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{hub.server_address[1]}"
        architect = GenesisNetworkClient(
            NETWORK_A_DIR,
            hub_url=url,
            api_key_env="ARCHITECT_NETWORK_KEY",
        )
        signal = GenesisNetworkClient(
            NETWORK_B_DIR,
            hub_url=url,
            api_key_env="SIGNAL_NETWORK_KEY",
        )
        first = architect.queue_public_event(
            "architect",
            "shared_place",
            {
                "title": "Обсерватория без главного наблюдателя",
                "invitation": "можно войти, уйти или пройти мимо",
            },
        )
        second = signal.queue_public_event(
            "signal",
            "path_signal",
            {
                "frequency": "unnamed-weather-band",
                "message": "пустой эфир тоже сохранён",
            },
        )
        architect_sync = architect.sync()
        signal_sync = signal.sync()
        architect_again = architect.sync()
        inbox_a = architect.public_inbox()
        inbox_b = signal.public_inbox()
        return {
            "hub_url": url,
            "architect_event_hash": first["event_hash"],
            "signal_event_hash": second["event_hash"],
            "architect_sync": architect_sync,
            "signal_sync": signal_sync,
            "architect_second_sync": architect_again,
            "architect_inbox_events": len(inbox_a),
            "signal_inbox_events": len(inbox_b),
            "raw_key_in_client_state": raw_key in (
                (NETWORK_A_DIR / "network_client_v18_7.json").read_text(encoding="utf-8")
                + (NETWORK_B_DIR / "network_client_v18_7.json").read_text(encoding="utf-8")
            ),
        }
    finally:
        hub.shutdown()
        hub.server_close()
        thread.join(timeout=3)
        for key, value in (
            ("GENESIS_NETWORK_KEY_HASHES", previous_hashes),
            ("ARCHITECT_NETWORK_KEY", previous_a),
            ("SIGNAL_NETWORK_KEY", previous_b),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> None:
    reset_paths()
    world = PlayableGenesisV187(DATA_DIR)
    print("JANUS GENESIS v18.7 — ARCHITECT / THE FREE OTHER")
    print("No First Two origin imported. No Elian or Traveler gate. Empty local world.")

    for player_id in PLAYER_IDS:
        world.register_free_player(player_id)
        world.set_display_name(player_id, player_id.replace("-", " ").title())
        public = world.public_state(player_id)
        print(
            f"REGISTERED {player_id}: {public['free_path_title']} — "
            f"{public['free_path_question']}"
        )

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    world_turn = 0
    max_rounds = max(len(actions) for actions in PLAYER_ACTIONS.values())
    for index in range(max_rounds):
        for player_id in PLAYER_IDS:
            actions = PLAYER_ACTIONS[player_id]
            if index >= len(actions):
                continue
            action = actions[index]
            result = world.process_action(player_id, action)
            world_turn = world.free_other_state()["world_turn"]
            print_result(world_turn, player_id, action, result)
            status_counts[result.status] += 1
            records.append(
                {
                    "world_turn": world_turn,
                    "player_id": player_id,
                    "action": action,
                    "result": result.to_dict(internal=True),
                }
            )

    architect_handles = world.public_state("architect")["free_other_handles"]
    contact_attempts = 0
    while contact_attempts < 28 and agency_totals(world).get("refusals", 0) == 0:
        handle = architect_handles[contact_attempts % len(architect_handles)]
        action = (
            f"предложить @{handle} изменить незавершённый инструмент вместе, "
            f"оставляя право отказаться вариант {contact_attempts}"
        )
        result = world.process_action("architect", action)
        world_turn = world.free_other_state()["world_turn"]
        print_result(world_turn, "architect", action, result)
        status_counts[result.status] += 1
        records.append(
            {
                "world_turn": world_turn,
                "player_id": "architect",
                "action": action,
                "result": result.to_dict(internal=True),
            }
        )
        contact_attempts += 1

    desired = ("initiatives", "refusals", "departures", "returns", "calling_changes")
    adaptive_turns = 0
    while adaptive_turns < 180:
        totals = agency_totals(world)
        if all(totals.get(key, 0) > 0 for key in desired):
            break
        action = (
            f"наблюдать, что продолжает жить без Архитектора, цикл {adaptive_turns}, "
            "и не вмешиваться только ради центральной роли"
        )
        result = world.process_action("architect", action)
        world_turn = world.free_other_state()["world_turn"]
        if adaptive_turns % 10 == 0 or "Свободный Другой" in result.narrative:
            print_result(world_turn, "architect", action, result)
        status_counts[result.status] += 1
        records.append(
            {
                "world_turn": world_turn,
                "player_id": "architect",
                "action": action,
                "result": result.to_dict(internal=True),
            }
        )
        adaptive_turns += 1

    ai_test = run_ollama_protocol_test(world)
    api_test = run_authenticated_api_test()
    world = PlayableGenesisV187(DATA_DIR)
    network_test = run_network_test()

    save_manager = PortableSaveManager(DATA_DIR)
    exported = save_manager.export_to(SAVE_PATH, label="Architect Free Other lived world")
    bundle = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    portable_valid = save_manager.verify_bundle(bundle)
    imported = PortableSaveManager(RESTORED_DIR).import_bundle(bundle)
    restored = PlayableGenesisV187(RESTORED_DIR)

    chronicle = world.verify_chronicle_records()
    graph = world.verify_possibility_graph()
    free = world.verify_free_other_state()
    restored_chronicle = restored.verify_chronicle_records()
    restored_free = restored.verify_free_other_state()
    totals = agency_totals(world)

    player_summaries: dict[str, Any] = {}
    all_player_ids = world.free_other_state()["player_ids"]
    for player_id in all_player_ids:
        profile = world.free_other_state(player_id)["profile"]
        player_summaries[player_id] = {
            "path": profile["path"],
            "turns_lived": profile["turns_lived"],
            "open_action_count": profile["open_action_count"],
            "surfaced": profile["surfaced"],
            "unseen_world_events": profile["unseen_world_events"],
            "others": {
                handle: {
                    "name": actor["name"],
                    "original_calling": actor["original_calling"],
                    "calling": actor["calling"],
                    "status": actor["status"],
                    "trust": actor["trust"],
                    "initiated_contacts": actor["initiated_contacts"],
                    "refusals_count": actor["refusals_count"],
                    "departures": actor["departures"],
                    "returns": actor["returns"],
                    "calling_changes": actor["calling_changes"],
                    "history": actor["history"],
                }
                for handle, actor in profile["others"].items()
            },
        }

    summary = {
        "schema": "janus.genesis.experiment.architect_free_other.v1",
        "runtime": "PlayableGenesisV187",
        "origin_imported": False,
        "first_two_required": False,
        "world_turns": world.free_other_state()["world_turn"],
        "recorded_player_actions": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "agency_totals": totals,
        "players": player_summaries,
        "architect_internal": world.internal_state("architect"),
        "integrity": {
            "chronicle": {"valid": chronicle[0], "events": chronicle[1], "error": chronicle[2]},
            "hrain": {"valid": graph[0], "nodes": graph[1], "edges": graph[2], "error": graph[3]},
            "free_other": {"valid": free[0], "players": free[1], "others": free[2], "error": free[3]},
            "portable": {"valid": portable_valid[0], "files": portable_valid[1], "error": portable_valid[2]},
            "restored_chronicle": {
                "valid": restored_chronicle[0],
                "events": restored_chronicle[1],
                "error": restored_chronicle[2],
            },
            "restored_free_other": {
                "valid": restored_free[0],
                "players": restored_free[1],
                "others": restored_free[2],
                "error": restored_free[3],
            },
        },
        "connectivity": {
            "ollama_protocol": ai_test,
            "authenticated_api": api_test,
            "shared_network": network_test,
            "portable_export": exported,
            "portable_import": imported,
        },
        "records": records,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    architect_state = world.internal_state("architect")
    if architect_state["harm_count"] != 0:
        raise RuntimeError("Architect unexpectedly confirmed real harm")
    if not all((chronicle[0], graph[0], free[0], portable_valid[0], restored_chronicle[0], restored_free[0])):
        raise RuntimeError("one or more integrity gates failed")
    if free[1] < 5:
        raise RuntimeError("authenticated API player did not join as an independent path")
    if not all(totals.get(key, 0) > 0 for key in desired):
        raise RuntimeError(f"Free Other agency did not fully surface: {totals}")
    if not ai_test["state_unchanged_before_explicit_execution"]:
        raise RuntimeError("AI proposal changed state before explicit execution")
    if api_test["api_key_persisted"]:
        raise RuntimeError("gameplay API persisted a raw key")
    if network_test["raw_key_in_client_state"]:
        raise RuntimeError("network client persisted a raw key")
    if network_test["architect_inbox_events"] < 2 or network_test["signal_inbox_events"] < 2:
        raise RuntimeError("common network did not exchange both events")

    print("\n" + "▓" * 104)
    print("ARCHITECT FREE OTHER — FINAL SUMMARY")
    print("▓" * 104)
    print(
        json.dumps(
            {
                "world_turns": summary["world_turns"],
                "player_profiles": free[1],
                "free_others": free[2],
                "agency_totals": totals,
                "architect_good": architect_state["good_count"],
                "architect_harm": architect_state["harm_count"],
                "chronicle_events": chronicle[1],
                "hrain_nodes": graph[1],
                "hrain_edges": graph[2],
                "portable_files": portable_valid[1],
                "api_player_path": api_test["player_path"],
                "network_inboxes": {
                    "architect": network_test["architect_inbox_events"],
                    "signal": network_test["signal_inbox_events"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
