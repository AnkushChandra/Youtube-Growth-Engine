from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AnyUrl, BaseModel, Field


class ChannelBase(BaseModel):
    channel_url: str


class AddChannelRequest(ChannelBase):
    pass


class ChannelResponse(BaseModel):
    id: int
    channel_url: str
    channel_id: Optional[str] = None
    title: Optional[str] = None
    last_checked: Optional[str] = None


class AnalyzeChannelRequest(BaseModel):
    channel_url: str = Field(..., alias='channelUrl')


class VideoResponse(BaseModel):
    id: int
    channel_id: int
    video_id: str
    title: Optional[str]
    published_at: Optional[str]
    views: Optional[int]
    likes: Optional[int]
    comments: Optional[int]
    thumbnail_url: Optional[str] = None
    captions: Optional[str]
    fetched_at: Optional[str]
    performance_score: Optional[float]


class AgentVideoResponse(BaseModel):
    """Video shape returned by the AI agent (no DB ids)."""
    videoId: Optional[str] = None
    video_id: Optional[str] = None
    title: Optional[str] = None
    publishedAt: Optional[str] = None
    published_at: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    thumbnailUrl: Optional[str] = None
    thumbnail_url: Optional[str] = None
    captions: Optional[str] = None
    performanceScore: Optional[float] = None
    performance_score: Optional[float] = None

    model_config = {'extra': 'allow'}


class AgentStep(BaseModel):
    """A single step in the agent's reasoning/tool-calling trace."""
    type: str
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result_preview: Optional[str] = None
    content: Optional[str] = None


class Strategy(BaseModel):
    key_findings: List[str]
    recommended_format: Dict[str, Any]
    action_plan: List[str]
    confidence: float
    summary: str


class AgentChannelResponse(BaseModel):
    """Channel shape returned by the agent (may not have DB id yet)."""
    id: Optional[int] = None
    channel_url: Optional[str] = None
    channel_id: Optional[str] = None
    title: Optional[str] = None

    model_config = {'extra': 'allow'}


class AnalyzeChannelResponse(BaseModel):
    strategy: Strategy
    summary: str
    channel: AgentChannelResponse
    videos: List[AgentVideoResponse] = []
    agent_steps: List[AgentStep] = []


class BatchAnalyzeRequest(BaseModel):
    channel_urls: List[str] = Field(..., alias='channelUrls', min_length=1, max_length=10)


class ChannelSummary(BaseModel):
    channel_url: str
    title: Optional[str] = None
    channel_id: Optional[str] = None
    top_videos: List[AgentVideoResponse] = []

    model_config = {'extra': 'allow'}


class NextVideoSuggestion(BaseModel):
    topic: str
    why: str
    reference_channels: List[str] = []
    estimated_appeal: Optional[str] = None

    model_config = {'extra': 'allow'}


class CrossChannelStrategy(BaseModel):
    trending_topics: List[str] = []
    common_patterns: List[str] = []
    content_gaps: List[str] = []
    next_video_suggestions: List[NextVideoSuggestion] = []
    key_findings: List[str] = []
    confidence: float = 0.5
    summary: str = ''

    model_config = {'extra': 'allow'}


class BatchAnalyzeResponse(BaseModel):
    channels: List[ChannelSummary] = []
    strategy: CrossChannelStrategy
    agent_steps: List[AgentStep] = []


class ThumbnailRequest(BaseModel):
    title: str
    description: str = ''


class ThumbnailResponse(BaseModel):
    image_base64: str
    mime_type: str = 'image/png'


class BatchHistoryListItem(BaseModel):
    id: int
    created_at: str
    channel_urls: List[str] = []


class BatchHistoryDetail(BaseModel):
    id: int
    created_at: str
    channel_urls: List[str] = []
    channels: List[ChannelSummary] = []
    strategy: CrossChannelStrategy
    agent_steps: List[AgentStep] = []


class LearningInsightResponse(BaseModel):
    id: int
    created_at: str
    insight_text: str
    evidence: Optional[Dict[str, Any]] = None


class SuggestionMatchResponse(BaseModel):
    id: int
    suggestion_id: str
    suggestion_topic: Optional[str] = None
    channel_id: Optional[str] = None
    video_id: str
    video_title: Optional[str] = None
    matched_at: str
    match_confidence: float = 0.0
    views: Optional[int] = None
    avg_views: Optional[float] = None
    performance_score: Optional[float] = None
    beat_average: Optional[bool] = None

    model_config = {'extra': 'allow'}


class MemoryResponse(BaseModel):
    memory: List[str]


class ResetMemoryRequest(BaseModel):
    confirm: bool


class AppendMemoryRequest(BaseModel):
    channel_ref: str
    findings: List[str] = []
    action: str = 'Manual note'
