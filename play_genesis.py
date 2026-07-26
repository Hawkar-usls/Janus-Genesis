# -*- coding: utf-8 -*-
"""Primary playable CLI for Janus Genesis v17."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from genesis_v17 import WorldResult
from genesis_v17_playable import PLAYABLE_VERSION, PlayableGenesisV17


def banner() -> None:
    print(
        "\n╔══════════════════════════════════════════════════╗\n"
        f"║       JANUS GENESIS v{PLAYABLE_VERSION:<22}║\n"
        "║  THE OTHER FACE · LIVING GRACE · MEMORY          ║\n"
        "╚══════════════════════════════════════════════════╝\n"
    )


def print_result(result: WorldResult) -> None:
    print(f"\n{result.narrative}")
    print(f"[{result.realm.value}]", end="")
    if result.branch_id:
        print(f" branch={result.branch_id}", end="")
    print()
    for index, choice in enumerate(result.choices, 1):
        print(f"{index}. {choice}")
    print()


def play(data_dir: Path, player_id: str, name: str) -> int:
    world = PlayableGenesisV17(data_dir)
    world.set_display_name(player_id, name)
    banner()
    state = world.public_state(player_id)
    print(
        f"Игрок: {state['display_name']} | Мир: {state['realm']}\n"
        f"{state['world_response']}\n\n"
        "Напиши действие обычными словами.\n"
        "Другой игрок указывается через @id, например:\n"
        "  помочь @wanderer починить крышу после пожара\n"
        "Желание начинается словами «Пусть…» или «Желаю…».\n"
        "Первая обычная команда выхода открывает порог подтверждения.\n"
        "Повтори её или напиши «подтверждаю выход»; Ctrl+C выходит сразу.\n"
    )
    while True:
        try:
            action = input("🌀 > ").strip() or "Осмотреться"
        except EOFError:
            print()
            result = world.force_exit(player_id, reason="end_of_input")
            print_result(result)
            return 0
        except KeyboardInterrupt:
            print()
            result = world.force_exit(player_id, reason="keyboard_interrupt")
            print_result(result)
            return 0
        result = world.process_action(player_id, action)
        print_result(result)
        if result.status == "EXIT":
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="play_genesis.py")
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument("--player", default="traveler")
    parser.add_argument("--name", default="Unknown Wanderer")
    parser.add_argument("--action", help="Process one v17 action, print JSON and exit.")
    parser.add_argument("--status", action="store_true", help="Print public player state.")
    parser.add_argument(
        "--verify-chronicle",
        action="store_true",
        help="Validate v17 Chronicle records and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    world = PlayableGenesisV17(args.data_dir)
    world.set_display_name(args.player, args.name)
    if args.verify_chronicle:
        valid, count, error = world.verify_chronicle_records()
        print(json.dumps(
            {"valid": valid, "events": count, "error": error},
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if valid else 1
    if args.status:
        print(json.dumps(world.public_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.action is not None:
        print(json.dumps(
            world.process_action(args.player, args.action).to_dict(),
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    return play(args.data_dir, args.player, args.name)


if __name__ == "__main__":
    raise SystemExit(main())
