from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .config import settings

DB_PATH: Path = settings.db_path


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('PRAGMA foreign_keys = ON;')
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_url TEXT UNIQUE NOT NULL,
                channel_id TEXT,
                title TEXT,
                last_checked DATETIME
            );

            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                video_id TEXT UNIQUE NOT NULL,
                title TEXT,
                published_at TEXT,
                views INTEGER,
                likes INTEGER,
                comments INTEGER,
                thumbnail_url TEXT,
                captions TEXT,
                fetched_at DATETIME,
                performance_score REAL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                strategy TEXT
            );

            CREATE TABLE IF NOT EXISTS batch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                channel_urls TEXT NOT NULL,
                channels_json TEXT NOT NULL,
                strategy_json TEXT NOT NULL,
                agent_steps_json TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                batch_id TEXT,
                topic_title TEXT NOT NULL,
                topic_summary TEXT,
                keywords TEXT NOT NULL DEFAULT '[]',
                reference_channels TEXT NOT NULL DEFAULT '[]',
                hypothesis TEXT,
                status TEXT NOT NULL DEFAULT 'suggested'
            );

            CREATE TABLE IF NOT EXISTS suggestion_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id TEXT NOT NULL,
                channel_id TEXT,
                video_id TEXT NOT NULL,
                video_title TEXT,
                matched_at TEXT NOT NULL,
                match_confidence REAL NOT NULL DEFAULT 0.0,
                views INTEGER,
                avg_views REAL,
                performance_score REAL,
                beat_average INTEGER DEFAULT 0,
                UNIQUE(suggestion_id, video_id)
            );

            CREATE TABLE IF NOT EXISTS learning_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                insight_text TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '{}'
            );
            """
        )


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_one(query: str, params: Iterable[Any] | dict[str, Any] = ()):  # type: ignore[type-var]
    with get_connection() as conn:
        cur = conn.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def query_all(query: str, params: Iterable[Any] | dict[str, Any] = ()):  # type: ignore[type-var]
    with get_connection() as conn:
        cur = conn.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def execute(query: str, params: Iterable[Any] | dict[str, Any] = ()):  # type: ignore[type-var]
    with get_connection() as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid
