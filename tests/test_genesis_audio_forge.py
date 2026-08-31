from __future__ import annotations

import copy

import pytest

from genesis_audio_forge import AudioForgeViolation, plan_bar, validate_recipe


def recipe():
    return {
        "schema": "janus.genesis.audio_recipe.v1",
        "generator": "GENESIS_AUDIO_FORGE_V1",
        "generator_version": "1.0.0",
        "recipe_id": "genesis://audio/biome/liminal-hall/v1",
        "tempo_bpm": 66,
        "root_midi": 50,
        "scale": [0, 2, 4, 6, 7, 9, 11],
        "motif": [0, 4, 2, 5, 1, 6, 4, 2],
        "layers": {
            "pulse": {"enabled": True, "density": 0.42, "gain": 0.03, "wave": "sine"},
            "bass": {"enabled": True, "density": 0.58, "gain": 0.045, "wave": "triangle"},
            "arp": {"enabled": True, "density": 0.70, "gain": 0.024, "wave": "triangle"},
            "pad": {"enabled": True, "density": 1, "gain": 0.020, "wave": "sine"},
            "bells": {"enabled": True, "density": 0.38, "gain": 0.018, "wave": "sine"},
            "drone": {"enabled": True, "density": 1, "gain": 0.012, "wave": "sine"},
            "noise": {"enabled": True, "density": 0.22, "gain": 0.009, "wave": "sine"}
        },
        "world_bindings": {
            "entropy": "filter_cutoff",
            "depth": "register",
            "portal_energy": "tempo_and_register",
            "danger": "pulse_density",
            "weather_intensity": "noise_texture"
        }
    }


def test_same_recipe_seed_and_world_produce_same_plan():
    world = {"entropy": .25, "depth": .4, "portal_energy": .7, "danger": .2, "weather_intensity": .1}
    first = plan_bar(recipe(), seed=883105, bar_index=9, world_state=world)
    second = plan_bar(recipe(), seed=883105, bar_index=9, world_state=world)
    assert first == second
    assert first["plan_sha256"] == second["plan_sha256"]


def test_seed_changes_score_plan_without_changing_recipe_identity():
    first = plan_bar(recipe(), seed=1, bar_index=0)
    second = plan_bar(recipe(), seed=2, bar_index=0)
    assert first["recipe_sha256"] == second["recipe_sha256"]
    assert first["plan_sha256"] != second["plan_sha256"]


def test_world_modulation_is_bounded_and_presentation_only():
    calm = plan_bar(recipe(), seed=7, bar_index=0, world_state={"portal_energy": 0, "danger": 0, "entropy": 0, "depth": 0, "weather_intensity": 0})
    portal = plan_bar(recipe(), seed=7, bar_index=0, world_state={"portal_energy": 1, "danger": 1, "entropy": 1, "depth": 0, "weather_intensity": 1})
    assert portal["tempo_bpm"] > calm["tempo_bpm"]
    assert portal["filter_hz"] >= calm["filter_hz"]
    assert portal["authority"]["world_mutation"] is False
    assert portal["authority"]["hidden_human_telemetry"] is False


def test_recipe_rejects_arbitrary_or_unsupported_oscillator_type():
    broken = copy.deepcopy(recipe())
    broken["layers"]["arp"]["wave"] = "eval(js)"
    with pytest.raises(AudioForgeViolation, match="Unsupported oscillator wave"):
        validate_recipe(broken)


def test_hidden_or_unapproved_telemetry_is_rejected():
    with pytest.raises(AudioForgeViolation, match="telemetry"):
        plan_bar(recipe(), seed=1, bar_index=0, world_state={"player_fear_score": 0.9})


def test_seed_and_bar_index_are_strictly_bounded():
    with pytest.raises(AudioForgeViolation, match="unsigned 32-bit"):
        plan_bar(recipe(), seed=-1, bar_index=0)
    with pytest.raises(AudioForgeViolation, match="non-negative"):
        plan_bar(recipe(), seed=1, bar_index=-1)
