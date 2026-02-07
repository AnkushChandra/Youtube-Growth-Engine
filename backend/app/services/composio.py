from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from composio import Composio
from composio_gemini import GeminiProvider

from ..config import settings

logger = logging.getLogger(__name__)

SAMPLE_DATA_PATH = Path(__file__).resolve().parents[2] / 'sample_data.json'

# ---------------------------------------------------------------------------
# YouTube toolkit tools exposed to the LLM agent via Composio + Gemini
#
#   YOUTUBE_GET_CHANNEL_ID_BY_HANDLE  – resolve @handle → channel ID
#   YOUTUBE_GET_CHANNEL_STATISTICS    – subscriber count, view count, etc.
#   YOUTUBE_LIST_CHANNEL_VIDEOS       – list videos for a channel ID
#   YOUTUBE_VIDEO_DETAILS             – snippet + statistics for a video
#   YOUTUBE_LIST_CAPTION_TRACK        – list caption track IDs for a video
#   YOUTUBE_LOAD_CAPTIONS             – download caption text by track ID
#   YOUTUBE_SEARCH_YOU_TUBE           – search YouTube for videos/channels
# ---------------------------------------------------------------------------

YOUTUBE_TOOLS = [
    'YOUTUBE_GET_CHANNEL_ID_BY_HANDLE',
    'YOUTUBE_GET_CHANNEL_STATISTICS',
    'YOUTUBE_LIST_CHANNEL_VIDEOS',
    'YOUTUBE_VIDEO_DETAILS',
    'YOUTUBE_LIST_CAPTION_TRACK',
    'YOUTUBE_LOAD_CAPTIONS',
    'YOUTUBE_SEARCH_YOU_TUBE',
]


def get_composio_client() -> Composio:
    """Create a Composio client configured with the Gemini provider."""
    return Composio(
        api_key=settings.composio_api_key,
        provider=GeminiProvider(),
    )


def get_youtube_tools(composio: Composio) -> list:
    """Fetch Gemini-formatted tool definitions for the YouTube toolkit."""
    return composio.tools.get(
        user_id=settings.composio_user_id,
        tools=YOUTUBE_TOOLS,
    )


def execute_tool_directly(composio: Composio, tool_slug: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a single Composio tool directly (without LLM), for fallback / DEV_MODE."""
    result = composio.tools.execute(
        tool_slug,
        user_id=settings.composio_user_id,
        arguments=arguments,
    )
    return result


def load_sample_data() -> dict[str, Any] | None:
    """Load sample_data.json for DEV_MODE."""
    if SAMPLE_DATA_PATH.exists():
        with SAMPLE_DATA_PATH.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        logger.info('DEV_MODE: loaded sample data (%d videos)', len(data.get('videos', [])))
        return data
    return None
