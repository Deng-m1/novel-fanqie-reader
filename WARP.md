# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Fanqie Reader (番茄小说阅读器)** is a web application for crawling, managing, and reading novels from the Fanqie (番茄小说) platform. The system uses a distributed, containerized architecture with:

- **Backend**: Flask API with Celery workers for async novel downloading
- **Frontend**: Vue 3 SPA with real-time WebSocket updates
- **Database**: MySQL for persistent storage
- **Message Broker**: Redis for Celery task queue and SocketIO messaging
- **Deployment**: Docker Compose orchestration

---

## Essential Commands

### Development Setup

**Prerequisites**: Docker Engine and Docker Compose v2+

1. **Initial Setup with Environment Configuration**:
```bash
# Copy .env template and configure required variables
# Required: DB_NAME, DB_USER, DB_PASSWORD, DB_ROOT_PASSWORD, JWT_SECRET_KEY, FLASK_SECRET_KEY
# Optional: TZ, FLASK_ENV, FLASK_LOG_LEVEL, SQLALCHEMY_ECHO, NOVEL_* settings

# Start all services (builds images on first run)
docker-compose up -d --build
```

2. **View Logs**:
```bash
# All services
docker-compose logs -f

# Specific service (backend, celery_worker, mysql, redis, frontend)
docker-compose logs -f backend
docker-compose logs -f celery_worker
```

3. **Restart Services**:
```bash
# All services
docker-compose restart

# Specific service
docker-compose restart backend
```

4. **Stop Services**:
```bash
docker-compose down
```

5. **Update Code and Rebuild**:
```bash
git pull
docker-compose up -d --build
```

### Frontend Development (Standalone)

Navigate to `frontend/` directory:

```bash
# Install dependencies (uses Bun)
bun install

# Run development server with hot-reload
bun dev

# Type checking
bun run type-check

# Build for production
bun run build

# Lint and fix
bun lint

# Format code
bun run format
```

### Backend Development (Standalone - Advanced)

**Note**: Typically run via Docker Compose. For local development:

```bash
# From backend/ directory, ensure Python 3.13+ and dependencies installed
pip install -r requirements.txt

# Set environment variables (see .env file)
# Start Flask app
gunicorn --bind 0.0.0.0:5000 --worker-class=eventlet --log-level=INFO "app:app"

# Start Celery worker (separate terminal)
celery -A celery_init:celery_app worker --loglevel=INFO -O fair
```

### Database Access

```bash
# Connect to MySQL (from host machine)
mysql -h 127.0.0.1 -P 3307 -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME}

# Or use any MySQL client pointing to localhost:3307
```

### Service URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:5000
- **MySQL**: localhost:3307
- **Redis**: localhost:6379

---

## Architecture Overview

### System Flow

1. **User Authentication**: JWT-based auth via `/api/auth/*` endpoints
2. **Novel Search**: Frontend queries backend `/api/search`, which scrapes Fanqie platform
3. **Download Task Creation**: User adds novel → Creates `DownloadTask` in DB → Dispatches Celery task
4. **Background Processing**: Celery worker picks up task, uses `novel_downloader` module to:
   - Fetch book metadata and chapter list
   - Download chapter content (with encryption handling)
   - Save to database (`Novel`, `Chapter` models)
   - Generate EPUB file
   - Perform word frequency analysis and generate word cloud
5. **Real-time Updates**: Backend emits `task_update` via Flask-SocketIO, frontend receives via WebSocket
6. **Reading Interface**: Frontend fetches chapters from `/api/novels/<id>/chapters/<cid>`, renders content

### Key Components

#### Backend (`backend/`)

**Entry Point**: `app.py`
- Flask application with JWT authentication, SocketIO support
- Routes defined for novels, chapters, tasks, stats, auth
- Global exception handling with standardized JSON error responses

**Task Processing**: `tasks.py`
- Celery tasks: `process_novel_task` (download & save novel), `analyze_novel_task` (word stats/cloud)
- Uses `ContextTask` base class (from `celery_init.py`) to ensure Flask app context is available
- Updates `DownloadTask` status in DB and emits SocketIO events during execution

