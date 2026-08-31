# -*- coding: utf-8 -*-
"""Deterministic score planner for JANUS Genesis Audio Forge v1.

The planner is deliberately renderer-agnostic. It turns a bounded declarative
recipe + explicit world state + seed into a reproducible event plan. It does
not open audio devices, inspect the user, access the network, mutate gameplay,
or execute recipe-supplied code.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

SCHEMA = "janus.genesis.audio_recipe.v1"
GENERATOR = "GENESIS_AUDIO_FORGE_V1"
VERSION = "1.0.0"
STEPS_PER_BAR = 16
ALLOWED_WAVES = frozenset({"sine", "triangle", "square", "sawtooth"})
ALLOWED_WORLD_KEYS = frozenset({"entropy", "depth", "portal_energy", "danger", "weather_intensity"})
DEFAULT_PROGRESSION = (0, 4, 5, 3)
BASE_PULSE_STEPS = (0, 4, 8, 12)
BASE_BASS_STEPS = (0, 3, 6, 8, 11, 14)
STAR_STEPS = (5, 13)


class AudioForgeViolation(ValueError):
    """Raised when a recipe or world-state input violates Audio Forge laws."""


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AudioForgeViolation(f"Expected numeric value, got {value!r}") from exc
    if not math.isfinite(number):
        raise AudioForgeViolation("Non-finite audio parameter is forbidden")
    return max(minimum, min(maximum, number))


def _stable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _stable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_stable(value), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def hash32(value: int) -> int:
    value &= 0xFFFFFFFF
    value = (value + 0x7ED55D16 + ((value << 12) & 0xFFFFFFFF)) & 0xFFFFFFFF
    value = (value ^ 0xC761C23C ^ (value >> 19)) & 0xFFFFFFFF
    value = (value + 0x165667B1 + ((value << 5) & 0xFFFFFFFF)) & 0xFFFFFFFF
    value = (value + 0xD3A2646C) & 0xFFFFFFFF
    value = (value ^ ((value << 9) & 0xFFFFFFFF)) & 0xFFFFFFFF
    value = (value + 0xFD7046C5 + ((value << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    value = (value ^ 0xB55A4F09 ^ (value >> 16)) & 0xFFFFFFFF
    return value


def unit_rand(seed: int, bar: int, step: int, salt: int = 0) -> float:
    mixed = (
        (int(seed) & 0xFFFFFFFF)
        ^ (((bar + 1) * 0x9E3779B1) & 0xFFFFFFFF)
        ^ (((step + 1) * 0x85EBCA6B) & 0xFFFFFFFF)
        ^ (int(salt) & 0xFFFFFFFF)
    )
    return hash32(mixed) / 0xFFFFFFFF


def midi_to_hz(midi_note: int) -> float:
    return 440.0 * math.pow(2.0, (float(midi_note) - 69.0) / 12.0)


def _validate_int_list(value: Any, *, name: str, minimum: int, maximum: int, max_items: int) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)) or not value or len(value) > max_items:
        raise AudioForgeViolation(f"{name} must be a non-empty bounded array")
    out: list[int] = []
    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or int(raw) != raw:
            raise AudioForgeViolation(f"{name} entries must be integers")
        number = int(raw)
        if number < minimum or number > maximum:
            raise AudioForgeViolation(f"{name} entry out of range: {number}")
        out.append(number)
    return tuple(out)


def validate_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(recipe, Mapping):
        raise AudioForgeViolation("Audio recipe must be an object")
    if recipe.get("schema") != SCHEMA:
        raise AudioForgeViolation("Unsupported audio recipe schema")
    if recipe.get("generator") != GENERATOR:
        raise AudioForgeViolation("Unsupported audio generator")

    recipe_id = recipe.get("recipe_id")
    if not isinstance(recipe_id, str) or not recipe_id.startswith("genesis://audio/") or len(recipe_id) > 180:
        raise AudioForgeViolation("Invalid recipe_id")

    root_midi = int(_clamp(recipe.get("root_midi", 50), 24, 84))
    tempo_bpm = _clamp(recipe.get("tempo_bpm", 66), 36, 160)
    scale = _validate_int_list(recipe.get("scale"), name="scale", minimum=-24, maximum=24, max_items=16)
    motif = _validate_int_list(recipe.get("motif"), name="motif", minimum=-32, maximum=32, max_items=32)

    layers = recipe.get("layers")
    if not isinstance(layers, Mapping):
        raise AudioForgeViolation("layers must be an object")
    normalized_layers: dict[str, dict[str, Any]] = {}
    for name in ("pulse", "bass", "arp", "pad", "bells", "drone", "noise"):
        raw = layers.get(name, {})
        if not isinstance(raw, Mapping):
            raise AudioForgeViolation(f"layers.{name} must be an object")
        wave = str(raw.get("wave", "sine"))
        if wave not in ALLOWED_WAVES:
            raise AudioForgeViolation(f"Unsupported oscillator wave: {wave}")
        normalized_layers[name] = {
            "enabled": bool(raw.get("enabled", True)),
            "density": _clamp(raw.get("density", 0.5), 0.0, 1.0),
            "gain": _clamp(raw.get("gain", 0.03), 0.0001, 0.2),
            "wave": wave,
        }

    bindings = recipe.get("world_bindings", {})
    if not isinstance(bindings, Mapping):
        raise AudioForgeViolation("world_bindings must be an object")
    unknown_bindings = sorted(set(bindings) - ALLOWED_WORLD_KEYS)
    if unknown_bindings:
        raise AudioForgeViolation(f"Unsupported world bindings: {', '.join(unknown_bindings)}")

    return {
        "schema": SCHEMA,
        "generator": GENERATOR,
        "generator_version": str(recipe.get("generator_version", VERSION)),
        "recipe_id": recipe_id,
        "tempo_bpm": tempo_bpm,
        "root_midi": root_midi,
        "scale": scale,
        "motif": motif,
        "layers": normalized_layers,
        "world_bindings": {str(k): str(v) for k, v in bindings.items()},
    }


def normalize_world_state(world_state: Mapping[str, Any] | None) -> dict[str, float]:
    raw = world_state or {}
    if not isinstance(raw, Mapping):
        raise AudioForgeViolation("world_state must be an object")
    unknown = sorted(set(raw) - ALLOWED_WORLD_KEYS)
    if unknown:
        raise AudioForgeViolation(f"Hidden or unsupported world telemetry is forbidden: {', '.join(unknown)}")
    return {key: _clamp(raw.get(key, 0.0), 0.0, 1.0) for key in sorted(ALLOWED_WORLD_KEYS)}


def _mode_midi(recipe: Mapping[str, Any], degree: int, octave: int = 0) -> int:
    scale = tuple(recipe["scale"])
    length = len(scale)
    octave_shift, index = divmod(int(degree), length)
    return int(recipe["root_midi"]) + int(scale[index]) + 12 * (octave + octave_shift)


def _event(kind: str, step: int, **payload: Any) -> dict[str, Any]:
    return {"kind": kind, "step": int(step), **payload}


def plan_bar(
    recipe: Mapping[str, Any],
    *,
    seed: int,
    bar_index: int,
    world_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deterministic, renderer-independent 16-step score plan."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed > 0xFFFFFFFF:
        raise AudioForgeViolation("seed must be an unsigned 32-bit integer")
    if isinstance(bar_index, bool) or not isinstance(bar_index, int) or bar_index < 0:
        raise AudioForgeViolation("bar_index must be a non-negative integer")

    normalized = validate_recipe(recipe)
    world = normalize_world_state(world_state)
    layers = normalized["layers"]
    progression_root = DEFAULT_PROGRESSION[bar_index % len(DEFAULT_PROGRESSION)]

    entropy = world["entropy"]
    depth = world["depth"]
    portal = world["portal_energy"]
    danger = world["danger"]
    weather = world["weather_intensity"]
    tempo = _clamp(normalized["tempo_bpm"] + portal * 18.0 + danger * 10.0 - depth * 5.0, 36, 180)
    filter_hz = _clamp(2200.0 + entropy * 2400.0 + portal * 1300.0 - depth * 600.0, 500, 7600)
    register_shift = -1 if depth > 0.70 else (1 if portal > 0.82 else 0)

    events: list[dict[str, Any]] = []
    if layers["drone"]["enabled"]:
        events.append(_event("drone", 0, midi=_mode_midi(normalized, progression_root, -2 + register_shift), gain=layers["drone"]["gain"], wave=layers["drone"]["wave"]))

    if layers["pad"]["enabled"]:
        chord = [_mode_midi(normalized, progression_root + degree, -1 + register_shift) for degree in (0, 2, 4)]
        events.append(_event("pad", 0, midi=chord, gain=layers["pad"]["gain"], wave=layers["pad"]["wave"]))

    motif = tuple(normalized["motif"])
    for step in range(STEPS_PER_BAR):
        if layers["pulse"]["enabled"]:
            threshold = min(1.0, layers["pulse"]["density"] + danger * 0.18 + portal * 0.12)
            if step in BASE_PULSE_STEPS or unit_rand(seed, bar_index, step, 101) < threshold * 0.22:
                events.append(_event("pulse", step, gain=layers["pulse"]["gain"] * (1.0 + danger * 0.25), wave=layers["pulse"]["wave"]))

        if layers["bass"]["enabled"] and step in BASE_BASS_STEPS:
            threshold = min(1.0, layers["bass"]["density"] + danger * 0.15)
            if unit_rand(seed, bar_index, step, 202) < threshold:
                degree = progression_root + (0, 0, 2, 0, 4, 2)[BASE_BASS_STEPS.index(step)]
                events.append(_event("bass", step, midi=_mode_midi(normalized, degree, -2 + register_shift), gain=layers["bass"]["gain"], wave=layers["bass"]["wave"]))

        if layers["arp"]["enabled"] and step % 2 == 1:
            threshold = min(1.0, layers["arp"]["density"] + portal * 0.22 + entropy * 0.10)
            if unit_rand(seed, bar_index, step, 303) < threshold:
                degree = progression_root + motif[(step // 2 + bar_index) % len(motif)]
                events.append(_event("arp", step, midi=_mode_midi(normalized, degree, register_shift), gain=layers["arp"]["gain"], wave=layers["arp"]["wave"], pan=round(unit_rand(seed, bar_index, step, 304) * 1.4 - 0.7, 6)))

        if layers["bells"]["enabled"] and step in STAR_STEPS:
            threshold = min(1.0, layers["bells"]["density"] + portal * 0.25)
            if unit_rand(seed, bar_index, step, 404) < threshold:
                degree = progression_root + motif[(step + bar_index) % len(motif)] + 4
                events.append(_event("bell", step, midi=_mode_midi(normalized, degree, 1 + register_shift), gain=layers["bells"]["gain"], wave=layers["bells"]["wave"], pan=(-0.55 if step < 8 else 0.55)))

        if layers["noise"]["enabled"]:
            threshold = min(1.0, layers["noise"]["density"] * 0.25 + weather * 0.42 + entropy * 0.08)
            if unit_rand(seed, bar_index, step, 505) < threshold:
                events.append(_event("noise", step, gain=layers["noise"]["gain"] * (0.5 + weather * 0.8), cutoff_hz=round(filter_hz + weather * 900.0, 3)))

    plan: dict[str, Any] = {
        "schema": "janus.genesis.audio_score_plan.v1",
        "generator": GENERATOR,
        "generator_version": VERSION,
        "recipe_id": normalized["recipe_id"],
        "recipe_sha256": sha256_hex(normalized),
        "seed": seed,
        "bar_index": bar_index,
        "steps_per_bar": STEPS_PER_BAR,
        "tempo_bpm": round(tempo, 6),
        "filter_hz": round(filter_hz, 3),
        "world_state": world,
        "events": events,
        "authority": {
            "presentation_only": True,
            "world_mutation": False,
            "hidden_human_telemetry": False,
            "network_access": False,
            "arbitrary_code_execution": False,
        },
    }
    plan["plan_sha256"] = sha256_hex(plan)
    return plan


LAWS = (
    "AUDIO_RECIPE_NE_ARBITRARY_CODE",
    "GENERATED_AUDIO_NE_STORED_TRACK",
    "SOUND_PRESENTATION_NE_WORLD_AUTHORITY",
    "WORLD_STATE_TO_AUDIO_ALLOWED",
    "AUDIO_TO_WORLD_MUTATION_DEFAULT_DENY",
    "HIDDEN_HUMAN_TELEMETRY_FORBIDDEN",
    "USER_GESTURE_REQUIRED_FOR_BROWSER_AUDIO",
    "SAME_RECIPE_SEED_VERSION_EQ_SAME_SCORE_PLAN",
    "RENDERER_NE_RECIPE",
    "PROVENANCE_SURVIVES_EXTRACTION",
)
