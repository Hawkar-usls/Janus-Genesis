# -*- coding: utf-8 -*-
"""Primary playable CLI for Janus Genesis v18.7.

Normal ``process_action`` entries are routed through the v18.7.33 portable
stable-request receipt boundary. A logical retry must reuse its request ID;
repeating identical text under a new request ID remains a new intent.

This does not claim that every mutating utility in this file is transactionally
covered. In particular save import/export, network publication and forced exit
have their own semantics and must not inherit the process_action claim merely
because the normal action path is protected.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from genesis_v18 import WorldResult
from genesis_v18_7_ai import AIProviderConfig, GenesisAIBridge, build_provider
from genesis_v18_7_network import ALLOWED_EVENT_KINDS, GenesisNetworkClient
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager
from genesis_v18_7_31_portable_receipt_runtime import (
    PortableRequestConflict,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
    PortableRuntimeReceiptIntegrityError,
)
from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)

CONTROL_CLIENT_ID = "play-genesis"


def banner() -> None:
    print(
        "\n╔══════════════════════════════════════════════════╗\n"
        f"║       JANUS GENESIS v{PLAYABLE_VERSION:<22}║\n"
        "║ FREE OTHER · AI BRIDGE · SHARED NETWORK       ║\n"
        "╚══════════════════════════════════════════════════╝\n"
    )


def print_result(result: WorldResult) -> None:
    print(f"\n{result.narrative}")
    for index, choice in enumerate(result.choices, 1):
        print(f"{index}. {choice}")
    print()


def _new_request_id(prefix: str = "CLI") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _build_controlled_runtime(world: PlayableGenesisV187, data_dir: Path):
    return ReconciledPortableReceiptRuntimeAdapter(world, data_dir)


def _control_error_payload(runtime, request_id: str, exc: BaseException) -> dict[str, Any]:
    return {
        "status": "JANUS_CONTROL_BLOCKED",
        "client_id": CONTROL_CLIENT_ID,
        "request_id": request_id,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "request_state": runtime.request_state(
            client_id=CONTROL_CLIENT_ID,
            request_id=request_id,
        ),
        "automatic_reexecution_attempted": False,
    }


def _execute_controlled(
    runtime,
    *,
    player_id: str,
    action: str,
    request_id: str,
) -> WorldResult:
    return runtime.execute(
        client_id=CONTROL_CLIENT_ID,
        request_id=request_id,
        actor_id=player_id,
        action=action,
    )


def _build_ai_bridge(args: argparse.Namespace) -> GenesisAIBridge | None:
    if not args.ai_provider:
        return None
    if not args.ai_model:
        raise SystemExit("--ai-model is required when --ai-provider is used")
    provider = args.ai_provider.lower()
    endpoint = args.ai_endpoint
    if not endpoint:
        endpoint = (
            "http://127.0.0.1:11434"
            if provider == "ollama"
            else "http://127.0.0.1:8000"
        )
    config = AIProviderConfig(
        provider=provider,
        model=args.ai_model,
        endpoint=endpoint,
        api_key_env=args.ai_key_env,
        timeout_seconds=args.ai_timeout,
    )
    return GenesisAIBridge(build_provider(config))


def _build_network_client(
    args: argparse.Namespace,
    data_dir: Path,
) -> GenesisNetworkClient | None:
    if not args.network_url:
        return None
    return GenesisNetworkClient(
        data_dir,
        hub_url=args.network_url,
        api_key_env=args.network_key_env,
        timeout_seconds=args.network_timeout,
    )


def _parse_public_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {"text": ""}
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return {"text": stripped[:4000]}
    if isinstance(value, dict):
        return value
    return {"value": value}


def play(
    data_dir: Path,
    player_id: str,
    name: str | None,
    *,
    ai_bridge: GenesisAIBridge | None = None,
    network: GenesisNetworkClient | None = None,
) -> int:
    world = PlayableGenesisV187(data_dir)
    runtime = _build_controlled_runtime(world, data_dir)
    saves = PortableSaveManager(data_dir)
    if name:
        world.set_display_name(player_id, name)
    banner()
    state = world.public_state(player_id)
    print(
        f"Игрок: {state['display_name']}\n"
        f"Твоя линия: {state['free_path_title']}\n"
        f"Вопрос пути: {state['free_path_question']}\n"
        f"{state['world_response']}\n\n"
        "Пиши действия обычными словами. Готовые варианты — только примеры, а не границы мира.\n"
        "Другой человек обозначается через @id; доступные Free Other handles видны через --debug-others.\n"
        "Свободный Другой не является наградой: он может первым заговорить, отказаться, уйти, изменить цель и вернуться.\n"
        "Ни Путник, ни Элиан, ни любой иной origin не являются обязательным началом для нового игрока.\n"
        "Добро не является валютой: построенное, исцелённое и соединённое создаёт новые реальные возможности.\n"
        "HRaiN сохраняет происхождение возможностей и самостоятельных действий Другого.\n"
        "Внешний ИИ может только предложить действие; состояние меняет исключительно Genesis runtime.\n"
        "Локальный JSON-save остаётся источником истины устройства; общий hub передаёт лишь явно публичные события.\n"
        "Молчание допустимо. Отсутствие ответа не является согласием, любовью, прощением или обещанием вернуться.\n"
        "Разрушительный поступок и выход требуют повторного подтверждения.\n"
        "Каждое обычное действие получает request_id. Для логического повтора используй /retry REQUEST_ID ДЕЙСТВИЕ.\n"
    )
    commands = ["/save PATH", "/retry REQUEST_ID ДЕЙСТВИЕ", "/request REQUEST_ID"]
    if ai_bridge is not None:
        commands.append("/ai НАМЕРЕНИЕ")
    if network is not None:
        commands.extend(["/publish ТЕКСТ", "/sync", "/network"])
    print("Служебные команды: " + " · ".join(commands) + "\n")

    while True:
        try:
            action = input("🌀 > ").strip() or "Осмотреться"
        except EOFError:
            print()
            # Forced-exit persistence remains an explicitly separate mutation
            # boundary; it is not silently attributed to the action receipt path.
            print_result(world.force_exit(player_id, reason="end_of_input"))
            return 0
        except KeyboardInterrupt:
            print()
            print_result(world.force_exit(player_id, reason="keyboard_interrupt"))
            return 0

        explicit_request_id: str | None = None
        if action.startswith("/retry "):
            parts = action.split(" ", 2)
            if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
                print("Формат: /retry REQUEST_ID ДЕЙСТВИЕ")
                continue
            explicit_request_id = parts[1].strip()
            action = parts[2].strip()

        elif action.startswith("/request "):
            request_id = action.split(" ", 1)[1].strip()
            if not request_id:
                print("Нужен REQUEST_ID.")
                continue
            print(
                json.dumps(
                    runtime.request_state(client_id=CONTROL_CLIENT_ID, request_id=request_id),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            continue

        if action.startswith("/save "):
            path = action.split(" ", 1)[1].strip()
            if not path:
                print("Нужен путь к JSON-файлу.")
                continue
            print(json.dumps(saves.export_to(path), ensure_ascii=False, indent=2))
            continue

        if action.startswith("/ai "):
            if ai_bridge is None:
                print("AI bridge не настроен. Запусти CLI с --ai-provider и --ai-model.")
                continue
            intention = action.split(" ", 1)[1].strip()
            try:
                proposal = ai_bridge.propose_action(world, player_id, intention)
            except Exception as exc:
                print(f"AI bridge error: {exc}")
                continue
            print(json.dumps(proposal, ensure_ascii=False, indent=2))
            confirmation = input("Исполнить предложенное действие через Genesis? [y/N] ").strip().lower()
            if confirmation not in {"y", "yes", "д", "да"}:
                print("Предложение осталось предложением и не изменило мир.")
                continue
            action = proposal["action"]

        elif action == "/sync":
            if network is None:
                print("Network client не настроен. Укажи --network-url.")
                continue
            try:
                print(json.dumps(network.sync(), ensure_ascii=False, indent=2))
            except Exception as exc:
                print(f"Network sync error: {exc}")
            continue

        elif action == "/network":
            if network is None:
                print("Network client не настроен. Укажи --network-url.")
            else:
                print(json.dumps(network.state(), ensure_ascii=False, indent=2))
            continue

        elif action.startswith("/publish "):
            if network is None:
                print("Network client не настроен. Укажи --network-url.")
                continue
            text = action.split(" ", 1)[1].strip()
            try:
                event = network.queue_public_event(
                    player_id,
                    "public_message",
                    {"text": text[:4000]},
                )
                print(
                    json.dumps(
                        {
                            "queued": True,
                            "event_hash": event["event_hash"],
                            "public_player_id": event["public_player_id"],
                            "api_key_persisted": False,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            except Exception as exc:
                print(f"Network queue error: {exc}")
            continue

        request_id = explicit_request_id or _new_request_id("TURN")
        print(f"🔒 request_id: {request_id}")
        try:
            result = _execute_controlled(
                runtime,
                player_id=player_id,
                action=action,
                request_id=request_id,
            )
        except (
            PortableRequestConflict,
            PortableRuntimeOutcomeUndetermined,
            PortableRuntimeReceiptIntegrityError,
            PortableRuntimeControlError,
        ) as exc:
            print(json.dumps(_control_error_payload(runtime, request_id, exc), ensure_ascii=False, indent=2))
            continue
        print_result(result)
        if result.status == "EXIT":
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="play_genesis.py")
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument("--player", default="traveler")
    parser.add_argument("--name", default=None)
    parser.add_argument("--action", help="Process one controlled action, print safe JSON and exit.")
    parser.add_argument(
        "--request-id",
        help=(
            "Stable logical request ID for --action. Reuse only when retrying the same actor/action intent; "
            "same ID with different action fails closed."
        ),
    )
    parser.add_argument(
        "--request-state",
        metavar="REQUEST_ID",
        help="Inspect the persisted play-genesis request state without executing the world.",
    )
    parser.add_argument("--status", action="store_true", help="Print public player state.")
    parser.add_argument("--debug-state", action="store_true", help="Developer-only internal state.")
    parser.add_argument("--debug-secrets", action="store_true", help="Developer-only Secret seed state.")
    parser.add_argument("--debug-narrator", action="store_true", help="Developer-only MoralEcho/CareBond state.")
    parser.add_argument("--debug-absurdity", action="store_true", help="Developer-only Absurdity Lens state.")
    parser.add_argument("--debug-childhood", action="store_true", help="Developer-only child/guardian/gift safety state.")
    parser.add_argument("--debug-stories", action="store_true", help="Developer-only public story metadata.")
    parser.add_argument("--debug-threads", action="store_true", help="Developer-only Living Threads state.")
    parser.add_argument("--debug-possibilities", action="store_true", help="Developer-only HRaiN possibility graph state.")
    parser.add_argument("--debug-others", action="store_true", help="Developer-only independent player path and Free Other state.")
    parser.add_argument("--verify-chronicle", action="store_true", help="Validate the linked v18 Chronicle.")
    parser.add_argument("--verify-possibility-graph", action="store_true", help="Validate HRaiN node and edge integrity hashes.")
    parser.add_argument("--verify-free-others", action="store_true", help="Validate player-path and Free Other agency invariants.")

    parser.add_argument("--export-save", type=Path, help="Export all local Genesis JSON state into one portable JSON file.")
    parser.add_argument("--import-save", type=Path, help="Import one verified portable Genesis JSON save.")
    parser.add_argument("--save-conflict", choices=("replace", "skip", "fail"), default="replace")

    parser.add_argument("--ai-provider", choices=("ollama", "openai-compatible"))
    parser.add_argument("--ai-model")
    parser.add_argument("--ai-endpoint")
    parser.add_argument("--ai-key-env", default=None)
    parser.add_argument("--ai-timeout", type=float, default=45.0)
    parser.add_argument("--ai-propose", help="Ask the configured AI to propose one action without executing it.")

    parser.add_argument("--network-url", help="Shared Genesis Network hub base URL.")
    parser.add_argument("--network-key-env", default="GENESIS_NETWORK_API_KEY")
    parser.add_argument("--network-timeout", type=float, default=20.0)
    parser.add_argument("--network-sync", action="store_true", help="Push outbox and pull public events once.")
    parser.add_argument("--network-state", action="store_true", help="Show local network client state without API keys.")
    parser.add_argument("--network-publish", choices=tuple(sorted(ALLOWED_EVENT_KINDS)))
    parser.add_argument("--network-payload", default="{}", help="JSON object or text for --network-publish.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    world = PlayableGenesisV187(args.data_dir)
    runtime = _build_controlled_runtime(world, args.data_dir)
    saves = PortableSaveManager(args.data_dir)
    if args.name:
        world.set_display_name(args.player, args.name)

    if args.request_state:
        print(
            json.dumps(
                runtime.request_state(
                    client_id=CONTROL_CLIENT_ID,
                    request_id=args.request_state,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.import_save:
        print(json.dumps(saves.import_file(args.import_save, conflict=args.save_conflict), ensure_ascii=False, indent=2))
        return 0
    if args.export_save:
        print(json.dumps(saves.export_to(args.export_save), ensure_ascii=False, indent=2))
        return 0

    ai_bridge = _build_ai_bridge(args)
    network = _build_network_client(args, args.data_dir)
    if args.ai_propose is not None:
        if ai_bridge is None:
            raise SystemExit("--ai-propose requires --ai-provider and --ai-model")
        print(json.dumps(ai_bridge.propose_action(world, args.player, args.ai_propose), ensure_ascii=False, indent=2))
        return 0
    if args.network_state:
        if network is None:
            raise SystemExit("--network-state requires --network-url")
        print(json.dumps(network.state(), ensure_ascii=False, indent=2))
        return 0
    if args.network_publish:
        if network is None:
            raise SystemExit("--network-publish requires --network-url")
        event = network.queue_public_event(
            args.player,
            args.network_publish,
            _parse_public_payload(args.network_payload),
        )
        print(json.dumps(event, ensure_ascii=False, indent=2))
        return 0
    if args.network_sync:
        if network is None:
            raise SystemExit("--network-sync requires --network-url")
        print(json.dumps(network.sync(), ensure_ascii=False, indent=2))
        return 0

    if args.verify_chronicle:
        valid, count, error = world.verify_chronicle_records()
        print(json.dumps({"valid": valid, "events": count, "error": error}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if args.verify_possibility_graph:
        valid, nodes, edges, error = world.verify_possibility_graph()
        print(json.dumps({"valid": valid, "nodes": nodes, "edges": edges, "error": error}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if args.verify_free_others:
        valid, players, others, error = world.verify_free_other_state()
        print(json.dumps({"valid": valid, "players": players, "others": others, "error": error}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if args.status:
        print(json.dumps(world.public_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_state:
        print(json.dumps(world.internal_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_secrets:
        print(json.dumps(world.secret_state(), ensure_ascii=False, indent=2))
        return 0
    if args.debug_narrator:
        print(json.dumps(world.narrator_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_absurdity:
        print(json.dumps(world.absurdity_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_childhood:
        payload = world.protected_childhood_state(args.player)
        payload["gifts"] = world._read_json(world.gifts_path, {"gifts": []})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.debug_stories:
        print(json.dumps(world.public_story_state(), ensure_ascii=False, indent=2))
        return 0
    if args.debug_threads:
        print(json.dumps(world.living_threads_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_possibilities:
        print(json.dumps(world.possibility_graph_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_others:
        print(json.dumps(world.free_other_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.action is not None:
        request_id = str(args.request_id).strip() if args.request_id else _new_request_id("ACTION")
        try:
            result = _execute_controlled(
                runtime,
                player_id=args.player,
                action=args.action,
                request_id=request_id,
            )
        except (
            PortableRequestConflict,
            PortableRuntimeOutcomeUndetermined,
            PortableRuntimeReceiptIntegrityError,
            PortableRuntimeControlError,
        ) as exc:
            print(json.dumps(_control_error_payload(runtime, request_id, exc), ensure_ascii=False, indent=2))
            return 2
        payload = result.to_dict()
        payload["_janus_control"] = {
            "client_id": CONTROL_CLIENT_ID,
            "request_id": request_id,
            "request_state": runtime.request_state(
                client_id=CONTROL_CLIENT_ID,
                request_id=request_id,
            ),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.request_id:
        raise SystemExit("--request-id requires --action; use --request-state to inspect an existing request")
    return play(
        args.data_dir,
        args.player,
        args.name,
        ai_bridge=ai_bridge,
        network=network,
    )


if __name__ == "__main__":
    raise SystemExit(main())
