from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, List

CHANNEL_ID_RE = re.compile(r"/channel/([A-Za-z0-9_-]+)")
HANDLE_RE = re.compile(r"/@([A-Za-z0-9._-]+)")
CUSTOM_RE = re.compile(r"/c/([A-Za-z0-9_-]+)")
VIDEO_ID_RE = re.compile(r"v=([A-Za-z0-9_-]{11})")
NUMBER_RE = re.compile(r"\d+")

POSITIVE_WORDS = {
    'win', 'boost', 'easy', 'secret', 'proven', 'grow', 'success', 'best', 'powerful', 'fast'
}
NEGATIVE_WORDS = {
    'fail', 'stop', 'avoid', 'worst', "don't", 'hard', 'slow', 'boring', 'stuck'
}

HOOK_KEYWORDS = [
    'what', 'why', 'how', 'you', 'number', 'secret', 'won\'t believe', 'in 60 seconds', '?'
]


def extract_channel_identifier(url_or_handle: str) -> str:
    text = url_or_handle.strip()
    if text.startswith('@'):
        return text
    match = CHANNEL_ID_RE.search(text)
    if match:
        return match.group(1)
    match = HANDLE_RE.search(text)
    if match:
        return f"@{match.group(1)}"
    match = CUSTOM_RE.search(text)
    if match:
        return match.group(1)
    if 'youtube.com' not in text and '/' not in text:
        return text
    return text.rsplit('/', 1)[-1]


def parse_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        return datetime.fromisoformat(dt_str).astimezone(timezone.utc)
    except ValueError:
        return None


def tokenize(text: str) -> List[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9']+", text)]


def count_sentiment(tokens: Iterable[str]) -> dict[str, int]:
    positives = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negatives = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    return {'positive': positives, 'negative': negatives}


def contains_number(text: str) -> bool:
    return bool(NUMBER_RE.search(text))


def title_starts_with_question(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith('how') or lowered.startswith('why')


def hook_score(text: str) -> float:
    lowered = text.lower()
    score = 0
    for keyword in HOOK_KEYWORDS:
        if keyword in lowered:
            score += 1
    if '?' in lowered:
        score += 0.5
    if contains_number(lowered):
        score += 0.5
    return score


def first_chars(text: str | None, limit: int = 300) -> str:
    if not text:
        return ''
    return text.strip()[:limit]
