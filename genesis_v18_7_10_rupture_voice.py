# -*- coding: utf-8 -*-
"""Stable dynamic voice for terminal Free Other relationship ruptures."""
from __future__ import annotations

from typing import Any


class RuptureVoiceIntegrityMixin:
    """Use present-tense constructions without inferring gender from a name."""

    def _terminate_free_other_relationship(
        self,
        store: dict[str, Any],
        player_id: str,
        profile: dict[str, Any],
        actor: dict[str, Any],
        *,
        reason_code: str,
        reason_text: str,
        source_conflicts: list[dict[str, Any]],
    ) -> str:
        del reason_text
        latest = source_conflicts[-1] if source_conflicts else {}
        other_position = str(latest.get("other_position") or "собственную позицию")
        stable_reason = (
            f"{actor['name']} сохраняет собственную позицию «{other_position}» "
            "и завершает связь, не прекращая собственный путь."
        )
        return super()._terminate_free_other_relationship(
            store,
            player_id,
            profile,
            actor,
            reason_code=reason_code,
            reason_text=stable_reason,
            source_conflicts=source_conflicts,
        )
