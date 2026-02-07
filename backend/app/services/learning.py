"""Continuously Learning: Video-Performance-Driven Feedback Loop.

Analyzes ALL stored video data to learn what works — framing patterns,
topic keywords, engagement signals — and feeds those insights back into
the agent prompt so suggestions improve with every batch run.

No paid services, deterministic heuristics only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import string
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from .. import crud
from ..memory import append_memory_entry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

STOPWORDS = frozenset(
    'a an the is are was were be been being have has had do does did will would '
    'shall should may might can could of in to for on with at by from as into '
    'through during before after above below between out off over under again '
    'further then once here there when where why how all both each few more most '
    'other some such no nor not only own same so than too very and but or if '
    'about up its it he she they them their this that these those i me my we our '
    'you your what which who whom video videos channel channels'.split()
)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return ' '.join(text.split())


def keyword_extract(text: str) -> list[str]:
    """Simple keyword extraction: split, remove stopwords, keep tokens len>=3."""
    tokens = normalize(text).split()
    return [t for t in tokens if t not in STOPWORDS and len(t) >= 3]


# ---------------------------------------------------------------------------
# Framing pattern detection
# ---------------------------------------------------------------------------

FRAMING_PATTERNS = {
    'curiosity_hook': re.compile(r'^(why|how|what if|the truth about|the problem with|the real reason)', re.I),
    'superlative': re.compile(r'\b(most|best|worst|biggest|smallest|fastest|deadliest|greatest)\b', re.I),
    'listicle': re.compile(r'^\d+\s', re.I),
    'versus': re.compile(r'\bvs\.?\b|\bversus\b', re.I),
    'negative_hook': re.compile(r'\b(mistakes?|wrong|fail|never|dont|stop|worst|dead|killed|dangerous|problem)\b', re.I),
    'mystery': re.compile(r'\b(mystery|secret|hidden|unknown|unexplained|impossible)\b', re.I),
    'personal_story': re.compile(r'^i\s|\bi (built|made|tried|tested|spent|bought)\b', re.I),
    'challenge': re.compile(r'\b(challenge|experiment|test|tried|attempt)\b', re.I),
    'emotional': re.compile(r'\b(shocking|incredible|insane|amazing|beautiful|terrifying)\b', re.I),
    'educational': re.compile(r'\b(explained|explanation|guide|tutorial|introduction|intro)\b', re.I),
}


def _detect_framing(title: str) -> list[str]:
    frames = []
    for name, pattern in FRAMING_PATTERNS.items():
        if pattern.search(title):
            frames.append(name)
    return frames


# ---------------------------------------------------------------------------
# Per-channel video scoring
# ---------------------------------------------------------------------------

def _score_videos_per_channel(all_videos: list[dict]) -> list[dict]:
    """Score each video relative to its channel's average.

    Returns enriched video dicts with 'perf_score' and 'channel_title' fields.
    """
    # Group by channel
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for v in all_videos:
        ch_key = v.get('external_channel_id') or v.get('channel_id') or 'unknown'
        by_channel[ch_key].append(v)

    scored: list[dict] = []
    for ch_id, videos in by_channel.items():
        view_vals = [v.get('views') or 0 for v in videos]
        avg_views = sum(view_vals) / len(view_vals) if view_vals else 1

        for v in videos:
            views = v.get('views') or 0
            perf = views / avg_views if avg_views > 0 else 1.0

            # Engagement boost
            likes = v.get('likes') or 0
            comments = v.get('comments') or 0
            eng_rate = (likes + comments * 3) / views if views > 0 else 0
            avg_eng_rates = []
            for ov in videos:
                ov_views = ov.get('views') or 0
                if ov_views > 0:
                    avg_eng_rates.append(((ov.get('likes') or 0) + (ov.get('comments') or 0) * 3) / ov_views)
            avg_eng = sum(avg_eng_rates) / len(avg_eng_rates) if avg_eng_rates else 0
            if avg_eng > 0:
                eng_mult = max(0.8, min(1.3, eng_rate / avg_eng))
            else:
                eng_mult = 1.0

            final_score = round(perf * eng_mult, 3)
            scored.append({
                **v,
                'perf_score': final_score,
                'avg_views': round(avg_views),
                'channel_key': ch_id,
            })

    return scored


# ---------------------------------------------------------------------------
# Insight generation from video performance data
# ---------------------------------------------------------------------------

def _generate_video_insights(scored_videos: list[dict]) -> list[str]:
    """Analyze ALL stored videos and generate actionable insights."""
    if len(scored_videos) < 3:
        return []

    insights: list[str] = []

    # Split into top and bottom performers
    sorted_vids = sorted(scored_videos, key=lambda v: v.get('perf_score', 0), reverse=True)
    top_cutoff = max(1, len(sorted_vids) // 4)
    top_vids = sorted_vids[:top_cutoff]
    bottom_vids = sorted_vids[-top_cutoff:]

    # --- 1. Framing patterns that win ---
    top_frames: Counter = Counter()
    bottom_frames: Counter = Counter()
    for v in top_vids:
        for f in _detect_framing(v.get('title', '')):
            top_frames[f] += 1
    for v in bottom_vids:
        for f in _detect_framing(v.get('title', '')):
            bottom_frames[f] += 1

    winning_frames = []
    for frame, count in top_frames.most_common(5):
        top_rate = count / len(top_vids)
        bottom_rate = bottom_frames.get(frame, 0) / len(bottom_vids) if bottom_vids else 0
        if top_rate > bottom_rate + 0.1 and count >= 2:
            winning_frames.append(frame.replace('_', ' '))
    if winning_frames:
        insights.append(
            f"Title framings that correlate with above-average performance: "
            f"{', '.join(winning_frames)}. Prefer these styles in suggestions."
        )

    losing_frames = []
    for frame, count in bottom_frames.most_common(5):
        bottom_rate = count / len(bottom_vids)
        top_rate = top_frames.get(frame, 0) / len(top_vids) if top_vids else 0
        if bottom_rate > top_rate + 0.1 and count >= 2:
            losing_frames.append(frame.replace('_', ' '))
    if losing_frames:
        insights.append(
            f"Title framings that correlate with below-average performance: "
            f"{', '.join(losing_frames)}. Avoid or reframe these."
        )

    # --- 2. Keywords in top performers ---
    top_kw: Counter = Counter()
    all_kw: Counter = Counter()
    for v in top_vids:
        for kw in keyword_extract(v.get('title', '')):
            top_kw[kw] += 1
    for v in scored_videos:
        for kw in keyword_extract(v.get('title', '')):
            all_kw[kw] += 1

    hot_keywords = []
    for kw, count in top_kw.most_common(20):
        if count >= 2:
            top_rate = count / len(top_vids)
            overall_rate = all_kw.get(kw, 0) / len(scored_videos)
            if top_rate > overall_rate * 1.5:
                hot_keywords.append(kw)
    if hot_keywords[:6]:
        insights.append(
            f"Keywords over-represented in top-performing videos: "
            f"{', '.join(hot_keywords[:6])}. Topics around these tend to outperform."
        )

    # --- 3. Top-performing video examples ---
    top_examples = []
    for v in top_vids[:5]:
        title = v.get('title', '?')
        score = v.get('perf_score', 1.0)
        views = v.get('views', 0)
        top_examples.append(f'"{title}" ({score:.1f}x avg, {views:,} views)')
    if top_examples:
        insights.append(
            f"Best-performing videos across tracked channels: {'; '.join(top_examples[:3])}. "
            f"Study their topic angles and framing."
        )

    # --- 4. Engagement patterns ---
    high_eng_vids = []
    for v in scored_videos:
        views = v.get('views') or 0
        comments = v.get('comments') or 0
        if views > 0 and comments / views > 0.005:  # >0.5% comment rate = high engagement
            high_eng_vids.append(v)
    if high_eng_vids and len(high_eng_vids) >= 2:
        eng_frames: Counter = Counter()
        for v in high_eng_vids:
            for f in _detect_framing(v.get('title', '')):
                eng_frames[f] += 1
        top_eng_frames = [f.replace('_', ' ') for f, _ in eng_frames.most_common(3) if eng_frames[f] >= 2]
        if top_eng_frames:
            insights.append(
                f"Videos with high comment engagement often use: {', '.join(top_eng_frames)}. "
                f"These framings spark discussion."
            )

    # --- 5. Channel-level patterns ---
    channel_avgs: dict[str, float] = {}
    channel_names: dict[str, str] = {}
    for v in scored_videos:
        ch = v.get('channel_key', 'unknown')
        channel_avgs.setdefault(ch, []).append(v.get('perf_score', 1.0)) if isinstance(channel_avgs.get(ch), list) else None
        if not channel_avgs.get(ch):
            channel_avgs[ch] = [v.get('perf_score', 1.0)]
        # Try to get channel name
        ch_title = v.get('channel_title') or v.get('title', '')
        if ch not in channel_names:
            channel_names[ch] = ch_title

    # --- 6. Content gap signal ---
    if len(scored_videos) >= 10:
        all_keywords_flat = []
        for v in scored_videos:
            all_keywords_flat.extend(keyword_extract(v.get('title', '')))
        kw_freq = Counter(all_keywords_flat)
        rare_in_top = []
        for kw, count in top_kw.most_common(10):
            if kw_freq.get(kw, 0) <= 2 and count >= 1:
                rare_in_top.append(kw)
        if rare_in_top[:4]:
            insights.append(
                f"Underexplored topics that performed well when covered: "
                f"{', '.join(rare_in_top[:4])}. These may be content gaps worth pursuing."
            )

    return insights[:8]


# ---------------------------------------------------------------------------
# Suggestion persistence (unchanged)
# ---------------------------------------------------------------------------

def make_suggestion_id(topic_title: str, batch_id: str | None = None) -> str:
    """Deterministic suggestion ID from title + optional batch."""
    raw = f"{topic_title.strip().lower()}:{batch_id or 'none'}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def save_suggestions_from_strategy(strategy: dict, batch_id: str | None = None) -> int:
    """Persist next_video_suggestions from a strategy dict. Returns count saved."""
    suggestions = strategy.get('next_video_suggestions', [])
    count = 0
    for s in suggestions:
        topic = s.get('topic', '')
        if not topic:
            continue
        sid = make_suggestion_id(topic, batch_id)
        keywords = keyword_extract(topic)
        crud.save_suggestion(
            suggestion_id=sid,
            topic_title=topic,
            topic_summary=s.get('why'),
            keywords=keywords,
            reference_channels=s.get('reference_channels', []),
            hypothesis=s.get('why'),
            batch_id=batch_id,
        )
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main learning cycle — now based on actual video performance
# ---------------------------------------------------------------------------

def run_learning_cycle(channels_data: list[dict] | None = None) -> dict[str, Any]:
    """Analyze all stored video data, extract performance patterns, generate insights.

    This learns from the ACTUAL videos and channels the user has tracked,
    not just from suggestion-to-video title matching.

    Returns:
        dict with 'videos_analyzed', 'insights_generated', 'insights' keys.
    """
    logger.info('LEARNING CYCLE START')

    # 1. Load all stored videos from DB
    db_videos = crud.get_all_videos_with_channel(limit=500)

    # Also merge in any fresh batch data not yet persisted
    seen_ids = {v.get('video_id', '') for v in db_videos}
    if channels_data:
        for ch in channels_data:
            ch_id = ch.get('channel_id', '')
            ch_title = ch.get('title', '')
            for v in ch.get('top_videos', []):
                vid_id = v.get('videoId') or v.get('video_id', '')
                if vid_id and vid_id not in seen_ids:
                    seen_ids.add(vid_id)
                    db_videos.append({
                        'video_id': vid_id,
                        'title': v.get('title', ''),
                        'external_channel_id': ch_id,
                        'channel_title': ch_title,
                        'views': v.get('views'),
                        'likes': v.get('likes'),
                        'comments': v.get('comments'),
                    })

    # Filter out memory stubs and videos with no views
    real_videos = [
        v for v in db_videos
        if not (v.get('video_id', '').startswith('memory_'))
        and (v.get('views') or 0) > 0
    ]

    logger.info('Analyzing %d videos across tracked channels', len(real_videos))

    if len(real_videos) < 3:
        logger.info('Not enough video data to generate insights (need ≥3).')
        return {'videos_analyzed': len(real_videos), 'insights_generated': 0, 'insights': []}

    # 2. Score each video relative to its channel average
    scored = _score_videos_per_channel(real_videos)

    # 3. Generate insights from performance patterns
    insights = _generate_video_insights(scored)

    if not insights:
        logger.info('No new insights could be generated from current data.')
        return {'videos_analyzed': len(real_videos), 'insights_generated': 0, 'insights': []}

    # 4. Clear old insights and save fresh ones (insights are regenerated each cycle)
    crud.clear_learning_insights()

    insights_saved = 0
    for insight in insights:
        evidence = {
            'videos_analyzed': len(real_videos),
            'channels_tracked': len({v.get('external_channel_id') or v.get('channel_key', '') for v in scored}),
            'generated_at': datetime.utcnow().isoformat(),
        }
        crud.save_learning_insight(insight, evidence)
        insights_saved += 1

    # 5. Append summary to memory.txt
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    findings = insights[:3]
    action = f'LEARNING UPDATE {date_str}: analyzed {len(real_videos)} videos, generated {insights_saved} insights'
    append_memory_entry('learning', findings, action)
    logger.info('Appended learning insights to memory.txt')

    logger.info('LEARNING CYCLE DONE: %d videos analyzed, %d insights', len(real_videos), insights_saved)

    return {
        'videos_analyzed': len(real_videos),
        'insights_generated': insights_saved,
        'insights': insights,
    }


# ---------------------------------------------------------------------------
# Prompt injection — feed learned patterns into the agent
# ---------------------------------------------------------------------------

def get_learning_context_for_prompt() -> str:
    """Build a learning context string to inject into the agent prompt."""
    insights = crud.list_learning_insights(limit=10)
    if not insights:
        return ''

    lines = [
        'LEARNED RULES (from analyzing performance of videos across tracked channels).',
        'Use these patterns to make BETTER suggestions this time:',
    ]
    for ins in insights:
        lines.append(f'  - {ins["insight_text"]}')

    return '\n'.join(lines)
