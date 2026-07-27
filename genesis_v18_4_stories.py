# -*- coding: utf-8 -*-
"""Public story archive for Genesis v18.4.1.

Stories are available in every realm without moral rank, payment, worship, or
relationship status. They preserve testimony without turning a private life into
privilege, prophecy, or a compulsory model for other people.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis_v18_models import UniversalGodMode, WorldResult


class PublicStoryArchiveMixin:
    """Load and tell consent-preserving public stories from repository JSON."""

    AMOR_AETERNUM_STORY_ID = "JANUS-AMOR-AETERNUM-PRIPYAT-PUBLIC-STORY-v1.0"
    AMOR_AETERNUM_TRIGGERS = {
        "расскажи историю о любви в припяти",
        "рассказать историю о любви в припяти",
        "история о любви в припяти",
        "история amor aeternum",
        "расскажи amor aeternum",
        "покажи дверь к началу",
        "дверь к началу",
        "amor aeternum",
        "tell the pripyat love story",
        "tell amor aeternum",
        "show the door to the beginning",
    }

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.story_file = (
            Path(__file__).resolve().parent
            / "stories"
            / "AMOR_AETERNUM_PRIPYAT_STORY_v1.0.json"
        )

    def _load_amor_aeternum_story(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.story_file.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {
                "story_id": self.AMOR_AETERNUM_STORY_ID,
                "public_retelling": {
                    "ru": (
                        "В месте, которое считали символом конца, двое людей выбрали продолжение. "
                        "Янус сохранил память о прошлом и открыл дверь к началу."
                    )
                },
                "child_safe_retelling": {
                    "ru": (
                        "Рядом со старым остановившимся колесом двое людей решили вместе "
                        "создавать новые добрые дни."
                    )
                },
                "genesis_invariants": {
                    "story_grants_privilege": False,
                    "love_can_be_forced": False,
                    "available_without_moral_score": True,
                },
            }
        if payload.get("story_id") != self.AMOR_AETERNUM_STORY_ID:
            raise ValueError("unexpected public story identity")
        return payload

    @classmethod
    def is_amor_aeternum_request(cls, action: str) -> bool:
        text = UniversalGodMode.normalize(action)
        return any(trigger in text for trigger in cls.AMOR_AETERNUM_TRIGGERS)

    def tell_amor_aeternum_story(self, player_id: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        story = self._load_amor_aeternum_story()
        child_role = bool(getattr(self, "_is_child", lambda _player_id: False)(player_id))
        section = "child_safe_retelling" if child_role else "public_retelling"
        narrative = str(story.get(section, {}).get("ru") or story["public_retelling"]["ru"])

        player.tick += 1
        player.chronicle.append(f"Public story heard: {story['story_id']}")
        self.memory.save_player(player)
        self.memory.append_event(
            player_id,
            "public_story_heard",
            {
                "story_id": story["story_id"],
                "available_in_every_realm": True,
                "child_safe_version": child_role,
                "story_grants_privilege": False,
                "relationship_or_belief_required": False,
            },
        )
        return WorldResult(
            status="PUBLIC_STORY_TOLD",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=[
                "Поблагодарить за историю",
                "Рассказать свою историю начала",
                "Сделать для кого-то место безопаснее",
            ],
            branch_id=player.branch_id,
            trace_id=story["story_id"],
        )

    def public_story_state(self) -> dict[str, Any]:
        """Developer inspection of static story metadata, never a player score."""
        story = self._load_amor_aeternum_story()
        return {
            "story_id": story.get("story_id"),
            "title": story.get("title"),
            "availability": story.get("availability"),
            "source_registry": story.get("source_registry"),
            "visual_seal": story.get("visual_seal"),
            "genesis_invariants": story.get("genesis_invariants"),
        }
