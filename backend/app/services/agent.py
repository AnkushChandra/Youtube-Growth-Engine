from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import types

from .. import crud
from ..config import settings
from ..memory import append_memory_entry, read_recent_memory
from ..services.composio import get_composio_client, get_youtube_tools, load_sample_data
from ..services.learning import get_learning_context_for_prompt, run_learning_cycle, save_suggestions_from_strategy
from ..utils import extract_channel_identifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File logger — writes detailed agent trace to agent_debug.log
# ---------------------------------------------------------------------------
_LOG_PATH = Path(__file__).resolve().parents[2] / 'agent_debug.log'
_file_handler = logging.FileHandler(_LOG_PATH, mode='a', encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(message)s'))
_agent_logger = logging.getLogger('agent_debug')
_agent_logger.setLevel(logging.DEBUG)
_agent_logger.addHandler(_file_handler)
_agent_logger.propagate = False


def _log(msg: str, *args: Any) -> None:
    """Log to both console and the debug file."""
    logger.info(msg, *args)
    _agent_logger.info(msg, *args)

# ---------------------------------------------------------------------------
# System prompt that turns the LLM into a YouTube strategy agent.
# It instructs the model to use Composio YouTube tools, reason step-by-step,
# and produce a structured JSON strategy at the end.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a YouTube Strategy Agent. Your job is to analyze a YouTube channel and \
produce an actionable growth strategy based on data.

You have access to YouTube tools via Composio. Use them to:
1. Resolve the channel handle/URL to a channel ID (YOUTUBE_GET_CHANNEL_ID_BY_HANDLE)
2. Get channel statistics (YOUTUBE_GET_CHANNEL_STATISTICS)
3. List the last 10 videos (YOUTUBE_LIST_CHANNEL_VIDEOS)
4. For each video, get detailed stats — views, likes, comments (YOUTUBE_VIDEO_DETAILS)
5. Optionally fetch captions for top videos (YOUTUBE_LIST_CAPTION_TRACK + YOUTUBE_LOAD_CAPTIONS)

After gathering data, analyze patterns:
- Which titles/formats perform best (views, engagement)?
- What hooks or keywords correlate with high performance?
- What's the ideal posting cadence?

{memory_context}

IMPORTANT: After your analysis, you MUST output a final message containing a JSON block \
wrapped in ```json ... ``` with this exact structure:
```json
{{
  "channel": {{
    "channelId": "UC...",
    "title": "Channel Name",
    "url": "original url"
  }},
  "videos": [
    {{
      "videoId": "...",
      "title": "...",
      "publishedAt": "...",
      "views": 12345,
      "likes": 100,
      "comments": 10,
      "thumbnailUrl": "...",
      "captions": "first 300 chars or null"
    }}
  ],
  "strategy": {{
    "key_findings": ["finding 1", "finding 2", ...],
    "recommended_format": {{
      "ideal_length_minutes": 8,
      "title_patterns": ["pattern 1", "pattern 2"],
      "hook_template": "...",
      "thumbnail_text": "..."
    }},
    "action_plan": ["step 1", "step 2", ...],
    "confidence": 0.75,
    "summary": "One paragraph summary of the strategy"
  }}
}}
```

Be thorough but efficient. Call tools in a logical order. Think step by step.
"""


MAX_AGENT_TURNS = 15
RETRY_BACKOFFS = [15, 30, 60]


def _send_with_retry(chat, message: str):
    """Send a message to Gemini chat with retry on 429 rate limit errors."""
    for attempt, backoff in enumerate(RETRY_BACKOFFS):
        try:
            return chat.send_message(message)
        except Exception as exc:
            exc_str = str(exc)
            if '429' in exc_str or 'RESOURCE_EXHAUSTED' in exc_str:
                logger.warning(
                    'Gemini rate limited (attempt %d/%d), retrying in %ds…',
                    attempt + 1, len(RETRY_BACKOFFS), backoff,
                )
                time.sleep(backoff)
            else:
                raise
    # Final attempt — let it raise if it fails
    return chat.send_message(message)


def _build_memory_context() -> str:
    """Build a memory context string from recent memory entries."""
    lines = read_recent_memory()
    if not lines:
        return 'You have no prior memory of analyzing channels.'
    joined = '\n'.join(f'  - {line}' for line in lines[-5:])
    return (
        f'You have memory from prior analyses. Use this to improve confidence '
        f'and spot recurring patterns:\n{joined}'
    )


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract the first ```json ... ``` block from LLM output."""
    match = re.search(r'```json\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning('Failed to parse JSON block from agent output')
    return None


def analyze_channel(channel_url: str) -> dict[str, Any]:
    """Run the AI agent loop to analyze a YouTube channel."""
    logger.info('Starting AI agent analysis for %s', channel_url)

    if settings.dev_mode:
        return _analyze_dev_mode(channel_url)

    if not settings.gemini_api_key:
        raise RuntimeError('GEMINI_API_KEY is required. Set it in .env')

    # 1. Initialize Composio + Gemini
    composio = get_composio_client()
    gemini_client = genai.Client(api_key=settings.gemini_api_key)
    tools = get_youtube_tools(composio)

    # Extract underlying genai Tool objects for the SDK config,
    # but keep GeminiTool wrappers for handle_response()
    genai_tools = [t._genai_tool for t in tools if hasattr(t, '_genai_tool')]

    # 2. Build conversation config with tools
    memory_context = _build_memory_context()
    system_msg = SYSTEM_PROMPT.format(memory_context=memory_context)

    config = types.GenerateContentConfig(
        tools=genai_tools,
        system_instruction=system_msg,
    )

    # 3. Create a chat session — Gemini handles multi-turn + tool calls
    chat = gemini_client.chats.create(model=settings.gemini_model, config=config)

    agent_steps: List[Dict[str, Any]] = []

    # 4. Send initial message
    user_msg = f'Analyze this YouTube channel and create a strategy: {channel_url}'

    for turn in range(MAX_AGENT_TURNS):
        logger.info('Agent turn %d/%d', turn + 1, MAX_AGENT_TURNS)

        response = _send_with_retry(chat, user_msg)

        # Check for function calls in the response
        if response.function_calls:
            # Log each function call for the agent trace
            for fc in response.function_calls:
                fn_name = fc.name or ''
                fn_args = dict(fc.args) if fc.args else {}
                logger.info('Agent calling tool: %s(%s)', fn_name, fn_args)
                agent_steps.append({
                    'type': 'tool_call',
                    'tool': fn_name,
                    'arguments': fn_args,
                })

            # Execute all function calls via Composio's GeminiProvider
            try:
                function_responses, executed = composio.provider.handle_response(
                    response, tools,
                )
                for fc in response.function_calls:
                    agent_steps.append({
                        'type': 'tool_result',
                        'tool': fc.name or '',
                        'result_preview': 'Tool executed successfully' if executed else 'Execution skipped',
                    })
            except Exception as exc:
                logger.error('Tool execution failed: %s', exc)
                agent_steps.append({
                    'type': 'tool_result',
                    'tool': 'batch',
                    'result_preview': f'Error: {str(exc)[:400]}',
                })
                # Send error back to the model so it can recover
                user_msg = f'Tool execution failed with error: {exc}. Try a different approach or skip this step.'
                continue

            # Send function responses back to the chat so the model sees the results
            if executed and function_responses:
                response = _send_with_retry(chat, function_responses)
                # Check if this new response also has function calls (chain)
                if response.function_calls:
                    # Re-process on next iteration
                    user_msg = 'Continue analyzing with the tool results. When done, output the final JSON strategy.'
                    continue
                # Otherwise fall through to text handling below
                final_text = response.text or ''
                agent_steps.append({'type': 'reasoning', 'content': final_text[:1000]})
                parsed = _extract_json_block(final_text)
                if parsed:
                    return _persist_and_return(channel_url, parsed, agent_steps)
                user_msg = 'Continue analyzing. When done, output the final JSON strategy wrapped in ```json ... ```.'
                continue
            else:
                user_msg = 'Continue analyzing with the tool results. When done, output the final JSON strategy.'
                continue

        # No function calls — the model produced a final text response
        final_text = response.text or ''
        agent_steps.append({'type': 'reasoning', 'content': final_text[:1000]})
        logger.info('Agent produced final response (turn %d)', turn + 1)

        # 5. Extract structured JSON from the response
        parsed = _extract_json_block(final_text)
        if parsed:
            return _persist_and_return(channel_url, parsed, agent_steps)

        # If no JSON block found, ask the model to produce one
        if turn < MAX_AGENT_TURNS - 2:
            user_msg = 'Please output the final strategy as a JSON block wrapped in ```json ... ``` as instructed.'
            continue

        # Last resort: return what we have
        logger.warning('Agent did not produce structured JSON after %d turns', turn + 1)
        return _fallback_response(channel_url, final_text, agent_steps)

    logger.warning('Agent exhausted max turns without final output')
    return _fallback_response(channel_url, 'Agent could not complete analysis in time.', agent_steps)


def _persist_and_return(
    channel_url: str,
    parsed: dict[str, Any],
    agent_steps: List[Dict[str, Any]],
) -> dict[str, Any]:
    """Persist analysis results to DB + memory and return the response."""
    channel_data = parsed.get('channel', {})
    videos_data = parsed.get('videos', [])
    strategy = parsed.get('strategy', {})
    summary = strategy.get('summary', '')

    # Upsert channel
    channel_record = crud.upsert_channel(
        channel_url,
        channel_id=channel_data.get('channelId'),
        title=channel_data.get('title'),
    )
    channel_db_id = channel_record['id']

    # Upsert videos
    for video in videos_data:
        crud.upsert_video(channel_db_id, {
            'video_id': video.get('videoId', ''),
            'title': video.get('title'),
            'published_at': video.get('publishedAt'),
            'views': video.get('views'),
            'likes': video.get('likes'),
            'comments': video.get('comments'),
            'thumbnail_url': video.get('thumbnailUrl'),
            'captions': video.get('captions'),
            'performance_score': video.get('performanceScore', 0),
        })

    # Persist analysis
    crud.insert_analysis(channel_db_id, summary, strategy)

    # Update memory
    findings = strategy.get('key_findings', [])
    action = (strategy.get('action_plan') or ['Iterate on content'])[0]
    append_memory_entry(channel_url, findings, action)

    return {
        'strategy': strategy,
        'summary': summary,
        'channel': {
            'id': channel_db_id,
            'channel_url': channel_record['channel_url'],
            'title': channel_record.get('title'),
            'channel_id': channel_record.get('channel_id'),
        },
        'videos': videos_data,
        'agent_steps': agent_steps,
    }


def _fallback_response(
    channel_url: str,
    text: str,
    agent_steps: List[Dict[str, Any]],
) -> dict[str, Any]:
    """Build a response when the agent didn't produce structured JSON."""
    identifier = extract_channel_identifier(channel_url)
    channel_record = crud.upsert_channel(channel_url, channel_id=identifier)

    strategy = {
        'key_findings': ['Agent analysis incomplete — see summary for details'],
        'recommended_format': {
            'ideal_length_minutes': 8,
            'title_patterns': ['Use numbers + promise', 'Lead with a question'],
            'hook_template': 'Open with a bold question or outcome in first 15s.',
            'thumbnail_text': 'Short, bold text with contrast',
        },
        'action_plan': ['Re-run analysis with more specific channel URL'],
        'confidence': 0.3,
        'summary': text[:500],
    }

    crud.insert_analysis(channel_record['id'], text[:500], strategy)

    return {
        'strategy': strategy,
        'summary': text[:500],
        'channel': {
            'id': channel_record['id'],
            'channel_url': channel_record['channel_url'],
            'title': channel_record.get('title'),
            'channel_id': channel_record.get('channel_id'),
        },
        'videos': [],
        'agent_steps': agent_steps,
    }


BATCH_SYSTEM_PROMPT = """\
You are a YouTube Trend Analyst Agent. You are given a list of YouTube channels. \
For EACH channel you must:
1. Resolve the channel handle/URL to a channel ID (YOUTUBE_GET_CHANNEL_ID_BY_HANDLE)
2. List the last 5 videos (YOUTUBE_LIST_CHANNEL_VIDEOS with maxResults=5)
3. For each video, get detailed stats (YOUTUBE_VIDEO_DETAILS)
4. For each video, fetch captions: first get caption tracks (YOUTUBE_LIST_CAPTION_TRACK), \
   then download the captions text (YOUTUBE_LOAD_CAPTIONS)

After gathering ALL data across ALL channels, analyze the combined data:
- What topics are trending across these channels?
- What patterns (titles, formats, hooks, lengths) are common among top-performing videos?
- What content gaps exist — topics that are underserved but have audience demand?
- Based on all of this, suggest 3-5 specific video topics the user should make next, \
  explaining WHY each would perform well based on the data.

{memory_context}

{learning_context}

IMPORTANT: After your analysis, you MUST output a final message containing a JSON block \
wrapped in ```json ... ``` with this exact structure:
```json
{{
  "channels": [
    {{
      "channel_url": "original url",
      "title": "Channel Name",
      "channel_id": "UC...",
      "top_videos": [
        {{
          "videoId": "...",
          "title": "...",
          "publishedAt": "...",
          "views": 12345,
          "likes": 100,
          "comments": 10,
          "thumbnailUrl": "...",
          "captions": "first 500 chars of captions or null"
        }}
      ]
    }}
  ],
  "strategy": {{
    "trending_topics": ["topic 1", "topic 2", ...],
    "common_patterns": ["pattern 1", "pattern 2", ...],
    "content_gaps": ["gap 1", "gap 2", ...],
    "next_video_suggestions": [
      {{
        "topic": "Specific video topic/title idea",
        "why": "Why this will perform well based on the data",
        "reference_channels": ["channel names that inspired this"],
        "estimated_appeal": "high/medium/low"
      }}
    ],
    "key_findings": ["finding 1", "finding 2", ...],
    "confidence": 0.75,
    "summary": "One paragraph summary of trends and recommendations"
  }}
}}
```

Process channels ONE AT A TIME. Be thorough with captions — they reveal the actual \
content topics. Think step by step.
"""


MAX_BATCH_TURNS = 25


def analyze_batch(channel_urls: List[str]) -> dict[str, Any]:
    """Run the AI agent loop to analyze multiple YouTube channels and produce a cross-channel strategy."""
    _log('=' * 80)
    _log('BATCH ANALYSIS START — %d channels: %s', len(channel_urls), channel_urls)
    _log('=' * 80)

    if not settings.gemini_api_key:
        raise RuntimeError('GEMINI_API_KEY is required. Set it in .env')

    # 1. Initialize Composio + Gemini
    composio = get_composio_client()
    gemini_client = genai.Client(api_key=settings.gemini_api_key)
    tools = get_youtube_tools(composio)

    # Extract underlying genai Tool objects for the SDK config,
    # but keep GeminiTool wrappers for handle_response()
    genai_tools = [t._genai_tool for t in tools if hasattr(t, '_genai_tool')]
    _log('Loaded %d genai tools for Gemini config', len(genai_tools))

    # 2. Build conversation config with tools
    memory_context = _build_memory_context()
    learning_context = get_learning_context_for_prompt()
    system_msg = BATCH_SYSTEM_PROMPT.format(memory_context=memory_context, learning_context=learning_context)
    _log('System prompt length: %d chars', len(system_msg))
    if learning_context:
        _log('Injected learning context (%d chars)', len(learning_context))

    config = types.GenerateContentConfig(
        tools=genai_tools,
        system_instruction=system_msg,
    )

    # 3. Create a chat session
    chat = gemini_client.chats.create(model=settings.gemini_model, config=config)

    agent_steps: List[Dict[str, Any]] = []

    # 4. Send initial message with all channel URLs
    channels_list = '\n'.join(f'  {i+1}. {url}' for i, url in enumerate(channel_urls))
    user_msg = (
        f'Analyze these {len(channel_urls)} YouTube channels. '
        f'For each, get the last 5 videos with full stats and captions. '
        f'Then produce a cross-channel trend analysis and next video suggestions.\n\n'
        f'Channels:\n{channels_list}'
    )
    _log('INITIAL USER MSG:\n%s', user_msg)

    for turn in range(MAX_BATCH_TURNS):
        _log('-' * 60)
        _log('TURN %d/%d — sending message (%d chars)', turn + 1, MAX_BATCH_TURNS, len(str(user_msg)))

        response = _send_with_retry(chat, user_msg)

        # Check for function calls
        if response.function_calls:
            _log('RESPONSE: %d function call(s)', len(response.function_calls))
            for i, fc in enumerate(response.function_calls):
                fn_name = fc.name or ''
                fn_args = dict(fc.args) if fc.args else {}
                _log('  TOOL_CALL[%d]: %s  args=%s', i, fn_name, json.dumps(fn_args, default=str))
                agent_steps.append({
                    'type': 'tool_call',
                    'tool': fn_name,
                    'arguments': fn_args,
                })

            # Execute all function calls via Composio's GeminiProvider
            try:
                function_responses, executed = composio.provider.handle_response(
                    response, tools,
                )
                _log('TOOL EXECUTION: executed=%s, responses type=%s', executed, type(function_responses).__name__)
                if function_responses:
                    resp_str = str(function_responses)
                    _log('TOOL RESPONSES (first 3000 chars):\n%s', resp_str[:3000])
                for fc in response.function_calls:
                    agent_steps.append({
                        'type': 'tool_result',
                        'tool': fc.name or '',
                        'result_preview': 'Tool executed successfully' if executed else 'Execution skipped',
                    })
            except Exception as exc:
                _log('TOOL EXECUTION FAILED: %s', exc)
                logger.error('Tool execution failed: %s', exc)
                agent_steps.append({
                    'type': 'tool_result',
                    'tool': 'batch',
                    'result_preview': f'Error: {str(exc)[:400]}',
                })
                user_msg = f'Tool execution failed with error: {exc}. Try a different approach or skip this step.'
                continue

            if executed and function_responses:
                _log('Sending function_responses back to chat...')
                response = _send_with_retry(chat, function_responses)
                if response.function_calls:
                    _log('CHAINED RESPONSE: %d more function call(s)', len(response.function_calls))
                    user_msg = 'Continue processing the channels. When all are done, output the final JSON strategy.'
                    continue
                final_text = response.text or ''
                _log('POST-TOOL TEXT RESPONSE (%d chars):\n%s', len(final_text), final_text[:2000])
                agent_steps.append({'type': 'reasoning', 'content': final_text[:1000]})
                parsed = _extract_json_block(final_text)
                if parsed:
                    _log('PARSED JSON — channels: %d, strategy keys: %s',
                         len(parsed.get('channels', [])),
                         list(parsed.get('strategy', {}).keys()))
                    return _persist_batch_and_return(channel_urls, parsed, agent_steps)
                user_msg = 'Continue. When done with all channels, output the final JSON wrapped in ```json ... ```.'
                continue
            else:
                user_msg = 'Continue processing the channels. When all are done, output the final JSON strategy.'
                continue

        # No function calls — final text response
        final_text = response.text or ''
        _log('TEXT RESPONSE (no tools) — %d chars:\n%s', len(final_text), final_text[:2000])
        agent_steps.append({'type': 'reasoning', 'content': final_text[:1000]})

        parsed = _extract_json_block(final_text)
        if parsed:
            _log('PARSED JSON — channels: %d, strategy keys: %s',
                 len(parsed.get('channels', [])),
                 list(parsed.get('strategy', {}).keys()))
            for ch in parsed.get('channels', []):
                _log('  Channel: %s — %d videos', ch.get('title', '?'), len(ch.get('top_videos', [])))
            return _persist_batch_and_return(channel_urls, parsed, agent_steps)

        if turn < MAX_BATCH_TURNS - 2:
            user_msg = 'Please output the final cross-channel strategy as a JSON block wrapped in ```json ... ``` as instructed.'
            continue

        _log('WARNING: No structured JSON after %d turns', turn + 1)
        return _fallback_batch_response(channel_urls, final_text, agent_steps)

    _log('WARNING: Exhausted max turns (%d)', MAX_BATCH_TURNS)
    return _fallback_batch_response(channel_urls, 'Agent could not complete batch analysis in time.', agent_steps)


def _persist_batch_and_return(
    channel_urls: List[str],
    parsed: dict[str, Any],
    agent_steps: List[Dict[str, Any]],
) -> dict[str, Any]:
    """Persist batch analysis results and return the response."""
    channels_data = parsed.get('channels', [])
    strategy = parsed.get('strategy', {})

    # Upsert each channel and its videos
    for ch in channels_data:
        channel_record = crud.upsert_channel(
            ch.get('channel_url', ''),
            channel_id=ch.get('channel_id'),
            title=ch.get('title'),
        )
        channel_db_id = channel_record['id']
        for video in ch.get('top_videos', []):
            vid_id = video.get('videoId') or video.get('video_id', '')
            if vid_id:
                crud.upsert_video(channel_db_id, {
                    'video_id': vid_id,
                    'title': video.get('title'),
                    'published_at': video.get('publishedAt') or video.get('published_at'),
                    'views': video.get('views'),
                    'likes': video.get('likes'),
                    'comments': video.get('comments'),
                    'thumbnail_url': video.get('thumbnailUrl') or video.get('thumbnail_url'),
                    'captions': video.get('captions'),
                    'performance_score': video.get('performanceScore', 0),
                })

    # Update memory
    findings = strategy.get('key_findings', [])
    topics = strategy.get('trending_topics', [])
    action = f'Batch analysis of {len(channel_urls)} channels. Trending: {", ".join(topics[:3])}'
    append_memory_entry('batch', findings[:3], action)

    # --- Learning feedback loop ---
    # 1. Save new suggestions
    try:
        batch_id = str(hash(tuple(channel_urls)))
        saved_count = save_suggestions_from_strategy(strategy, batch_id=batch_id)
        _log('LEARNING: saved %d suggestions', saved_count)
    except Exception as exc:
        _log('LEARNING: failed to save suggestions: %s', exc)

    # 2. Run learning cycle (match prior suggestions against newly fetched videos)
    try:
        learning_result = run_learning_cycle(channels_data)
        _log('LEARNING: %d matches, %d insights', learning_result['matches_found'], learning_result['insights_generated'])
    except Exception as exc:
        _log('LEARNING: cycle failed: %s', exc)

    return {
        'channels': channels_data,
        'strategy': strategy,
        'agent_steps': agent_steps,
    }


def _fallback_batch_response(
    channel_urls: List[str],
    text: str,
    agent_steps: List[Dict[str, Any]],
) -> dict[str, Any]:
    """Build a fallback response when the batch agent didn't produce structured JSON."""
    strategy = {
        'trending_topics': [],
        'common_patterns': [],
        'content_gaps': [],
        'next_video_suggestions': [],
        'key_findings': ['Batch analysis incomplete — see summary for details'],
        'confidence': 0.3,
        'summary': text[:500],
    }
    return {
        'channels': [{'channel_url': url, 'title': None, 'top_videos': []} for url in channel_urls],
        'strategy': strategy,
        'agent_steps': agent_steps,
    }


def _analyze_dev_mode(channel_url: str) -> dict[str, Any]:
    """DEV_MODE: use sample data + local analysis (no LLM / no API calls)."""
    from ..services.analysis import build_video_features, derive_strategy

    sample = load_sample_data()
    if not sample:
        raise RuntimeError('sample_data.json required for DEV_MODE')

    channel_meta = sample.get('channel', {})
    videos_payload = sample.get('videos', [])[:10]

    channel_record = crud.upsert_channel(
        channel_url,
        channel_id=channel_meta.get('channelId'),
        title=channel_meta.get('title'),
    )
    channel_db_id = channel_record['id']

    features = build_video_features(videos_payload)
    for feat in features:
        crud.upsert_video(channel_db_id, {
            'video_id': feat.video_id,
            'title': feat.title,
            'published_at': feat.published_at,
            'views': feat.views,
            'likes': feat.likes,
            'comments': feat.comments,
            'thumbnail_url': feat.thumbnail_url,
            'captions': feat.captions,
            'performance_score': feat.performance_score,
        })

    strategy = derive_strategy(features, channel_record['channel_url'])
    summary = strategy.get('summary', '')
    crud.insert_analysis(channel_db_id, summary, strategy)

    findings = strategy.get('key_findings', [])
    action = strategy.get('action_plan', ['Iterate hooks'])[0]
    append_memory_entry(channel_record['channel_url'], findings, action)

    return {
        'strategy': strategy,
        'summary': summary,
        'channel': {
            'id': channel_db_id,
            'channel_url': channel_record['channel_url'],
            'title': channel_record.get('title'),
            'channel_id': channel_record.get('channel_id'),
        },
        'videos': [feat.__dict__ for feat in features],
        'agent_steps': [{'type': 'reasoning', 'content': 'DEV_MODE: used local sample data'}],
    }
