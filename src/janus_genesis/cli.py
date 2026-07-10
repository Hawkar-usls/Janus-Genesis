from __future__ import annotations

import argparse
import json
from pathlib import Path

from janus_genesis.config import JanusConfig
from janus_genesis.pipeline import analyze_model, run_workspace

DEFAULT_WORKSPACE = Path("workspace")


def _load_config(path: Path) -> JanusConfig:
    return JanusConfig.load(path) if path.exists() else JanusConfig()


def init_workspace(workspace: Path) -> None:
    for name in ("inbox", "outbox", "reports"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    config_path = workspace / "janus.config.json"
    if not config_path.exists():
        JanusConfig().save(config_path)
    print(f"[JANUS] Workspace готов: {workspace.resolve()}")
    print(f"[JANUS] Положи STL/OBJ/PLY в: {(workspace / 'inbox').resolve()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="janus-genesis",
        description="Преобразователь существующих моделей для FDM-печати.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init-workspace", help="Создать рабочие папки")
    init_cmd.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)

    analyze_cmd = subparsers.add_parser("analyze", help="Проанализировать одну модель")
    analyze_cmd.add_argument("model", type=Path)
    analyze_cmd.add_argument("--config", type=Path, default=DEFAULT_WORKSPACE / "janus.config.json")

    run_cmd = subparsers.add_parser("run", help="Преобразовать модели из inbox")
    run_cmd.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    run_cmd.add_argument("--config", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "init-workspace":
        init_workspace(args.workspace)
        return 0

    if args.command == "analyze":
        config = _load_config(args.config)
        report = analyze_model(args.model, config)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    workspace: Path = args.workspace
    config_path: Path = args.config or workspace / "janus.config.json"
    config = _load_config(config_path)
    results = run_workspace(
        input_dir=workspace / "inbox",
        output_dir=workspace / "outbox",
        report_dir=workspace / "reports",
        config=config,
    )
    if not results:
        print(f"[JANUS] В {(workspace / 'inbox').resolve()} нет STL/OBJ/PLY моделей.")
        return 2
    for result in results:
        print(f"[JANUS] Готов кандидат: {result['output']}")
        print(f"[JANUS] Отчёт: {result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
