from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from .database import execute, query_all, query_one


def normalize_channel_url(channel_url: str) -> str:
    return channel_url.strip()


def upsert_channel(channel_url: str, channel_id: Optional[str] = None, title: Optional[str] = None):
    normalized = normalize_channel_url(channel_url)
    existing = query_one('SELECT * FROM channels WHERE channel_url = %s', (normalized,))
    now = datetime.utcnow().isoformat()
    if existing:
        execute(
            'UPDATE channels SET channel_id = COALESCE(%s, channel_id), title = COALESCE(%s, title), last_checked = %s WHERE id = %s',
            (channel_id, title, now, existing['id']),
        )
        return get_channel_by_id(existing['id'])
    execute(
        'INSERT INTO channels (channel_url, channel_id, title, last_checked) VALUES (%s, %s, %s, %s)',
        (normalized, channel_id, title, now),
    )
    return get_channel_by_url(normalized)


def list_channels():
    return query_all('SELECT * FROM channels ORDER BY id DESC')


def get_channel_by_url(channel_url: str):
    return query_one('SELECT * FROM channels WHERE channel_url = %s', (normalize_channel_url(channel_url),))


def get_channel_by_id(channel_id: int):
    return query_one('SELECT * FROM channels WHERE id = %s', (channel_id,))


def get_channel_by_external_id(external_id: str):
    return query_one('SELECT * FROM channels WHERE channel_id = %s', (external_id,))


def upsert_video(channel_db_id: int, video: dict[str, Any]):
    execute(
        '''
        INSERT INTO videos (
            channel_id, video_id, title, published_at, views, likes,
            comments, thumbnail_url, captions, fetched_at, performance_score
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(video_id) DO UPDATE SET
            title = EXCLUDED.title,
            published_at = EXCLUDED.published_at,
            views = EXCLUDED.views,
            likes = EXCLUDED.likes,
            comments = EXCLUDED.comments,
            thumbnail_url = EXCLUDED.thumbnail_url,
            captions = EXCLUDED.captions,
            fetched_at = EXCLUDED.fetched_at,
            performance_score = EXCLUDED.performance_score
        ''',
        (
            channel_db_id,
            video['video_id'],
            video.get('title'),
            video.get('published_at'),
            video.get('views'),
            video.get('likes'),
            video.get('comments'),
            video.get('thumbnail_url'),
            video.get('captions'),
            datetime.utcnow().isoformat(),
            video.get('performance_score'),
        ),
    )


def get_videos_by_channel(channel_db_id: int):
    return query_all(
        'SELECT * FROM videos WHERE channel_id = %s ORDER BY published_at DESC',
        (channel_db_id,),
    )


def insert_analysis(channel_db_id: int, summary: str, strategy: dict[str, Any]):
    payload = strategy if isinstance(strategy, str) else json.dumps(strategy, ensure_ascii=False)
    execute(
        'INSERT INTO analyses (channel_id, summary, strategy) VALUES (%s, %s, %s)',
        (channel_db_id, summary, payload),
    )


def get_analyses_for_channel(channel_db_id: int, limit: int = 5):
    return query_all(
        'SELECT * FROM analyses WHERE channel_id = %s ORDER BY created_at DESC LIMIT %s',
        (channel_db_id, limit),
    )


def save_batch_history(channel_urls: list[str], channels: list[dict], strategy: dict, agent_steps: list[dict]) -> int:
    return execute(
        '''INSERT INTO batch_history (channel_urls, channels_json, strategy_json, agent_steps_json)
           VALUES (%s, %s, %s, %s) RETURNING id''',
        (
            json.dumps(channel_urls, ensure_ascii=False),
            json.dumps(channels, ensure_ascii=False),
            json.dumps(strategy, ensure_ascii=False),
            json.dumps(agent_steps, ensure_ascii=False),
        ),
    )


def list_batch_history(limit: int = 20):
    return query_all(
        'SELECT id, created_at, channel_urls FROM batch_history ORDER BY id DESC LIMIT %s',
        (limit,),
    )


def get_batch_history_by_id(history_id: int):
    return query_one('SELECT * FROM batch_history WHERE id = %s', (history_id,))


# ---------------------------------------------------------------------------
# Suggestions (learning feedback loop)
# ---------------------------------------------------------------------------

