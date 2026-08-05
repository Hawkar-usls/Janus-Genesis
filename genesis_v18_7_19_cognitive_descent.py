# -*- coding: utf-8 -*-
"""Genesis v18.7.19 — Cognitive Descent.

The extension wraps the current authoritative Genesis runtime with a derived
Janus Memory sidecar. The sidecar may deepen narration, but it cannot approve,
reject or mutate an action and cannot replace the canonical Chronicle.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from genesis_v18_7_19_cognitive_memory import JanusCognitiveMemory
from genesis_v18_7_playable import PlayableGenesisV187

__version__ = "18.7.19"
COGNITIVE_DESCENT_VERSION = __version__


class PlayableGenesisV18719(PlayableGenesisV187):
    """Current Genesis gameplay plus local return-aware cognitive depth."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.cognitive_memory = JanusCognitiveMemory(data_dir)
        self.cognitive_session_id = self.cognitive_memory.new_session_id()
        self._cognitive_last_error: str | None = None

    def process_action(self, player_id: str, action: str):
        # The authoritative runtime always acts first. Cognitive memory can only
        # observe the already-decided result and decorate its narrative.
        result = super().process_action(player_id, action)
        try:
            observation = self.cognitive_memory.record_turn(
                player_id,
                self.cognitive_session_id,
                action,
                result.status,
                result.narrative,
            )
            self._cognitive_last_error = None
        except Exception as exc:  # derived memory must never block the world
            self._cognitive_last_error = f"{type(exc).__name__}: {exc}"
            return result

        cue = str(observation.get("cue", "")).strip()
        if not cue:
            return result
        return replace(result, narrative=f"{result.narrative}\n\n🜂 {cue}")

    def cognitive_state(self, player_id: str) -> dict[str, Any]:
        payload = self.cognitive_memory.state(player_id)
        payload["runtime_extension"] = COGNITIVE_DESCENT_VERSION
        payload["last_sidecar_error"] = self._cognitive_last_error
        return payload

    def verify_cognitive_memory(self, player_id: str | None = None) -> dict[str, Any]:
        payload = self.cognitive_memory.verify(player_id)
        payload["runtime_extension"] = COGNITIVE_DESCENT_VERSION
        payload["canonical_world_authority"] = False
        return payload

    def public_state(self, player_id: str) -> dict[str, Any]:
        payload = super().public_state(player_id)
        cognitive = self.cognitive_memory.state(player_id)
        payload["cognitive_descent"] = {
            "version": COGNITIVE_DESCENT_VERSION,
            "layer": cognitive["layer"],
            "returns": cognitive["return_count"],
            "depth": cognitive["depth"],
            "authority": cognitive["authority"],
        }
        return payload

    def internal_state(self, player_id: str) -> dict[str, Any]:
        payload = super().internal_state(player_id)
        payload["cognitive_descent"] = self.cognitive_state(player_id)
        return payload
