# -*- coding: utf-8 -*-
"""Primary playable CLI for Janus Genesis v18."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from genesis_v18 import WorldResult
from genesis_v18_playable import PLAYABLE_VERSION, PlayableGenesisV18


def banner() -> None:
    print(
        "\n╔══════════════════════════════════════════════════╗\n"
        f"║       JANUS GENESIS v{PLAYABLE_VERSION:<22}║\n"
        "║  ONE WORLD · UNIVERSAL GOD MODE · LIVING MEMORY  ║\n"
        "╚══════════════════════════════════════════════════╝\n"
    )


def print_result(result: WorldResult) -> None:
    print(f"\n{result.narrative}")
    for index, choice in enumerate(result.choices, 1):
        print(f"{index}. {choice}")
    print()


def play(data_dir: Path, player_id: str, name: str | None) -> int:
    world = PlayableGenesisV18(data_dir)
    if name:
        world.set_display_name(player_id, name)
    banner()
    state = world.public_state(player_id)
    print(
        f"Игрок: {state['display_name']}\n"
        f"{state['world_response']}\n\n"
        "Пиши действия обычными словами. Другой человек обозначается через @id.\n"
        "Доброе желание начинается словами «Пусть…» или «Желаю…».\n"
        "Разрушительный поступок требует повторного подтверждения.\n"
        "Первая команда выхода также открывает мягкий порог подтверждения.\n"
    )
    while True:
        try:
            action = input("🌀 > ").strip() or "Осмотреться"
        except EOFError:
            print()
            print_result(world.force_exit(player_id, reason="end_of_input"))
            return 0
        except KeyboardInterrupt:
            print()
            print_result(world.force_exit(player_id, reason="keyboard_interrupt"))
            return 0
        result = world.process_action(player_id, action)
        print_result(result)
        if result.status == "EXIT":
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="play_genesis.py")
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument("--player", default="traveler")
    parser.add_argument("--name", default=None)
    parser.add_argument("--action", help="Process one action, print safe JSON and exit.")
    parser.add_argument("--status", action="store_true", help="Print public player state.")
    parser.add_argument("--debug-state", action="store_true", help="Developer-only internal state.")
    parser.add_argument("--verify-chronicle", action="store_true", help="Validate the linked v18 Chronicle.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    world = PlayableGenesisV18(args.data_dir)
    if args.name:
        world.set_display_name(args.player, args.name)
    if args.verify_chronicle:
        valid, count, error = world.verify_chronicle_records()
        print(json.dumps({"valid": valid, "events": count, "error": error}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if args.status:
        print(json.dumps(world.public_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.debug_state:
        print(json.dumps(world.internal_state(args.player), ensure_ascii=False, indent=2))
        return 0
    if args.action is not None:
        print(json.dumps(world.process_action(args.player, args.action).to_dict(), ensure_ascii=False, indent=2))
        return 0
    return play(args.data_dir, args.player, args.name)


if __name__ == "__main__":
    raise SystemExit(main())