def save_suggestion(
    suggestion_id: str,
    topic_title: str,
    topic_summary: str | None = None,
    keywords: list[str] | None = None,
    reference_channels: list[str] | None = None,
    hypothesis: str | None = None,
    batch_id: str | None = None,
) -> None:
    execute(
        '''INSERT INTO suggestions
           (id, created_at, batch_id, topic_title, topic_summary, keywords, reference_channels, hypothesis)
           VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO NOTHING''',
        (
            suggestion_id,
            batch_id,
            topic_title,
            topic_summary,
            json.dumps(keywords or [], ensure_ascii=False),
            json.dumps(reference_channels or [], ensure_ascii=False),
            hypothesis,
        ),
    )


def list_suggestions(status: str | None = None, limit: int = 100) -> list[dict]:
    if status:
        return query_all(
            'SELECT * FROM suggestions WHERE status = %s ORDER BY created_at DESC LIMIT %s',
            (status, limit),
        )
    return query_all('SELECT * FROM suggestions ORDER BY created_at DESC LIMIT %s', (limit,))


def update_suggestion_status(suggestion_id: str, status: str) -> None:
    execute('UPDATE suggestions SET status = %s WHERE id = %s', (status, suggestion_id))


# ---------------------------------------------------------------------------
# Suggestion matches
# ---------------------------------------------------------------------------

def save_suggestion_match(
    suggestion_id: str,
    video_id: str,
    channel_id: str | None = None,
    video_title: str | None = None,
    match_confidence: float = 0.0,
    views: int | None = None,
    avg_views: float | None = None,
    performance_score: float | None = None,
    beat_average: bool = False,
) -> int | None:
    try:
        return execute(
            '''INSERT INTO suggestion_matches
               (suggestion_id, channel_id, video_id, video_title, matched_at,
                match_confidence, views, avg_views, performance_score, beat_average)
               VALUES (%s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
               ON CONFLICT (suggestion_id, video_id) DO NOTHING
               RETURNING id''',
            (
                suggestion_id, channel_id, video_id, video_title,
                match_confidence, views, avg_views, performance_score,
                1 if beat_average else 0,
            ),
        )
    except Exception:
        return None


def list_suggestion_matches(limit: int = 50) -> list[dict]:
    return query_all(
        '''SELECT sm.*, s.topic_title AS suggestion_topic
           FROM suggestion_matches sm
           LEFT JOIN suggestions s ON sm.suggestion_id = s.id
           ORDER BY sm.matched_at DESC LIMIT %s''',
        (limit,),
    )


def get_matches_for_scoring() -> list[dict]:
    """Get scored matches for insight generation."""
    return query_all(
        '''SELECT sm.*, s.topic_title, s.keywords, s.reference_channels
           FROM suggestion_matches sm
           JOIN suggestions s ON sm.suggestion_id = s.id
           WHERE sm.performance_score IS NOT NULL
           ORDER BY sm.performance_score DESC''',
    )


# ---------------------------------------------------------------------------
# Learning insights
# ---------------------------------------------------------------------------

def save_learning_insight(insight_text: str, evidence: dict | None = None) -> int | None:
    return execute(
        "INSERT INTO learning_insights (created_at, insight_text, evidence) VALUES (NOW(), %s, %s) RETURNING id",
        (insight_text, json.dumps(evidence or {}, ensure_ascii=False)),
    )


def list_learning_insights(limit: int = 20) -> list[dict]:
    return query_all(
        'SELECT * FROM learning_insights ORDER BY id DESC LIMIT %s',
        (limit,),
    )


def clear_learning_insights() -> None:
    execute('DELETE FROM learning_insights')


def get_recent_videos_for_channel_ext(external_channel_id: str, limit: int = 10, exclude_video_id: str | None = None) -> list[dict]:
    """Get recent videos for a channel by external channel_id (UC...) for baseline calculation."""
    channel = query_one('SELECT id FROM channels WHERE channel_id = %s', (external_channel_id,))
    if not channel:
        return []
    if exclude_video_id:
        return query_all(
            'SELECT * FROM videos WHERE channel_id = %s AND video_id != %s ORDER BY published_at DESC LIMIT %s',
            (channel['id'], exclude_video_id, limit),
        )
    return query_all(
        'SELECT * FROM videos WHERE channel_id = %s ORDER BY published_at DESC LIMIT %s',
        (channel['id'], limit),
    )


def get_all_videos_with_channel(limit: int = 200) -> list[dict]:
    """Get all stored videos joined with their channel's external channel_id."""
    return query_all(
        '''SELECT v.*, c.channel_id AS external_channel_id
           FROM videos v
           JOIN channels c ON v.channel_id = c.id
           ORDER BY v.published_at DESC LIMIT %s''',
        (limit,),
    )


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)