**Models**: `models.py`
- `User`: User accounts with password hashing
- `Novel`: Novel metadata (title, author, description, tags, cover URL, total chapters)
- `Chapter`: Individual chapter content linked to novels
- `DownloadTask`: Tracks download job status (PENDING → DOWNLOADING → PROCESSING → COMPLETED/FAILED/TERMINATED)
- `WordStat`: Word frequency data for novel analysis

**Configuration**: `config.py`
- Loads settings from `.env` file using `python-dotenv`
- Maps environment variables to `Settings` class
- `get_downloader_config()` helper function prepares config dict for `novel_downloader` module

**Auth**: `auth.py` (Blueprint)
- `/api/auth/register`: Create new user
- `/api/auth/login`: Returns JWT access token
- `/api/auth/me`: Get current user profile

**Celery Init**: `celery_init.py`
- Creates Celery app instance with Redis broker/backend
- Defines `ContextTask` to wrap task execution in Flask app context
- `configure_celery(app)` function links Celery with Flask config

**Analysis**: `analysis.py`
- `update_word_stats()`: Jieba word segmentation, frequency counting, saves to `WordStat` table
- `generate_word_cloud()`: Uses `wordcloud` library to create PNG image

**Novel Downloader Module**: `novel_downloader/`
- Standalone module for crawling Fanqie novels
- **Key Classes**:
  - `GlobalContext` (in `base_system/context.py`): Singleton config manager, initialized in tasks
  - `NetworkClient` (in `network_parser/network.py`): HTTP client for Fanqie API/website, handles retries and rate limiting
  - `ChapterDownloader` (in `network_parser/downloader.py`): Multi-threaded chapter fetching with encryption decryption
  - `BookManager` (in `book_parser/book_manager.py`): Orchestrates download process, manages status files
  - `EPUBGenerator` (in `book_parser/epub_generator.py`): Creates EPUB files using `ebooklib`
- **Official API Support**: Can use official Fanqie API if `NOVEL_USE_OFFICIAL_API=True` and `NOVEL_IID` is set (see `offical_tools/`)

#### Frontend (`frontend/`)

**Main Entry**: `src/main.ts`
- Initializes Vue app, router, Pinia store, Element Plus UI library

**API Client**: `src/api.ts`
- Axios instance with JWT interceptor (adds `Authorization: Bearer <token>` header)
- Type-safe API wrappers: `Auth`, `Novels`, `Tasks`, `Stats`
- `WebSocketAPI` module for SocketIO client, handles `task_update` events

**Router**: `src/router/index.ts`
- `HomeView` (with nested routes): Dashboard, Novels, NovelDetail, ChapterDetail, Search, Upload, Tasks
- `AuthView`: Login/Register page
- Route guards: Redirects unauthenticated users for protected routes (`/tasks`, `/upload`)

**State Management**: `src/store/index.ts`
- Pinia store for auth state (`accessToken`, `isAuthenticated`, `user`)
- WebSocket connection management tied to auth state

**Views**:
- `DashboardView.vue`: Statistics dashboard with ECharts (upload trends, genre distribution)
- `SearchView.vue`: Novel search interface
- `NovelsView.vue`: User's novel library (paginated list)
- `NovelDetailView.vue`: Novel info, chapter list, download EPUB, view word cloud
- `ChapterView.vue`: Chapter content reader
- `TasksView.vue`: Download task list with real-time progress, terminate/delete/redownload actions

---

## Data Models & Relationships

```
User (1) ─── (M) DownloadTask ─── (1) Novel ─── (M) Chapter
                                             └── (M) WordStat
```

- **User**: Owns multiple download tasks
- **Novel**: Can have multiple download tasks from different users, has many chapters and word stats
- **DownloadTask**: Links user to novel, tracks Celery task ID and status
- **Chapter**: Belongs to one novel, stores chapter content
- **WordStat**: Word frequency data for a novel

---

## Task Status Lifecycle

