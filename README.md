# YouTube Strategy Lab

An AI-powered multi-channel YouTube trend analysis tool. Feed it a list of YouTube channels, and it will fetch their latest videos with subtitles, analyze cross-channel trends, and suggest your next video topics — complete with AI-generated thumbnail previews.

![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20React%20%2B%20Gemini-blue)

## What It Does

1. **Multi-channel analysis** — Input up to 10 YouTube channel URLs. The AI agent fetches the last 5 videos from each channel, including full stats (views, likes, comments) and subtitle/caption text via the YouTube API.
2. **Cross-channel strategy** — Identifies trending topics, common patterns, content gaps, and key findings across all analyzed channels.
3. **Next video suggestions** — Recommends 3–5 specific video topics with reasoning, reference channels, and estimated audience appeal.
4. **AI thumbnail generation** — Generates YouTube-style thumbnail previews for each suggestion using Gemini's image generation model.
5. **Persistent memory** — The agent remembers findings from previous runs in a `memory.txt` file, building context over time.
6. **Continuously learning** — Tracks past AI suggestions, detects when a suggested topic is actually published by a tracked channel, measures performance vs channel baseline, and generates learned rules that improve future suggestions.
7. **Full agent trace** — See every tool call, API response, and reasoning step the AI agent takes in real time.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Frontend (React + Vite)           localhost:5173    │
│  ├── Analyze Page   — batch input, suggestions, strategy
│  ├── Data Page      — memory, learning log, tracked channels
│  ├── History Page   — past batch analysis results        │
│  └── Agent Trace    — live tool call / reasoning log │
└──────────────────────┬──────────────────────────────┘
                       │ /api/*
┌──────────────────────▼──────────────────────────────┐
│  Backend (FastAPI + Python)        localhost:4000    │
│  ├── agent.py       — Gemini LLM agent loop         │
│  ├── composio.py    — Composio YouTube tool wrapper  │
│  ├── thumbnail.py   — Gemini image generation        │
│  ├── learning.py    — feedback loop (match/score/learn)│
│  ├── database.py    — SQLite persistence             │
│  └── memory.py      — memory.txt read/write          │
└──────────┬────────────────────┬─────────────────────┘
           │                    │
    Composio API          Google Gemini API
   (YouTube tools)     (LLM + image generation)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, React Router, Axios |
| **Backend** | Python, FastAPI, Uvicorn |
| **LLM** | Google Gemini (`gemini-3-flash-preview`) |
| **Image Gen** | Google Gemini (`gemini-2.5-flash-image`) |
| **YouTube API** | Composio (OAuth2 connected account) |
| **Database** | SQLite (`data.db`) |
| **Memory** | Flat file (`memory.txt`) |

## Project Structure

```
Youtube-meta/
├── .env                          # API keys and config
├── memory.txt                    # Persistent agent memory
├── data.db                       # SQLite database
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py               # FastAPI endpoints
│       ├── config.py             # Settings from .env
│       ├── schemas.py            # Pydantic request/response models
│       ├── database.py           # SQLite connection + helpers
│       ├── crud.py               # DB operations (channels, videos, learning)
│       ├── memory.py             # memory.txt operations
│       ├── utils.py              # Channel URL parsing
│       └── services/
│           ├── agent.py          # Gemini agent loop (single + batch)
│           ├── composio.py       # Composio client + YouTube tools
│           ├── thumbnail.py      # Gemini image generation
│           ├── learning.py       # Feedback loop: match → score → insights
│           └── analysis.py       # Local analysis (DEV_MODE)
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx               # Router shell
        ├── main.jsx              # Entry point
        ├── styles.css            # Global styles
        ├── context/
        │   └── AppContext.jsx    # Shared state provider
        ├── components/
        │   ├── BatchChannelInput.jsx
        │   ├── ChannelList.jsx
        │   ├── NavMenu.jsx
        │   └── ProgressTimeline.jsx
        ├── pages/
        │   ├── AnalyzePage.jsx   # Main analysis page
        │   ├── DataPage.jsx      # Memory + learning log + channels
        │   ├── HistoryPage.jsx   # Past batch analysis results
        │   └── AgentTracePage.jsx
        └── lib/
            └── api.js            # Axios API calls
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Google Gemini API key](https://aistudio.google.com/apikey)
- A [Composio](https://composio.dev) account with a connected YouTube OAuth app

### 1. Environment variables

Create a `.env` file in the project root:

```env
COMPOSIO_API_KEY="your_composio_api_key"
GEMINI_API_KEY="your_gemini_api_key"
COMPOSIO_USER_ID="your_composio_user_id"
DEV_MODE=false
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 4000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze-batch` | Analyze multiple channels (last 5 videos + captions each) |
| `POST` | `/api/analyze-channel` | Analyze a single channel |
| `POST` | `/api/generate-thumbnail` | Generate a YouTube thumbnail for a video title |
| `GET` | `/api/channels` | List tracked channels |
| `POST` | `/api/add-channel` | Add a channel to tracking |
| `GET` | `/api/videos/:id` | Get stored videos for a channel |
| `GET` | `/api/memory` | Read agent memory |
| `POST` | `/api/memory` | Append to agent memory |
| `POST` | `/api/reset-memory` | Clear agent memory |
| `GET` | `/api/history` | List past batch analyses |
| `GET` | `/api/history/:id` | Get a specific batch analysis |
| `GET` | `/api/learning/insights` | Get learned insights from the feedback loop |
| `GET` | `/api/learning/matches` | Get suggestion→video matches with scores |
| `POST` | `/api/learning/run` | Manually trigger the learning cycle |

## How the Agent Works

The batch analysis agent runs a multi-turn conversation with Gemini, equipped with 7 YouTube tools via Composio:

1. **YOUTUBE_GET_CHANNEL_ID_BY_HANDLE** — Resolve `@handle` to channel ID
2. **YOUTUBE_LIST_CHANNEL_VIDEOS** — Get the last 5 videos
3. **YOUTUBE_VIDEO_DETAILS** — Fetch views, likes, comments per video
4. **YOUTUBE_LIST_CAPTION_TRACK** — Find available subtitle tracks
5. **YOUTUBE_LOAD_CAPTIONS** — Download actual subtitle text
6. **YOUTUBE_GET_CHANNEL_STATISTICS** — Subscriber/view counts
7. **YOUTUBE_SEARCH_YOU_TUBE** — Search for channels/videos

The agent processes channels one at a time, gathers all data, then produces a structured JSON strategy with trending topics, patterns, content gaps, and next video suggestions. Results are persisted to SQLite and memory.

## Continuously Learning

The system implements an outcome-driven strategy feedback loop:

1. **Save suggestions** — After each batch analysis, the AI's topic suggestions are persisted with keywords and metadata.
2. **Match** — On subsequent runs (or manual trigger), the system compares all stored video titles against past suggestions using Jaccard similarity + substring matching (threshold: 0.28).
3. **Score** — Matched videos are scored against their channel's baseline: `view_ratio × engagement_multiplier` (likes/comments rates, clamped 0.7–1.5x).
4. **Learn** — Patterns are detected across high/low performers (framing styles, keyword clusters, multi-channel signals) and written as concise rules to both the DB and `memory.txt`.
5. **Adapt** — On the next batch analysis, learned rules are injected into the agent's system prompt so future suggestions improve.

The **Data Page** shows a Learning Log with insights and a matches table. The **Analyze Page** shows "Learned" or "Experimental" badges on each suggestion.

## Debugging

Agent debug logs are written to `backend/agent_debug.log` (appended across restarts). This includes every turn, tool call with arguments, tool responses, learning cycle results, and final parsed output.

## License

MIT
