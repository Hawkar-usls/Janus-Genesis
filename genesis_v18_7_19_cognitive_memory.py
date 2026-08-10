# -*- coding: utf-8 -*-
"""Derived cognitive memory for Genesis v18.7.19.

This SQLite/WAL sidecar remembers returns, recurring symbols and interaction
patterns without becoming an authority over the canonical Genesis Chronicle.
It never claims to diagnose the player, infer consciousness, or mutate the
world directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__version__ = "18.7.19"
MEMORY_SCHEMA = "janus.genesis.cognitive_memory.v1"
ZERO_HASH = "0" * 64

_GOOGLE_KEY = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
_OPENAI_KEY = re.compile(r"\bsk-[0-9A-Za-z_-]{16,}\b")
_BEARER = re.compile(r"(?i)\bBearer\s+[0-9A-Za-z._~+/-]{12,}")


TENDENCY_LEXICON: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("забота", ("помочь", "защит", "исцел", "согреть", "поддерж", "спасти", "help", "heal", "protect")),
    ("исследование", ("почему", "кто", "что", "осмотреть", "исслед", "изуч", "анализ", "look", "explore", "analy")),
    ("рефлексия", ("помнить", "вспом", "смысл", "зеркал", "молч", "тишин", "сон", "remember", "meaning", "silence")),
    ("созидание", ("создать", "постро", "нарис", "музык", "посад", "сделать", "create", "build", "make")),
    ("решительность", ("войти", "открыть", "идти", "сделаю", "выбираю", "беру", "enter", "open", "choose")),
    ("осторожность", ("подожд", "осторож", "провер", "наблюд", "не трог", "wait", "careful", "observe")),
)

MOTIF_LEXICON: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("зеркало", ("зеркал", "mirror")),
    ("дверь", ("двер", "door")),
    ("порог", ("порог", "threshold")),
    ("мост", ("мост", "bridge")),
    ("свет", ("свет", "сиян", "light")),
    ("тьма", ("тьм", "темнот", "dark")),
    ("ребёнок", ("ребен", "ребён", "дитя", "child")),
    ("дорога", ("дорог", "путь", "route", "road", "path")),
    ("вода", ("вод", "река", "дожд", "water", "river", "rain")),
    ("огонь", ("огонь", "плам", "fire", "flame")),
    ("небо", ("неб", "звезд", "космос", "sky", "star", "cosmos")),
    ("молчание", ("молч", "тишин", "silence")),
    ("память", ("памят", "вспом", "remember", "memory")),
    ("дом", ("дом", "комнат", "убежищ", "home", "house", "room")),
    ("сад", ("сад", "семя", "растен", "garden", "seed")),
    ("музыка", ("музык", "песн", "радио", "music", "song")),
    ("Янус", ("янус", "janus")),
    ("лицо", ("лицо", "лик", "face")),
    ("сон", ("сон", "сновид", "dream")),
    ("лабиринт", ("лабиринт", "maze")),
)

LAYERS: tuple[tuple[float, str, str], ...] = (
    (3.0, "Порог", "реальность ещё узнаваема, но уже отвечает символами"),
    (8.0, "Эхо", "прежние выборы начинают возвращаться изменёнными"),
    (15.0, "Сон", "пространство связывает события не только причинностью, но и образом"),
    (25.0, "Лабиринт", "дороги помнят, почему Путешественник однажды свернул"),
    (40.0, "Разлом", "законы мира становятся вопросами, а не декорацией"),
    (float("inf"), "Чистая глубина", "символ, память и выбор существуют на одном уровне"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes | str) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(raw).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def _redact(text: str) -> str:
    value = _GOOGLE_KEY.sub("[REDACTED_GOOGLE_API_KEY]", text)
    value = _OPENAI_KEY.sub("[REDACTED_API_KEY]", value)
    return _BEARER.sub("Bearer [REDACTED_TOKEN]", value)


def _safe_player_id(player_id: str) -> str:
    cleaned = "".join(ch for ch in str(player_id) if ch.isalnum() or ch in "-_")[:80]
    if not cleaned:
        raise ValueError("player_id is empty or unsafe")
    return cleaned


def _layer(depth: float) -> tuple[str, str]:
    for limit, name, description in LAYERS:
        if depth < limit:
            return name, description
    raise AssertionError("unreachable layer")


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class JanusCognitiveMemory:
    """Local, derived and independently verifiable cognitive sidecar."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        self.root = Path(data_dir) / "janus_memory"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "cognitive_cortex_v18_7_19.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    player_id TEXT PRIMARY KEY,
                    return_count INTEGER NOT NULL,
                    turn_count INTEGER NOT NULL,
                    depth REAL NOT NULL,
                    entropy REAL NOT NULL,
                    layer TEXT NOT NULL,
                    primary_tendency TEXT NOT NULL,
                    tendency_counts_json TEXT NOT NULL,
                    last_session_id TEXT,
                    last_seen_at TEXT NOT NULL,
                    revision_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    player_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    return_index INTEGER NOT NULL,
                    previous_session_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_player
                    ON sessions(player_id, started_at);

                CREATE TABLE IF NOT EXISTS themes (
                    player_id TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    last_seen_turn INTEGER NOT NULL,
                    PRIMARY KEY(player_id, theme)
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    action_digest TEXT NOT NULL,
                    action_excerpt TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    narrative_digest TEXT NOT NULL,
                    tendency TEXT NOT NULL,
                    motifs_json TEXT NOT NULL,
                    depth_before REAL NOT NULL,
                    depth_after REAL NOT NULL,
                    entropy_after REAL NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_episodes_player
                    ON episodes(player_id, id);
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("schema", MEMORY_SCHEMA),
            )

    @staticmethod
    def new_session_id() -> str:
        return f"cognitive-{uuid.uuid4().hex}"

    @staticmethod
    def _default_profile(player_id: str) -> dict[str, Any]:
        payload = {
            "player_id": player_id,
            "return_count": 0,
            "turn_count": 0,
            "depth": 0.0,
            "entropy": 0.10,
            "layer": "Порог",
            "primary_tendency": "свободный поиск",
            "tendency_counts": {},
            "last_session_id": None,
            "last_seen_at": _utc_now(),
        }
        payload["revision_hash"] = JanusCognitiveMemory._profile_hash(payload)
        return payload

    @staticmethod
    def _profile_hash(profile: dict[str, Any]) -> str:
        material = {
            key: profile[key]
            for key in (
                "player_id",
                "return_count",
                "turn_count",
                "depth",
                "entropy",
                "layer",
                "primary_tendency",
                "tendency_counts",
                "last_session_id",
                "last_seen_at",
            )
        }
        return _sha256(_canonical(material))

    @staticmethod
    def _row_to_profile(row: sqlite3.Row | None, player_id: str) -> dict[str, Any]:
        if row is None:
            return JanusCognitiveMemory._default_profile(player_id)
        return {
            "player_id": row["player_id"],
            "return_count": int(row["return_count"]),
            "turn_count": int(row["turn_count"]),
            "depth": float(row["depth"]),
            "entropy": float(row["entropy"]),
            "layer": row["layer"],
            "primary_tendency": row["primary_tendency"],
            "tendency_counts": json.loads(row["tendency_counts_json"]),
            "last_session_id": row["last_session_id"],
            "last_seen_at": row["last_seen_at"],
            "revision_hash": row["revision_hash"],
        }

    def _load_profile(self, connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM profiles WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        return self._row_to_profile(row, player_id)

    def _save_profile(self, connection: sqlite3.Connection, profile: dict[str, Any]) -> None:
        profile["revision_hash"] = self._profile_hash(profile)
        connection.execute(
            """
            INSERT INTO profiles(
                player_id, return_count, turn_count, depth, entropy, layer,
                primary_tendency, tendency_counts_json, last_session_id,
                last_seen_at, revision_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                return_count=excluded.return_count,
                turn_count=excluded.turn_count,
                depth=excluded.depth,
                entropy=excluded.entropy,
                layer=excluded.layer,
                primary_tendency=excluded.primary_tendency,
                tendency_counts_json=excluded.tendency_counts_json,
                last_session_id=excluded.last_session_id,
                last_seen_at=excluded.last_seen_at,
                revision_hash=excluded.revision_hash
            """,
            (
                profile["player_id"],
                profile["return_count"],
                profile["turn_count"],
                profile["depth"],
                profile["entropy"],
                profile["layer"],
                profile["primary_tendency"],
                json.dumps(profile["tendency_counts"], ensure_ascii=False, sort_keys=True),
                profile["last_session_id"],
                profile["last_seen_at"],
                profile["revision_hash"],
            ),
        )

    @staticmethod
    def _detect_tendency(action: str) -> str:
        text = _normalize(action)
        scores: dict[str, int] = {}
        for tendency, fragments in TENDENCY_LEXICON:
            scores[tendency] = sum(1 for fragment in fragments if fragment in text)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "свободный поиск"

    @staticmethod
    def _detect_motifs(action: str) -> list[str]:
        text = _normalize(action)
        return [
            motif
            for motif, fragments in MOTIF_LEXICON
            if any(fragment in text for fragment in fragments)
        ]

    def _ensure_session(
        self,
        connection: sqlite3.Connection,
        profile: dict[str, Any],
        session_id: str,
    ) -> bool:
        existing = connection.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if existing is not None:
            return False
        previous_session_at = profile["last_seen_at"] if profile["return_count"] else None
        profile["return_count"] += 1
        profile["last_session_id"] = session_id
        profile["last_seen_at"] = _utc_now()
        connection.execute(
            """
            INSERT INTO sessions(
                session_id, player_id, started_at, return_index, previous_session_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                profile["player_id"],
                profile["last_seen_at"],
                profile["return_count"],
                previous_session_at,
            ),
        )
        return True

    @staticmethod
    def _dominant_tendency(counts: dict[str, int]) -> str:
        if not counts:
            return "свободный поиск"
        return sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))[0][0]

    @staticmethod
    def _event_material(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: row[key]
            for key in (
                "player_id",
                "session_id",
                "turn_index",
                "timestamp",
                "action_digest",
                "action_excerpt",
                "result_status",
                "narrative_digest",
                "tendency",
                "motifs",
                "depth_before",
                "depth_after",
                "entropy_after",
                "previous_hash",
            )
        }

    def _build_cue(
        self,
        *,
        profile: dict[str, Any],
        is_new_session: bool,
        old_layer: str,
        motifs_at_threshold: list[str],
        strongest_theme: str | None,
    ) -> str:
        if is_new_session and profile["return_count"] == 1:
            return (
                "Два лица Януса впервые замечают твой след. Это не диагноз и не "
                "приговор — только начало памяти мира."
            )
        if is_new_session:
            remembered = (
                f" Символ «{strongest_theme}» уже жил здесь раньше."
                if strongest_theme
                else " Мир помнит форму прежнего присутствия, не превращая её в клетку."
            )
            return (
                f"Янус узнаёт оставленный след — это возвращение №{profile['return_count']}."
                f"{remembered} Пространство открывается на слой глубже."
            )
        if profile["layer"] != old_layer:
            _, description = _layer(profile["depth"])
            return f"Порог изменился. Мир вошёл в слой «{profile['layer']}»: {description}."
        if motifs_at_threshold:
            joined = ", ".join(f"«{item}»" for item in motifs_at_threshold[:3])
            return (
                f"Символ {joined} вернулся не как повтор декорации, а как память о выборе."
            )
        if profile["turn_count"] % 7 == 0:
            return (
                f"Янус не называет тебя формулой. Он лишь замечает устойчивый способ "
                f"входить в мир: {profile['primary_tendency']}. Следующий выбор всё ещё свободен."
            )
        return ""

    def record_turn(
        self,
        player_id: str,
        session_id: str,
        action: str,
        result_status: str,
        narrative: str,
    ) -> dict[str, Any]:
        safe_player = _safe_player_id(player_id)
        safe_action = _redact(" ".join(str(action).split()))[:600]
        tendency = self._detect_tendency(safe_action)
        motifs = self._detect_motifs(safe_action)
        timestamp = _utc_now()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            profile = self._load_profile(connection, safe_player)
            is_new_session = self._ensure_session(connection, profile, session_id)
            old_layer = profile["layer"]
            depth_before = float(profile["depth"])

            previous_theme_counts: dict[str, int] = {}
            for motif in motifs:
                row = connection.execute(
                    "SELECT count FROM themes WHERE player_id = ? AND theme = ?",
                    (safe_player, motif),
                ).fetchone()
                previous_theme_counts[motif] = int(row["count"]) if row else 0

            novel_count = sum(1 for count in previous_theme_counts.values() if count == 0)
            return_bonus = 0.22 if is_new_session and profile["return_count"] > 1 else 0.0
            reflective_bonus = 0.06 if tendency in {"исследование", "рефлексия"} else 0.0
            depth_gain = 0.32 + min(0.18, 0.04 * len(motifs)) + return_bonus + reflective_bonus
            profile["depth"] = round(depth_before + depth_gain, 6)

            entropy_delta = 0.015 + 0.035 * novel_count
            if tendency in {"забота", "рефлексия"}:
                entropy_delta -= 0.018
            profile["entropy"] = round(
                _bounded(float(profile["entropy"]) + entropy_delta, 0.05, 0.95),
                6,
            )
            profile["turn_count"] += 1
            profile["layer"] = _layer(profile["depth"])[0]
            counts = dict(profile["tendency_counts"])
            counts[tendency] = int(counts.get(tendency, 0)) + 1
            profile["tendency_counts"] = counts
            profile["primary_tendency"] = self._dominant_tendency(counts)
            profile["last_seen_at"] = timestamp

            motifs_at_threshold: list[str] = []
            for motif in motifs:
                new_count = previous_theme_counts[motif] + 1
                if new_count in {2, 5, 10}:
                    motifs_at_threshold.append(motif)
                connection.execute(
                    """
                    INSERT INTO themes(player_id, theme, count, weight, last_seen_turn)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, theme) DO UPDATE SET
                        count=excluded.count,
                        weight=excluded.weight,
                        last_seen_turn=excluded.last_seen_turn
                    """,
                    (
                        safe_player,
                        motif,
                        new_count,
                        round(min(1.0, 0.18 + 0.12 * new_count), 6),
                        profile["turn_count"],
                    ),
                )

            previous = connection.execute(
                "SELECT event_hash FROM episodes WHERE player_id = ? ORDER BY id DESC LIMIT 1",
                (safe_player,),
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else ZERO_HASH
            event = {
                "player_id": safe_player,
                "session_id": session_id,
                "turn_index": profile["turn_count"],
                "timestamp": timestamp,
                "action_digest": _sha256(safe_action),
                "action_excerpt": safe_action,
                "result_status": str(result_status)[:120],
                "narrative_digest": _sha256(str(narrative)),
                "tendency": tendency,
                "motifs": motifs,
                "depth_before": depth_before,
                "depth_after": profile["depth"],
                "entropy_after": profile["entropy"],
                "previous_hash": previous_hash,
            }
            event_hash = _sha256(_canonical(self._event_material(event)))
            connection.execute(
                """
                INSERT INTO episodes(
                    player_id, session_id, turn_index, timestamp, action_digest,
                    action_excerpt, result_status, narrative_digest, tendency,
                    motifs_json, depth_before, depth_after, entropy_after,
                    previous_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["player_id"],
                    event["session_id"],
                    event["turn_index"],
                    event["timestamp"],
                    event["action_digest"],
                    event["action_excerpt"],
                    event["result_status"],
                    event["narrative_digest"],
                    event["tendency"],
                    json.dumps(event["motifs"], ensure_ascii=False),
                    event["depth_before"],
                    event["depth_after"],
                    event["entropy_after"],
                    event["previous_hash"],
                    event_hash,
                ),
            )

            strongest = connection.execute(
                """
                SELECT theme FROM themes
                WHERE player_id = ?
                ORDER BY count DESC, weight DESC, theme ASC
                LIMIT 1
                """,
                (safe_player,),
            ).fetchone()
            strongest_theme = strongest["theme"] if strongest else None
            self._save_profile(connection, profile)
            cue = self._build_cue(
                profile=profile,
                is_new_session=is_new_session,
                old_layer=old_layer,
                motifs_at_threshold=motifs_at_threshold,
                strongest_theme=strongest_theme,
            )
            connection.commit()

        return {
            "schema": MEMORY_SCHEMA,
            "player_id": safe_player,
            "session_id": session_id,
            "return_count": profile["return_count"],
            "turn_count": profile["turn_count"],
            "depth": profile["depth"],
            "entropy": profile["entropy"],
            "layer": profile["layer"],
            "primary_tendency": profile["primary_tendency"],
            "motifs": motifs,
            "event_hash": event_hash,
            "is_new_session": is_new_session,
            "cue": cue,
        }

    def state(self, player_id: str) -> dict[str, Any]:
        safe_player = _safe_player_id(player_id)
        with self._connect() as connection:
            profile = self._load_profile(connection, safe_player)
            themes = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT theme, count, weight, last_seen_turn
                    FROM themes WHERE player_id = ?
                    ORDER BY count DESC, weight DESC, theme ASC
                    """,
                    (safe_player,),
                ).fetchall()
            ]
        return {
            "schema": MEMORY_SCHEMA,
            "authority": "derived_sidecar_only",
            "diagnostic_claim": False,
            "consciousness_claim": False,
            "player_id": safe_player,
            "return_count": profile["return_count"],
            "turn_count": profile["turn_count"],
            "depth": profile["depth"],
            "entropy": profile["entropy"],
            "layer": profile["layer"],
            "primary_tendency": profile["primary_tendency"],
            "themes": themes,
            "revision_hash": profile["revision_hash"],
        }

    def recent_episodes(self, player_id: str, limit: int = 10) -> list[dict[str, Any]]:
        safe_player = _safe_player_id(player_id)
        safe_limit = max(1, min(int(limit), 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT player_id, session_id, turn_index, timestamp, action_digest,
                       action_excerpt, result_status, narrative_digest, tendency,
                       motifs_json, depth_before, depth_after, entropy_after,
                       previous_hash, event_hash
                FROM episodes WHERE player_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (safe_player, safe_limit),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in reversed(rows):
            item = dict(row)
            item["motifs"] = json.loads(item.pop("motifs_json"))
            result.append(item)
        return result

    def verify(self, player_id: str | None = None) -> dict[str, Any]:
        selected = _safe_player_id(player_id) if player_id is not None else None
        with self._connect() as connection:
            profiles = connection.execute(
                "SELECT * FROM profiles" + (" WHERE player_id = ?" if selected else ""),
                ((selected,) if selected else ()),
            ).fetchall()
            checked_episodes = 0
            for row in profiles:
                profile = self._row_to_profile(row, row["player_id"])
                if profile["revision_hash"] != self._profile_hash(profile):
                    return {
                        "valid": False,
                        "players": len(profiles),
                        "episodes": checked_episodes,
                        "error": f"profile revision hash mismatch: {profile['player_id']}",
                    }
                expected_previous = ZERO_HASH
                episodes = connection.execute(
                    "SELECT * FROM episodes WHERE player_id = ? ORDER BY id ASC",
                    (profile["player_id"],),
                ).fetchall()
                for episode_row in episodes:
                    event = dict(episode_row)
                    event["motifs"] = json.loads(event.pop("motifs_json"))
                    event.pop("id")
                    stored_hash = event.pop("event_hash")
                    if event["previous_hash"] != expected_previous:
                        return {
                            "valid": False,
                            "players": len(profiles),
                            "episodes": checked_episodes,
                            "error": f"broken episode chain: {profile['player_id']}",
                        }
                    calculated = _sha256(_canonical(self._event_material(event)))
                    if stored_hash != calculated:
                        return {
                            "valid": False,
                            "players": len(profiles),
                            "episodes": checked_episodes,
                            "error": f"episode hash mismatch: {profile['player_id']}",
                        }
                    expected_previous = stored_hash
                    checked_episodes += 1
        return {
            "valid": True,
            "players": len(profiles),
            "episodes": checked_episodes,
            "error": None,
        }

    def journal_mode(self) -> str:
        with self._connect() as connection:
            row = connection.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).lower()