```
PENDING → DOWNLOADING → PROCESSING → COMPLETED
          ↓                         ↓
          FAILED                 FAILED
          ↓
          TERMINATED (user-initiated cancellation)
```

- **PENDING**: Task created, waiting for worker
- **DOWNLOADING**: Fetching book info and chapters
- **PROCESSING**: Generating EPUB, analyzing word frequency
- **COMPLETED**: Novel fully downloaded and processed
- **FAILED**: Error occurred during download/processing
- **TERMINATED**: User cancelled task via `/api/tasks/<id>/terminate`

---

## Environment Variables

**Required**:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`: MySQL credentials
- `JWT_SECRET_KEY`: JWT token signing key (use strong random string)
- `FLASK_SECRET_KEY`: Flask session secret (use strong random string)

**Optional (with defaults)**:
- `FLASK_ENV`: `production` or `development`
- `FLASK_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `SQLALCHEMY_ECHO`: `True` to log SQL queries (default: `False`)
- `TZ`: Timezone (default: `UTC`, recommended: `Asia/Shanghai`)
- `NOVEL_MAX_WORKERS`: Concurrent chapter downloads (default: `5`)
- `NOVEL_REQUEST_TIMEOUT`: HTTP request timeout in seconds (default: `20`)
- `NOVEL_MAX_RETRIES`: Max retry attempts for failed requests (default: `3`)
- `NOVEL_MIN_WAIT_TIME`, `NOVEL_MAX_WAIT_TIME`: Rate limiting delays in ms (defaults: `800`, `1500`)
- `NOVEL_FORMAT`: Output format, `epub` or `txt` (default: `epub`)
- `NOVEL_USE_OFFICIAL_API`: `True` to use official Fanqie API (default: `True`)
- `NOVEL_IID`: Device identifier for official API (optional, generated if not set)
- `NOVEL_IID_SPAWN_TIME`: IID generation timestamp (auto-generated)

---

## Common Development Patterns

### Adding a New API Endpoint

1. **Backend (`app.py`)**:
   - Define route function with `@app.route()` or `@auth_bp.route()` decorator
   - Add `@jwt_required()` if authentication needed
   - Use `get_jwt_identity()` to get current user ID
   - Return `jsonify()` response

2. **Frontend (`api.ts`)**:
   - Add TypeScript interface for request/response data
   - Add function to appropriate API module (e.g., `Novels`, `Tasks`)
   - Use `requests.get/post/delete` helpers

3. **Frontend View**:
   - Import API function from `@/api.ts`
   - Call in `onMounted`, event handler, or composable
   - Handle error responses (check for `error` field)

### Creating a New Celery Task

1. **Define in `tasks.py`**:
```python
@celery_app.task(bind=True, name="tasks.my_task")
def my_task(self, arg1, arg2):
    # Task logic here
    # Use current_app.logger for logging
    # Update DB as needed
    return {"status": "SUCCESS", "result": "..."}
```

2. **Dispatch from API endpoint**:
```python
from tasks import my_task
result = my_task.apply_async(args=[arg1, arg2])
celery_task_id = result.id
```

3. **ContextTask automatically provides Flask app context**, so DB operations work seamlessly

### WebSocket Communication

- Backend emits events with `socketio.emit(event_name, data, room=f"user_{user_id}")`
- Frontend registers handler with `WebSocketAPI.onTaskUpdate(callback)`
- Authentication required: Frontend sends JWT token via `authenticate` event after connection

### Database Migrations (Manual)

**No automatic migration tool (like Alembic) is configured.** Schema changes require manual coordination:

1. Update models in `models.py`
2. Manually write SQL migration script
3. Apply via MySQL client or Python script using `db.session.execute()`
4. **Consider adding Flask-Migrate for automatic migrations in future**

---

## Troubleshooting

