# URL Shortening Service

A high-performance URL shortening service built with FastAPI, featuring Redis caching, async database operations, and eventual consistency for click tracking.

## Features

- **URL Shortening**: Convert long URLs into short, shareable codes using base62 encoding
- **Redis Caching**: Multi-layer caching strategy for URLs, metadata, and click counters
- **Async/Await**: Fully asynchronous database and Redis operations
- **Rate Limiting**: Built-in rate limiting using SlowAPI
- **Click Analytics**: Track clicks with eventual consistency via Redis counters
- **Expiration Support**: Optional TTL for shortened URLs with automatic cleanup
- **Domain Exceptions**: Clean error handling with custom exception types
- **Background Processing**: Celery workers for periodic click count flushing

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Cache**: Redis (with namespaced keys)
- **Task Queue**: Celery with Redis broker
- **Rate Limiting**: SlowAPI
- **Validation**: Pydantic v2

## Project Structure

```
URL_Shortening_service/
├── db/
│   └── database.py          # Async database configuration
├── models/
│   ├── url.py               # URL database model
│   └── user.py              # User model (future auth)
├── routes/
│   ├── __init__.py
│   └── url.py               # URL endpoints
├── schemas/
│   └── url_schemas.py       # Pydantic request/response models
├── services/
│   ├── exceptions.py        # Domain exceptions
│   ├── tasks.py             # Celery tasks
│   └── url_service.py       # Business logic
├── utils/
│   └── encoder.py           # Base62 encoding
├── logs/                     # Application logs
├── main.py                   # FastAPI application
├── streamlit_app.py          # Streamlit frontend UI
├── start.sh                  # Start all services
├── stop.sh                   # Stop all services
├── requirements.txt
└── .env                      # Environment variables
```

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd URL_Shortening_service
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables in `.env`:
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/shortly_db

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=short:
REDIS_CLICK_PREFIX=url:clicks:
REDIS_META_PREFIX=url:meta:

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT=5/minute
RATE_LIMIT_BURST=10
```

5. Initialize the database:
```bash
python -c "from db.database import init_db; import asyncio; asyncio.run(init_db())"
```

## Running the Application

### Quick Start (All Services)

Use the convenience scripts to start/stop all services at once:

```bash
# Start FastAPI, Celery, and Streamlit
./start.sh

# Stop all services
./stop.sh
```

This will start:
- **FastAPI**: `http://localhost:8001`
- **Streamlit UI**: `http://localhost:8501`
- **Celery Worker + Beat**: Background task processing

### Manual Start

#### Start the API server:
```bash
uvicorn main:app --port 8001 --reload
```

The API will be available at `http://localhost:8001`

#### Start Celery worker (for background tasks):
```bash
celery -A services.tasks.celery_app worker --loglevel=info
```

#### Start Celery Beat (periodic task scheduler):
```bash
celery -A services.tasks.celery_app beat --loglevel=info
```

#### Start Streamlit Frontend:
```bash
streamlit run streamlit_app.py --server.port 8501
```

## API Endpoints

### Create Short URL
```http
POST /url/create
Content-Type: application/json

{
  "original_url": "https://www.example.com/some/long/path",
  "custom_alias": "myalias",
  "expire_in_days": 30
}
```

**Response:**
```json
{
  "short_code": "abc123",
  "long_url": "https://www.example.com/some/long/path"
}
```

### Redirect to Long URL
```http
GET /r/{short_code}
```

Returns a `302` redirect to the original URL and increments the click counter.

### Get URL Metadata
```http
GET /url/{short_code}
```

**Response:**
```json
{
  "long_url": "https://www.example.com/some/long/path",
  "short_code": "abc123",
  "clicks": 42,
  "created_at": "2024-01-01T12:00:00Z",
  "expires_at": "2024-01-31T12:00:00Z"
}
```

### Error Responses

- `404`: Short code not found
- `410`: URL has expired
- `500`: Internal server error

## Architecture Highlights

### Redis Caching Strategy

1. **URL Cache** (`short:{code}`): Stores long URL for fast redirects with TTL set from DB expiration
2. **Click Counters** (`url:clicks:{code}`): Eventual consistency for high-write performance
3. **Metadata Cache** (`url:meta:{code}`): URL metadata and click deltas cached with the same TTL as the URL

#### Caching Behavior
- Best practice: Do not store `expires_at` in Redis; rely on key TTL.
- On Redis hit: Serve directly from cache without querying the database.
- On Redis miss: Query DB, validate expiration, then cache with appropriate TTL.
- Metadata cache excludes `expires_at` to avoid DB checks on cache hits; it is returned only when fetched from DB on cache miss.

### Eventual Consistency

Click increments are written to Redis counters immediately, then periodically flushed to PostgreSQL in batches via Celery tasks. This provides:
- Low latency for redirects
- High write throughput
- Reduced database load

### Domain-Driven Errors

Custom exceptions (`UrlExpiredError`, `ShortCodeNotFoundError`) are raised in the service layer and mapped to HTTP status codes at the API boundary.

