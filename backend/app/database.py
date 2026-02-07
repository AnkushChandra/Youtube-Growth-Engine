from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import psycopg2
import psycopg2.extras

from .config import settings

DATABASE_URL: str = settings.database_url


def init_db() -> None:
    with _raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                channel_url TEXT UNIQUE NOT NULL,
                channel_id TEXT,
                title TEXT,
                last_checked TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                video_id TEXT UNIQUE NOT NULL,
                title TEXT,
                published_at TEXT,
                views INTEGER,
                likes INTEGER,
                comments INTEGER,
                thumbnail_url TEXT,
                captions TEXT,
                fetched_at TIMESTAMP,
                performance_score REAL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                strategy TEXT
            );

            CREATE TABLE IF NOT EXISTS batch_history (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
                created_at TEXT NOT NULL,
                insight_text TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '{}'
            );
            """)
        conn.commit()


def _raw_connection():
    """Create a raw psycopg2 connection."""
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
    finally:
        conn.close()


def query_one(query: str, params: tuple | dict = ()):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None


def query_all(query: str, params: tuple | dict = ()):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]


def execute(query: str, params: tuple | dict = ()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            # Try to get lastrowid via RETURNING, otherwise return rowcount
            try:
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
            except psycopg2.ProgrammingError:
                conn.commit()
                return cur.rowcount
