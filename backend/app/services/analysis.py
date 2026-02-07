from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from ..memory import read_recent_memory
from ..utils import (
    contains_number,
    count_sentiment,
    first_chars,
    hook_score,
    parse_datetime,
    title_starts_with_question,
    tokenize,
)


@dataclass
class VideoFeatures:
    video_id: str
    title: str | None
    published_at: str | None
    views: int | None
    likes: int | None
    comments: int | None
    captions: str | None
    thumbnail_url: str | None
    age_days: float
    views_per_day: float
    engagement_rate: float
    title_length: int
    title_has_number: bool
    title_has_question: bool
    first_30s_text: str
    hook_score: float
    performance_score: float


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def build_video_features(videos: List[Dict[str, Any]]) -> List[VideoFeatures]:
    now = datetime.now(timezone.utc)
    temp_results: List[VideoFeatures] = []
    views_per_day_values: List[float] = []
    engagement_values: List[float] = []

    for video in videos:
        video_id = video.get('videoId') or video.get('id')
        if not video_id:
            continue
        published_dt = parse_datetime(video.get('publishedAt'))
        age_days = max((now - published_dt).total_seconds() / 86400 if published_dt else 1, 1)
        views = _safe_int(video.get('views'))
        likes = _safe_int(video.get('likes'))
        comments = _safe_int(video.get('comments'))
        views_per_day = views / age_days
        engagement_rate = (likes + comments) / max(views, 1)
        title = video.get('title') or ''
        captions = video.get('captions') or ''
        first_text = first_chars(captions)
        features = VideoFeatures(
            video_id=video_id,
            title=title,
            published_at=video.get('publishedAt'),
            views=views,
            likes=likes,
            comments=comments,
            captions=captions,
            thumbnail_url=video.get('thumbnailUrl'),
            age_days=age_days,
            views_per_day=views_per_day,
            engagement_rate=engagement_rate,
            title_length=len(title),
            title_has_number=contains_number(title),
            title_has_question='?' in title,
            first_30s_text=first_text,
            hook_score=hook_score(first_text or title),
            performance_score=0.0,
        )
        temp_results.append(features)
        views_per_day_values.append(views_per_day)
        engagement_values.append(engagement_rate)

    max_views = max(views_per_day_values) if views_per_day_values else 1
    max_engagement = max(engagement_values) if engagement_values else 1

    for features in temp_results:
        norm_views = features.views_per_day / max_views if max_views else 0
        norm_engagement = features.engagement_rate / max_engagement if max_engagement else 0
        features.performance_score = 0.7 * norm_views + 0.3 * norm_engagement

    return temp_results


def analyze_patterns(videos: List[VideoFeatures]) -> dict[str, Any]:
    if not videos:
        return {}

    sorted_videos = sorted(videos, key=lambda v: v.performance_score, reverse=True)
    top = sorted_videos[:2]
    bottom = sorted_videos[-2:] if len(sorted_videos) >= 4 else sorted_videos[-1:]

    findings: List[str] = []
    pattern_stats: Dict[str, Tuple[int, int]] = {}

    def record_pattern(name: str, val_top: bool, val_bottom: bool):
        pattern_stats[name] = (
            pattern_stats.get(name, (0, 0))[0] + (1 if val_top else 0),
            pattern_stats.get(name, (0, 0))[1] + (1 if val_bottom else 0),
        )

    for video in top:
        record_pattern('numbers_in_title', video.title_has_number, False)
        record_pattern('questions_in_title', video.title_has_question, False)
        record_pattern('hook_score_high', video.hook_score >= 2, False)
        record_pattern('title_long', video.title_length > 40, False)
        record_pattern('starts_with_how_or_why', title_starts_with_question(video.title or ''), False)
        record_pattern('uses_you', 'you' in (video.title or '').lower(), False)

    for video in bottom:
        record_pattern('numbers_in_title', False, video.title_has_number)
        record_pattern('questions_in_title', False, video.title_has_question)
        record_pattern('hook_score_high', False, video.hook_score >= 2)
        record_pattern('title_long', False, video.title_length > 40)
        record_pattern('starts_with_how_or_why', False, title_starts_with_question(video.title or ''))
        record_pattern('uses_you', False, 'you' in (video.title or '').lower())

    for key, (top_count, bottom_count) in pattern_stats.items():
        if top_count > bottom_count:
            findings.append(f"Top performers favor {key.replace('_', ' ')}")
        elif bottom_count > top_count:
            findings.append(f"Lower performers favor {key.replace('_', ' ')}")

    tokens_top = [token for video in top for token in tokenize(video.title or '')]
    tokens_bottom = [token for video in bottom for token in tokenize(video.title or '')]

    sentiment_top = count_sentiment(tokens_top)
    sentiment_bottom = count_sentiment(tokens_bottom)

    ngram_findings = []
    if tokens_top:
        ngram_findings.append(f"Top titles skew positive by {sentiment_top['positive']} keywords")
    if tokens_bottom:
        ngram_findings.append(f"Lower titles carry {sentiment_bottom['negative']} negative cues")

    return {
        'findings': findings + ngram_findings,
        'top_videos': top,
        'bottom_videos': bottom,
    }


def derive_strategy(videos: List[VideoFeatures], channel_url: str) -> dict[str, Any]:
    ranked = sorted(videos, key=lambda v: v.performance_score, reverse=True)
    top_two = ranked[:2]
    pattern_payload = analyze_patterns(ranked)
    findings = pattern_payload.get('findings', []) if pattern_payload else []
    if not findings:
        findings = ['Need more data to detect strong patterns']

    avg_duration_guess = statistics.mean(v.age_days for v in ranked[:5]) if ranked[:5] else 3
    recommended_format = {
        'ideal_length_minutes': round(max(6, min(12, 14 - avg_duration_guess / 10)), 1),
        'title_patterns': [
            'Use numbers + promise ("10 riffs to master")',
            'Lead with a question ("Can you guess...")',
        ],
        'hook_template': 'Open with a bold question or outcome in first 15s, then tease the reveal.',
        'thumbnail_text': 'Short, 3-4 word contrast with bold number',
    }

    action_plan = [
        'Storyboard a hook that states the payoff within 10 seconds.',
        'Include a number or time-bound promise in the title.',
        'Use "you" or direct address within the first sentence of captions.',
        'Design two thumbnail variations: textual promise vs. reaction close-up.',
        'Publish during the channel’s historically top engagement hour and track retention.',
    ]

    memory_lines = read_recent_memory()
    memory_signal = sum(1 for line in memory_lines if channel_url in line)
    confidence = min(0.9, 0.4 + 0.1 * len(videos) / 10 + 0.05 * memory_signal)
    if len(ranked) >= 2:
        gap = ranked[0].performance_score - ranked[-1].performance_score
        confidence += min(0.2, gap)

    summary = (
        f"Top videos leaned on {', '.join(findings[:2])}. "
        f"Lean into sharp hooks, numeric promises, and energetic first 30 seconds."
    )

    return {
        'key_findings': findings[:5],
        'recommended_format': recommended_format,
        'action_plan': action_plan,
        'confidence': round(min(confidence, 0.98), 2),
        'summary': summary,
    }