## Architecture Diagrams

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           URL Shortening Service                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│   │   Streamlit  │         │   FastAPI    │         │    Celery    │       │
│   │   Frontend   │────────▶│   Backend    │────────▶│   Worker     │       │
│   │  (Port 8501) │         │  (Port 8001) │         │   + Beat     │       │
│   └──────────────┘         └──────┬───────┘         └──────┬───────┘       │
│                                   │                        │               │
│                    ┌──────────────┼────────────────────────┘               │
│                    │              │                                        │
│                    ▼              ▼                                        │
│            ┌──────────────┐  ┌──────────────┐                              │
│            │    Redis     │  │  PostgreSQL  │                              │
│            │   (Cache +   │  │  (Persistent │                              │
│            │    Broker)   │  │   Storage)   │                              │
│            └──────────────┘  └──────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### URL Shortening Flow

```
┌────────┐      POST /url/create       ┌──────────┐
│ Client │ ───────────────────────────▶│ FastAPI  │
└────────┘                             └────┬─────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       ▼                       │
                    │            ┌─────────────────────┐            │
                    │            │  Generate Short Code │            │
                    │            │  (Base62 Encoding)   │            │
                    │            └──────────┬──────────┘            │
                    │                       │                       │
                    │         ┌─────────────┴─────────────┐         │
                    │         ▼                           ▼         │
                    │  ┌─────────────┐             ┌───────────┐    │
                    │  │  PostgreSQL │             │   Redis   │    │
                    │  │  (persist)  │             │  (cache)  │    │
                    │  └─────────────┘             └───────────┘    │
                    │                                               │
                    └───────────────────────────────────────────────┘
                                            │
                                            ▼
                               ┌────────────────────────┐
                               │ Return: { short_code } │
                               └────────────────────────┘
```

### URL Redirect Flow

```
┌────────┐       GET /r/{code}        ┌──────────┐
│ Client │ ──────────────────────────▶│ FastAPI  │
└────────┘                            └────┬─────┘
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │   Check Redis   │
                                  │     Cache       │
                                  └────────┬────────┘
                                           │
                         ┌─────────────────┴─────────────────┐
                         │                                   │
                    Cache Hit                           Cache Miss
                         │                                   │
                         │                                   ▼
                         │                        ┌─────────────────┐
                         │                        │ Query PostgreSQL│
                         │                        │  + Cache Result │
                         │                        └────────┬────────┘
                         │                                 │
                         └─────────────┬───────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  Increment Click    │
                            │  Counter (Redis)    │
                            └──────────┬──────────┘
                                       │
                                       ▼
                             ┌───────────────────┐
                             │  302 Redirect to  │
                             │    Original URL   │
                             └───────────────────┘
```

### Click Tracking (Eventual Consistency)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Click Tracking Pipeline                           │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    Immediate     ┌─────────┐    Periodic    ┌───────────┐  │
│  │ Redirect │ ──────────────▶ │  Redis  │ ─────────────▶ │PostgreSQL │  │
│  │ Request  │   Increment     │ Counter │   Batch Flush  │   (sync)  │  │
│  └─────────┘                  └─────────┘   (Celery Beat) └───────────┘  │
│                                                                          │
│  Benefits:                                                               │
│  • Low latency redirects (no DB write on each request)                   │
│  • High throughput (Redis handles concurrent increments)                 │
│  • Eventual consistency (clicks sync to DB periodically)                 │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Interaction

```
                              ┌─────────────────────────────────┐
                              │          User Interfaces        │
                              ├─────────────────────────────────┤
                              │  Streamlit UI  │  API Clients   │
                              └────────┬───────┴───────┬────────┘
                                       │               │
                                       ▼               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Layer                               │
├──────────────────────────────────────────────────────────────────────────┤
│  routes/url.py  │  Rate Limiter (SlowAPI)  │  Exception Handlers        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            Service Layer                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  url_service.py  │  exceptions.py  │  tasks.py (Celery)                 │
└────────────┬─────────────────────────────────────────┬───────────────────┘
             │                                         │
             ▼                                         ▼
┌────────────────────────┐                 ┌────────────────────────┐
│      Data Layer        │                 │     Cache Layer        │
├────────────────────────┤                 ├────────────────────────┤
│  models/url.py         │                 │  Redis                 │
│  models/user.py        │                 │  • URL Cache           │
│  db/database.py        │                 │  • Click Counters      │
│  PostgreSQL + asyncpg  │                 │  • Metadata Cache      │
└────────────────────────┘                 └────────────────────────┘
```

## Interactive API Documentation

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Development

### Run tests:
```bash
pytest
```

### Type checking:
```bash
mypy .
```

### Format code:
```bash
black .
ruff check --fix .
```

## Streamlit Frontend

The project includes a Streamlit-based web UI for easy URL shortening:

```
┌─────────────────────────────────────────────────────┐
│              URL Shortener (Streamlit)              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Long URL: [____________________________]           │
│                                                     │
│  Expire in days: [7]                                │
│                                                     │
│  [      Shorten      ]                              │
│                                                     │
│  ✅ Short URL created                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ http://localhost:8001/r/abc123              │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Simple, user-friendly interface
- Configurable API base URL
- Adjustable URL expiration
- Direct link to shortened URL

## Future Enhancements

- [ ] User authentication with JWT
- [ ] URL validation and safety checks
- [ ] Analytics dashboard
- [ ] QR code generation
- [ ] API key management
- [ ] Webhook notifications
- [ ] Bulk URL shortening
- [ ] URL edit/delete functionality

## License

MIT