### Issue: Celery tasks not executing
- Check Celery worker logs: `docker-compose logs -f celery_worker`
- Verify Redis is running: `docker-compose ps redis`
- Ensure `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are correct in `.env`

### Issue: WebSocket connection fails
- Check CORS settings in `app.py` (`cors_allowed_origins` in SocketIO init)
- Verify frontend connects to correct URL (default: same origin as frontend)
- Check authentication token is valid (not expired)

### Issue: Database connection errors
- Verify MySQL container is healthy: `docker-compose ps mysql`
- Check database credentials in `.env` match `docker-compose.yml`
- Ensure port 3307 is not already in use

### Issue: Novel download fails
- Check `novel_downloader` logs in Celery worker output
- Verify network connectivity to Fanqie platform
- Check rate limiting settings (`NOVEL_MIN_WAIT_TIME`, `NOVEL_MAX_WAIT_TIME`)
- If using official API, verify `NOVEL_IID` is valid

### Issue: Frontend build errors
- Ensure Bun is installed (used instead of npm/yarn)
- Clear cache: `rm -rf node_modules .vite && bun install`
- Check TypeScript errors: `bun run type-check`

---

## Testing

**Note**: No automated test suite is currently implemented. Testing is manual via:

1. **API Testing**: Use tools like Postman, curl, or HTTPie to test backend endpoints
2. **Integration Testing**: Run full Docker Compose stack and test workflows via frontend UI
3. **Database Verification**: Query MySQL directly to verify data consistency

**Recommendation**: Add pytest for backend unit tests and Vitest for frontend component tests in future iterations.

---

## Security Considerations

- **JWT Secrets**: Always use strong, randomly generated secrets in production (never use default values)
- **Database Credentials**: Use strong passwords, restrict access to localhost/trusted IPs
- **CORS**: Configure `cors_allowed_origins` in SocketIO to match production frontend domain
- **Rate Limiting**: Adjust `NOVEL_MIN_WAIT_TIME`/`NOVEL_MAX_WAIT_TIME` to avoid being blocked by Fanqie platform
- **User Passwords**: Stored with Werkzeug's `generate_password_hash` (PBKDF2-SHA256)

---

## Project Structure Summary

```
fanqie-reader/
├── backend/
│   ├── app.py                  # Flask app, main API routes
│   ├── tasks.py                # Celery background tasks
│   ├── models.py               # SQLAlchemy ORM models
│   ├── config.py               # Configuration from .env
│   ├── auth.py                 # Auth blueprint (login/register)
│   ├── celery_init.py          # Celery app initialization
│   ├── database.py             # SQLAlchemy db instance
│   ├── analysis.py             # Word stats and word cloud generation
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile              # Backend container image
│   └── novel_downloader/       # Novel crawling module
│       └── novel_src/
│           ├── base_system/    # Config, logging, storage
│           ├── network_parser/ # HTTP client, chapter downloader
│           ├── book_parser/    # EPUB generator, book manager
│           └── offical_tools/  # Official API integration
├── frontend/
│   ├── src/
│   │   ├── main.ts             # Vue app entry
│   │   ├── App.vue             # Root component
│   │   ├── api.ts              # API client and types
│   │   ├── router/             # Vue Router config
│   │   ├── store/              # Pinia state management
│   │   └── views/              # Page components
│   ├── package.json            # Frontend dependencies (Bun)
│   ├── vite.config.ts          # Vite build config
│   └── Dockerfile              # Frontend container image
├── docker-compose.yml          # Multi-service orchestration
├── .env                        # Environment variables (not in git)
└── README.md                   # Project documentation (Chinese)
```

---

## Additional Notes

- **Language**: Most user-facing text, comments, and README are in Chinese. Code (variable names, functions) is primarily English.
- **Novel Source**: This project is specifically designed for the Fanqie (番茄小说) platform. Adapting to other novel sites requires modifying the `novel_downloader` module.
- **Performance**: Adjust `NOVEL_MAX_WORKERS` based on network speed and server resources. Too many workers may trigger rate limiting.
- **EPUB Generation**: Uses `ebooklib` Python library. EPUB files saved to `NOVEL_SAVE_PATH` (default: `backend/data/novel_downloads/`)
- **Word Clouds**: Generated using `jieba` for Chinese word segmentation and `wordcloud` for image creation. Saved to `DATA_BASE_PATH/wordclouds/`
