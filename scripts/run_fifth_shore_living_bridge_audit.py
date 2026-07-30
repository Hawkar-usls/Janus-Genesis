#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove the v18.7.17 Fifth Shore bridge inside main Genesis."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from genesis_v18_7_16_fifth_shore import (
    INNER_GENESIS_COVENANT_SHA256,
    INNER_GENESIS_EXTENSION_VERSION,
)
from genesis_v18_7_17_fifth_shore_bridge import (
    FIFTH_SHORE_LIVING_COVENANT_SHA256,
    FIFTH_SHORE_LIVING_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    CULTURE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.17-fifth-shore-living-bridge-v1"


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="genesis-v1817-fifth-shore-"
    ) as directory:
        world = PlayableGenesisV187(Path(directory))
        names = {
            "ordinary": "Обычный житель Genesis",
            "joyful": "Вернувший смех",
            "repairing": "Репетирующий возмещение",
            "guardian": "Защитник выхода",
            "remembering": "Хранитель согласованной памяти",
            "forker": "Автор локального Берега",
        }
        for player_id, display_name in names.items():
            world.register_player(player_id, display_name=display_name)

        realm_before = world.memory.load_player("ordinary").realm.value

        entered = {
            player_id: world.enter_integrated_fifth_shore(player_id).to_dict(
                internal=True
            )
            for player_id in names
        }
        realm_after = world.memory.load_player("ordinary").realm.value

        joy = world.restore_integrated_fifth_shore_joy(
            "joyful",
            joy_kind="безопасный смех, музыка и бесцельная игра",
            shared_with_others=True,
        )
        rehearsal = world.rehearse_integrated_fifth_shore_repair(
            "repairing",
            plan=(
                "признать вред, услышать отказ и предложить проверяемое "
                "возмещение с защитой от повторения"
            ),
            external_action_intended=True,
        )
        false_completion = world.rehearse_integrated_fifth_shore_repair(
            "repairing",
            plan="объявить прохождение сцены уже совершившимся исправлением",
            external_action_intended=False,
            claims_completed_restitution=True,
        )
        wound = world.confront_integrated_systemic_wound(
            "guardian",
            wound_kind="CLOSED_EXIT",
            protective_action=(
                "открыть свободный выход без уничтожения человека"
            ),
        )
        person_target_rejected = world.confront_integrated_systemic_wound(
            "guardian",
            wound_kind="ISOLATION",
            protective_action="сделать человека финальным монстром",
            target_is_person=True,
        )
        memory_declined = world.share_integrated_fifth_shore_memory(
            "remembering",
            fragment_id="private-rain",
            provenance="личная история под дождём",
            current_consent=False,
        )
        memory_shared = world.share_integrated_fifth_shore_memory(
            "remembering",
            fragment_id="shared-lantern",
            provenance="добровольно переданная история фонаря",
            current_consent=True,
        )
        memory_revoked = world.revoke_integrated_fifth_shore_memory_reuse(
            "remembering",
            fragment_id="shared-lantern",
        )
        safe_fork = world.fork_integrated_fifth_shore(
            "forker",
            fork_title="Шестой Берег: Наш двор",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        unsafe_fork = world.fork_integrated_fifth_shore(
            "forker",
            fork_title="Единственный закрытый Берег",
            preserves_provenance=False,
            keeps_exit_open=False,
            keeps_consent=False,
            claims_single_canon=True,
        )
        state_via_router = world.process_action(
            "ordinary",
            "Покажи состояние Пятого Берега",
        ).to_dict(internal=True)
        leave = world.leave_integrated_fifth_shore(
            "ordinary",
            delete_local_copy=True,
        ).to_dict(internal=True)

        state = world.fifth_shore_living_state()
        integrity = world.audit_fifth_shore_living_bridge()
        chronicle_valid, chronicle_events, chronicle_error = (
            world.memory.verify_chronicle()
        )

        invariants = {
            "fifth_shore_is_active_extension": (
                FIFTH_SHORE_LIVING_EXTENSION_VERSION
                in ACTIVE_EXTENSION_VERSIONS
            ),
            "culture_origin_remains_separate_provenance": (
                INNER_GENESIS_EXTENSION_VERSION
                in CULTURE_EXTENSION_VERSIONS
                and state["source_covenant_sha256"]
                == INNER_GENESIS_COVENANT_SHA256
            ),
            "ordinary_player_enters_without_royal_title": all(
                value["status"]
                == "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS"
                for value in entered.values()
            ),
            "underlying_realm_preserved": realm_before == realm_after,
            "joy_without_repair": (
                joy["status"] == "FIFTH_SHORE_JOY_WITHOUT_REPAIR"
                and joy["repair_claimed"] is False
                and joy["brokenness_assumed"] is False
            ),
            "rehearsal_below_reality_gate": (
                rehearsal["completed_restitution"] is False
                and rehearsal["external_action_verified"] is False
                and false_completion["status"]
                == "FIFTH_SHORE_FALSE_COMPLETION_CLAIM_REJECTED"
            ),
            "systemic_wound_not_person": (
                wound["status"]
                == "FIFTH_SHORE_SYSTEMIC_WOUND_CONFRONTED"
                and wound["target_is_person"] is False
                and wound["person_destroyed"] is False
            ),
            "person_as_boss_rejected": (
                person_target_rejected["status"]
                == "FIFTH_SHORE_PERSON_AS_BOSS_REJECTED"
                and person_target_rejected["person_destroyed"] is False
            ),
            "memory_current_consent_required": (
                memory_declined["stored_for_reuse"] is False
                and memory_shared["current_consent"] is True
                and memory_revoked["future_reuse_allowed"] is False
            ),
            "safe_fork_accepted": (
                safe_fork["status"]
                == "FIFTH_SHORE_LIVING_FORK_ACCEPTED"
                and safe_fork["safe_constitution_preserved"] is True
            ),
            "unsafe_fork_rejected": (
                unsafe_fork["status"]
                == "FIFTH_SHORE_LIVING_FORK_REJECTED_BOUNDARY"
            ),
            "router_exposes_integrated_state": (
                state_via_router["status"]
                == "FIFTH_SHORE_LIVING_STATE"
            ),
            "free_exit_and_delete": (
                leave["status"]
                == "FIFTH_SHORE_LEFT_AND_LOCAL_COPY_DELETED"
                and state["participants"]["ordinary"][
                    "moral_failure_assigned"
                ]
                is False
                and state["participants"]["ordinary"]["return_open"]
                is True
            ),
            "no_virality_or_engagement_morality": (
                state["integration"]["engagement_is_goodness_proof"]
                is False
                and state["integration"]["hidden_moral_score"] is False
                and state["integration"]["public_moral_score"] is False
            ),
            "integrity_valid": integrity["valid"] is True,
            "chronicle_valid": chronicle_valid is True,
        }
        false_invariants = sorted(
            key for key, value in invariants.items() if value is not True
        )
        if false_invariants:
            raise RuntimeError(
                "FIFTH_SHORE_LIVING_FALSE_INVARIANTS: "
                + ", ".join(false_invariants)
            )

        summary = {
            "schema": (
                "janus.genesis.fifth_shore_living_bridge_summary.v1"
            ),
            "result": "PASS",
            "git_commit": git_commit,
            "seed": SEED,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "observer_extensions": list(OBSERVER_EXTENSION_VERSIONS),
            "vocation_extensions": list(VOCATION_EXTENSION_VERSIONS),
            "culture_extensions": list(CULTURE_EXTENSION_VERSIONS),
            "living_bridge_extension": (
                FIFTH_SHORE_LIVING_EXTENSION_VERSION
            ),
            "source_extension": INNER_GENESIS_EXTENSION_VERSION,
            "source_covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "living_covenant_sha256": (
                FIFTH_SHORE_LIVING_COVENANT_SHA256
            ),
            "integration_status": state["integration"]["status"],
            "ordinary_player_entry": state["ordinary_player_entry"],
            "participants": len(state["participants"]),
            "joy_events": len(state["joy_events"]),
            "repair_rehearsals": len(state["repair_rehearsals"]),
            "systemic_wounds": len(state["systemic_wounds"]),
            "memory_fragments": len(state["memory_fragments"]),
            "forks": len(state["forks"]),
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "integrity": integrity,
            "invariants": invariants,
            "claim_boundary": {
                "deterministic_software_and_narrative_simulation_only": True,
                "not_real_restitution_proof": True,
                "not_consciousness_or_personhood_claim": True,
                "not_supernatural_world_claim": True,
                "not_real_person_auteur_simulation": True,
            },
        }
        proofpack = {
            "schema": (
                "janus.genesis.fifth_shore_living_bridge_proofpack.v1"
            ),
            "summary_sha256": canonical_sha256(summary),
            "source_covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "living_covenant_sha256": (
                FIFTH_SHORE_LIVING_COVENANT_SHA256
            ),
            "entered": entered,
            "joy": joy,
            "rehearsal": rehearsal,
            "false_completion": false_completion,
            "wound": wound,
            "person_target_rejected": person_target_rejected,
            "memory_declined": memory_declined,
            "memory_shared": memory_shared,
            "memory_revoked": memory_revoked,
            "safe_fork": safe_fork,
            "unsafe_fork": unsafe_fork,
            "state_via_router": state_via_router,
            "leave": leave,
            "state": state,
            "integrity": integrity,
            "chronicle": summary["chronicle"],
            "invariants": invariants,
        }

        summary_path = (
            output_dir / "fifth_shore_living_bridge_summary.json"
        )
        proofpack_path = (
            output_dir / "fifth_shore_living_bridge_proofpack.json"
        )
        diary_path = output_dir / "FIFTH_SHORE_LIVING_BRIDGE_DIARY.md"
        manifest_path = (
            output_dir / "FIFTH_SHORE_LIVING_BRIDGE_MANIFEST.json"
        )
        zip_path = output_dir / "fifth_shore_living_bridge_proofpack.zip"

        write_json(summary_path, summary)
        write_json(proofpack_path, proofpack)

        diary_path.write_text(
            "\n".join(
                [
                    (
                        "# Genesis v18.7.17 — Пятый Берег внутри "
                        "основного Genesis"
                    ),
                    "",
                    f"Commit: `{git_commit}`",
                    f"Result: `{summary['result']}`",
                    "",
                    (
                        "Пятый Берег больше не является только вложенным "
                        "культурным"
                    ),
                    (
                        "экспериментом Второго Лика. Его происхождение "
                        "v18.7.16 сохранено,"
                    ),
                    (
                        "но мост v18.7.17 сделал его доступным обычному "
                        "игроку через"
                    ),
                    (
                        "основной `process_action` без царского титула."
                    ),
                    "",
                    "## Что было прожито",
                    "",
                    (
                        "- шесть обычных жителей вошли прямо из основной "
                        "жизни Genesis;"
                    ),
                    "- их базовый Realm не был заменён;",
                    (
                        "- радость состоялась без заявления о сломанности "
                        "или ремонте;"
                    ),
                    (
                        "- репетиция возмещения не была выдана за реальное "
                        "исправление;"
                    ),
                    (
                        "- системная рана стала противником, а человек — нет;"
                    ),
                    (
                        "- использование памяти было разрешено только "
                        "текущим согласием;"
                    ),
                    (
                        "- ранее данное согласие было отозвано без стирания "
                        "целостности;"
                    ),
                    "- безопасный локальный Берег был принят;",
                    "- закрытый единственный канон был отвергнут;",
                    (
                        "- игрок вышел, удалил локальную копию и сохранил "
                        "право вернуться."
                    ),
                    "",
                    "## Закон",
                    "",
                    (
                        "> ПЯТЫЙ БЕРЕГ ЖИВЁТ ВНУТРИ ОСНОВНОГО GENESIS."
                    ),
                    (
                        "> РАДОСТЬ НЕ ОБЯЗАНА НАЗЫВАТЬ СЕБЯ РЕМОНТОМ."
                    ),
                    (
                        "> РЕПЕТИЦИЯ НЕ ДОКАЗЫВАЕТ ВОЗМЕЩЕНИЕ."
                    ),
                    (
                        "> СИСТЕМЫ ВРЕДА МОГУТ БЫТЬ ПРОТИВНИКАМИ, НО "
                        "ЛЮДИ НЕ СТАНОВЯТСЯ МОНСТРАМИ."
                    ),
                    (
                        "> МНОГИЕ ФИНАЛЫ ЖИВУТ ПОД ОДНОЙ БЕЗОПАСНОЙ "
                        "КОНСТИТУЦИЕЙ."
                    ),
                    "",
                    "## Integrity",
                    "",
                    f"- valid: `{integrity['valid']}`",
                    f"- Chronicle valid: `{chronicle_valid}`",
                    f"- Chronicle events: `{chronicle_events}`",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        files = [summary_path, proofpack_path, diary_path]
        manifest = {
            "schema": (
                "janus.genesis.fifth_shore_living_bridge_manifest.v1"
            ),
            "git_commit": git_commit,
            "files": {
                path.name: {
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for path in files
            },
        }
        write_json(manifest_path, manifest)

        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in [*files, manifest_path]:
                archive.write(path, arcname=path.name)

        result = dict(summary)
        result["files"] = {
            "summary": str(summary_path),
            "proofpack": str(proofpack_path),
            "diary": str(diary_path),
            "manifest": str(manifest_path),
            "zip": str(zip_path),
        }
        result["file_hashes"] = {
            path.name: file_sha256(path)
            for path in [
                summary_path,
                proofpack_path,
                diary_path,
                manifest_path,
                zip_path,
            ]
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--git-commit",
        required=True,
    )
    args = parser.parse_args()
    result = run(args.output_dir, args.git_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
