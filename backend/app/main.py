from __future__ import annotations

import json
import logging
import time
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import crud
from .config import settings
from .database import init_db
from .memory import append_memory_entry, read_recent_memory, reset_memory
from .schemas import (
    AddChannelRequest,
    AnalyzeChannelRequest,
    AnalyzeChannelResponse,
    AppendMemoryRequest,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    BatchHistoryDetail,
    BatchHistoryListItem,
    ChannelResponse,
    LearningInsightResponse,
    MemoryResponse,
    ResetMemoryRequest,
    SuggestionMatchResponse,
    ThumbnailRequest,
    ThumbnailResponse,
    VideoResponse,
    AgentStep,
)
from .services.agent import analyze_batch, analyze_channel
from .services.thumbnail import generate_thumbnail
from .utils import extract_channel_identifier

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

app = FastAPI(title='YouTube Strategy Agent', version='1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class MinuteRateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self._bucket: Dict[str, tuple[int, float]] = {}

    def check(self, key: str) -> None:
        now = time.time()
        count, window_start = self._bucket.get(key, (0, now))
        if now - window_start >= 60:
            count, window_start = 0, now
        if count >= self.max_per_minute:
            raise HTTPException(status_code=429, detail='Rate limit exceeded. Please slow down.')
        self._bucket[key] = (count + 1, window_start)


rate_limiter = MinuteRateLimiter(settings.rate_limit_per_min)


def rate_limit_dependency() -> None:
    rate_limiter.check('global')


@app.on_event('startup')
def on_startup() -> None:
    init_db()
    memory_snapshot = read_recent_memory()
    logger.info('Loaded %d memory lines into working context', len(memory_snapshot))


@app.post(f"{settings.api_prefix}/add-channel", response_model=ChannelResponse, dependencies=[Depends(rate_limit_dependency)])
def add_channel(payload: AddChannelRequest):
    identifier = extract_channel_identifier(payload.channel_url)
    channel = crud.upsert_channel(payload.channel_url, channel_id=identifier)
    if not channel:
        raise HTTPException(status_code=500, detail='Failed to store channel')
    return ChannelResponse(**dict(channel))


@app.get(f"{settings.api_prefix}/channels", response_model=list[ChannelResponse])
def list_channels_route():
    channels = crud.list_channels()
    return [ChannelResponse(**dict(row)) for row in channels]


@app.post(
    f"{settings.api_prefix}/analyze-channel",
    response_model=AnalyzeChannelResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
def analyze_channel_route(payload: AnalyzeChannelRequest):
    try:
        result = analyze_channel(payload.channel_url)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Analysis failed: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    strategy = result['strategy']
    summary = result['summary']
    return AnalyzeChannelResponse(
        strategy=strategy,
        summary=summary,
        channel=result['channel'],
        videos=result['videos'],
    )


@app.post(
    f"{settings.api_prefix}/analyze-batch",
    response_model=BatchAnalyzeResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
def analyze_batch_route(payload: BatchAnalyzeRequest):
    try:
        result = analyze_batch(payload.channel_urls)
    except Exception as exc:
        logger.exception('Batch analysis failed: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist to history
    try:
        crud.save_batch_history(
            channel_urls=payload.channel_urls,
            channels=result.get('channels', []),
            strategy=result.get('strategy', {}),
            agent_steps=result.get('agent_steps', []),
        )
    except Exception as exc:
        logger.warning('Failed to save batch history: %s', exc)

    return BatchAnalyzeResponse(
        channels=result.get('channels', []),
        strategy=result['strategy'],
        agent_steps=result.get('agent_steps', []),
    )


@app.post(f"{settings.api_prefix}/generate-thumbnail", response_model=ThumbnailResponse)
def generate_thumbnail_route(payload: ThumbnailRequest):
    try:
        result = generate_thumbnail(payload.title, payload.description)
    except Exception as exc:
        logger.exception('Thumbnail generation failed: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ThumbnailResponse(**result)


@app.get(f"{settings.api_prefix}/videos/{{channel_id}}", response_model=list[VideoResponse])
def list_videos(channel_id: int = Path(..., description='Internal channel id')):
    channel = crud.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail='Channel not found')
    videos = crud.get_videos_by_channel(channel_id)
    return [VideoResponse(**dict(row)) for row in videos]


@app.get(f"{settings.api_prefix}/history", response_model=list[BatchHistoryListItem])
def list_history():
    rows = crud.list_batch_history()
    items = []
    for row in rows:
        urls = row.get('channel_urls', '[]')
        items.append(BatchHistoryListItem(
            id=row['id'],
            created_at=row['created_at'],
            channel_urls=json.loads(urls) if isinstance(urls, str) else urls,
        ))
    return items


@app.get(f"{settings.api_prefix}/history/{{history_id}}", response_model=BatchHistoryDetail)
def get_history(history_id: int = Path(..., description='Batch history ID')):
    row = crud.get_batch_history_by_id(history_id)
    if not row:
        raise HTTPException(status_code=404, detail='History entry not found')
    return BatchHistoryDetail(
        id=row['id'],
        created_at=row['created_at'],
        channel_urls=json.loads(row['channel_urls']) if isinstance(row['channel_urls'], str) else row['channel_urls'],
        channels=json.loads(row['channels_json']) if isinstance(row['channels_json'], str) else row['channels_json'],
        strategy=json.loads(row['strategy_json']) if isinstance(row['strategy_json'], str) else row['strategy_json'],
        agent_steps=json.loads(row['agent_steps_json']) if isinstance(row['agent_steps_json'], str) else row['agent_steps_json'],
    )


@app.get(f"{settings.api_prefix}/learning/insights", response_model=list[LearningInsightResponse])
def get_learning_insights():
    rows = crud.list_learning_insights(limit=20)
    results = []
    for row in rows:
        evidence = row.get('evidence', '{}')
        results.append(LearningInsightResponse(
            id=row['id'],
            created_at=row['created_at'],
            insight_text=row['insight_text'],
            evidence=json.loads(evidence) if isinstance(evidence, str) else evidence,
        ))
    return results


@app.post(f"{settings.api_prefix}/learning/run")
def run_learning_manually():
    """Manually trigger the learning cycle against all stored videos."""
    from .services.learning import run_learning_cycle
    result = run_learning_cycle(channels_data=None)
    return result


@app.get(f"{settings.api_prefix}/learning/matches", response_model=list[SuggestionMatchResponse])
def get_learning_matches():
    rows = crud.list_suggestion_matches(limit=50)
    results = []
    for row in rows:
        results.append(SuggestionMatchResponse(
            id=row['id'],
            suggestion_id=row['suggestion_id'],
            suggestion_topic=row.get('suggestion_topic'),
            channel_id=row.get('channel_id'),
            video_id=row['video_id'],
            video_title=row.get('video_title'),
            matched_at=row['matched_at'],
            match_confidence=row.get('match_confidence', 0),
            views=row.get('views'),
            avg_views=row.get('avg_views'),
            performance_score=row.get('performance_score'),
            beat_average=bool(row.get('beat_average', 0)),
        ))
    return results


@app.get(f"{settings.api_prefix}/memory", response_model=MemoryResponse)
def get_memory():
    memory_lines = read_recent_memory()
    return MemoryResponse(memory=memory_lines)


@app.post(f"{settings.api_prefix}/memory")
def append_memory(payload: AppendMemoryRequest):
    entry = append_memory_entry(payload.channel_ref, payload.findings, payload.action)
    return JSONResponse({'entry': entry})


@app.post(f"{settings.api_prefix}/reset-memory")
def reset_memory_route(payload: ResetMemoryRequest):
    try:
        reset_memory(confirm=payload.confirm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({'status': 'ok'})
