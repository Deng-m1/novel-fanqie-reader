# backend/app.py
import logging
import sys
import os
import re
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify, send_file, current_app, abort
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    get_jwt_identity,
    verify_jwt_in_request,
)
from flask_jwt_extended.exceptions import JWTDecodeError, NoAuthorizationError
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from celery.result import AsyncResult
from sqlalchemy import desc, asc, text as sql_text
from werkzeug.exceptions import HTTPException

from database import db as _db
from models import Novel, Chapter, WordStat, User, DownloadTask, TaskStatus
from config import settings, get_downloader_config
from auth import auth_bp
from celery_init import celery_app, configure_celery

try:
    from novel_downloader.novel_src.base_system.context import GlobalContext
    from novel_downloader.novel_src.network_parser.network import NetworkClient

    DOWNLOADER_AVAILABLE = True
except ImportError as e:
    logging.getLogger("app.init").error(f"Failed novel_downloader import: {e}")
    DOWNLOADER_AVAILABLE = False

# --- Logging Setup ---
log_level_str = os.getenv("FLASK_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
handler.setFormatter(formatter)

# --- Flask App Init ---
app = Flask(__name__)
app.config.from_object(settings)

app.logger.addHandler(handler)
app.logger.setLevel(log_level)
app.logger.propagate = False
app.logger.info(f"Flask application starting with log level {log_level_str}")

# --- Extensions Init ---
_db.init_app(app)
jwt = JWTManager(app)
socketio = SocketIO(
    app,
    message_queue=settings.CELERY_BROKER_URL,
    async_mode="eventlet",
    cors_allowed_origins="http://localhost:5173",
)
app.register_blueprint(auth_bp)
configure_celery(app)

# --- Database Creation ---
try:
    with app.app_context():
        app.logger.info("Creating database tables if they don't exist...")
        _db.create_all()
        app.logger.info("Database tables checked/created.")
except Exception as e:
    app.logger.error(f"Error during _db.create_all(): {e}", exc_info=True)

# --- Import Tasks ---
try:
    from tasks import process_novel_task, analyze_novel_task

    app.logger.info("Task functions imported successfully")
except ImportError as e:
    app.logger.error(f"Failed to import task functions: {e}", exc_info=True)


# --- JWT Loaders ---
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    try:
        user_id = int(identity)
        return User.query.get(user_id)
    except (ValueError, TypeError):
        app.logger.warning(f"Invalid user identity format in JWT: {identity}")
        return None


@jwt.user_lookup_error_loader
def custom_user_lookup_error(_jwt_header, jwt_data):
    identity = jwt_data.get("sub", "<unknown>")
    app.logger.warning(
        f"User lookup failed for identity: {identity}. User might not exist."
    )
    return jsonify(
        msg="用户不存在或令牌关联的用户已被删除", error="user_not_found"
    ), 401


@jwt.unauthorized_loader
def missing_token_callback(error_string):
    app.logger.debug(f"Unauthorized - Missing JWT: {error_string}")
    return jsonify(
        msg=f"需要提供授权令牌 ({error_string})", error="authorization_required"
    ), 401


@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    app.logger.debug(f"Unauthorized - Invalid JWT: {error_string}")
    return jsonify(
        msg=f"无效或格式错误的令牌 ({error_string})", error="invalid_token"
    ), 401


@jwt.expired_token_loader
def expired_token_callback(_jwt_header, _jwt_payload):
    app.logger.debug("Unauthorized - Expired JWT")
    return jsonify(msg="令牌已过期，请重新登录", error="token_expired"), 401


@jwt.needs_fresh_token_loader
def token_not_fresh_callback(_jwt_header, _jwt_payload):
    app.logger.debug("Unauthorized - Fresh token required")
    return jsonify(msg="需要提供刷新令牌", error="fresh_token_required"), 401


@jwt.revoked_token_loader
def revoked_token_callback(_jwt_header, _jwt_payload):
    app.logger.debug("Unauthorized - Revoked token")
    return jsonify(msg="令牌已被撤销", error="token_revoked"), 401


# --- SocketIO Handlers ---
connected_users = {}


@socketio.on("connect")
def handle_connect():
    app.logger.info(f"Client connected: {request.sid}")
    emit("request_auth", {"message": "Please authenticate with your JWT token."})


@socketio.on("authenticate")
def handle_authenticate(data):
    token = data.get("token")
    sid = request.sid
    if not token:
        app.logger.warning(f"Auth attempt failed for SID {sid}: No token.")
        emit(
            "auth_response",
            {"success": False, "message": "Authentication token required."},
        )
        disconnect(sid)
        return

    try:
        with app.app_context():
            original_headers = request.headers
            try:
                request.headers = {"Authorization": f"Bearer {token}"}
                verify_jwt_in_request(optional=False)
                user_identity = get_jwt_identity()
                user_id = int(user_identity)
                app.logger.info(
                    f"SID {sid} authenticated successfully for user_id {user_id}."
                )

                leave_room(f"user_{user_id}", sid=sid)
                join_room(f"user_{user_id}", sid=sid)
                connected_users[user_id] = sid
                app.logger.info(
                    f"User {user_id} (SID: {sid}) joined room 'user_{user_id}'."
                )
                emit(
                    "auth_response",
                    {"success": True, "message": "Authentication successful."},
                )
            except (JWTDecodeError, NoAuthorizationError, Exception) as e:
                app.logger.error(f"WebSocket JWT Auth failed for SID {sid}: {e}")
                error_message = "Invalid or expired token."
                if isinstance(e, JWTDecodeError):
                    error_message = "Invalid token format."
                elif isinstance(e, NoAuthorizationError):
                    error_message = "Authorization header missing or invalid."
                emit("auth_response", {"success": False, "message": error_message})
                disconnect(sid)
            finally:
                request.headers = original_headers
    except Exception as e:
        app.logger.error(
            f"Error during WebSocket auth for SID {sid}: {e}", exc_info=True
        )
        emit(
            "auth_response",
            {"success": False, "message": "Internal authentication error."},
        )
        disconnect(sid)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    user_id = None
    for uid, stored_sid in list(connected_users.items()):
        if stored_sid == sid:
            user_id = uid
            del connected_users[user_id]
            app.logger.info(f"User {user_id} (SID: {sid}) disconnected.")
            break
    if user_id is None:
        app.logger.info(f"Unauthenticated client disconnected: {sid}")


def emit_task_update(user_id: int, task_data: dict):
    room = f"user_{user_id}"
    if user_id in connected_users:
        # logger = current_app.logger # logger is available via app context
        socketio.emit("task_update", task_data, room=room)


# --- API Endpoints ---
def _download_cover_from_url(cover_url: str, novel_id: str, book_name: str) -> Optional[str]:
    """下载封面图片到本地
    
    Args:
        cover_url: 封面图片URL
        novel_id: 小说ID
        book_name: 小说名称
        
    Returns:
        本地封面URL或None
    """
    if not cover_url:
        return None
        
    try:
        import requests
        from pathlib import Path
        
        logger = current_app.logger
        cfg = GlobalContext.get_config()
        
        # 获取状态文件夹路径
        status_folder = cfg.status_folder_path(book_name, novel_id)
        status_folder.mkdir(parents=True, exist_ok=True)
        
        # 安全文件名
        safe_book_name = re.sub(r'[\\/*?:"<>|]', "_", book_name)
        cover_path = status_folder / f"{safe_book_name}.jpg"
        
        # 如果已存在，直接返回
        if cover_path.exists():
            return f"/api/novels/{novel_id}/cover"
        
        # 下载封面
        response = requests.get(cover_url, timeout=10, verify=False)
        response.raise_for_status()
        
        # 保存封面
        cover_path.write_bytes(response.content)
        logger.info(f"Downloaded cover for novel {novel_id} from {cover_url}")
        
        return f"/api/novels/{novel_id}/cover"
        
    except Exception as e:
        current_app.logger.warning(f"Failed to download cover for {novel_id}: {e}")
        return None


@app.route("/api/search", methods=["GET"])
def search_novels_api():
    logger = current_app.logger
    query = request.args.get("query")
    if not query:
        return jsonify(error="Missing 'query' parameter"), 400
    
    # 新参数: 是否预下载封面 (默认关闭以提升响应速度)
    preload_covers = request.args.get("preload_covers", "false").lower() == "true"
    
    logger.info(f"Search request: '{query}' (preload_covers={preload_covers})")

    if not DOWNLOADER_AVAILABLE:
        logger.error("Downloader components unavailable for search.")
        return jsonify(error="Search functionality unavailable"), 503

    try:
        if not GlobalContext.is_initialized():
            logger.warning(
                "Downloader context not initialized for search, attempting init..."
            )
            GlobalContext.initialize(get_downloader_config(), logger)

        network_client = NetworkClient()
        search_results = network_client.search_book(query)
        logger.info(f"Search for '{query}' returned {len(search_results)} results.")

        # 获取所有搜索结果的ID
        search_ids = [res.get("book_id") for res in search_results if res.get("book_id")]
        
        # 从数据库查询已存在的小说封面
        existing_novels = {}
        if search_ids:
            novels_in_db = Novel.query.filter(Novel.id.in_(search_ids)).all()
            existing_novels = {
                str(novel.id): novel.cover_image_url 
                for novel in novels_in_db 
                if novel.cover_image_url
            }
            logger.debug(f"Found {len(existing_novels)} novels with local covers")

        # 预下载封面图片
        if preload_covers:
            downloaded_count = 0
            for res in search_results:
                book_id = res.get("book_id")
                if not book_id or str(book_id) in existing_novels:
                    continue  # 已有本地封面，跳过
                
                thumb_url = res.get("thumb_url")
                if thumb_url:
                    title = res.get("title") or f"Novel {book_id}"
                    local_cover = _download_cover_from_url(thumb_url, str(book_id), title)
                    if local_cover:
                        existing_novels[str(book_id)] = local_cover
                        downloaded_count += 1
                        
                        # 更新数据库（如果小说已存在）
                        try:
                            novel = Novel.query.get(int(book_id))
                            if novel:
                                novel.cover_image_url = local_cover
                                _db.session.commit()
                        except Exception as db_err:
                            logger.warning(f"Failed to update cover in DB for {book_id}: {db_err}")
                            _db.session.rollback()
            
            if downloaded_count > 0:
                logger.info(f"Pre-downloaded {downloaded_count} covers for search results")

        formatted_results = [
            {
                "id": str(res.get("book_id"))
                if res.get("book_id") is not None
                else None,
                "title": res.get("title"),
                "author": res.get("author"),
                # 优先使用本地封面，如果不存在则使用番茄API返回的URL
                "cover": existing_novels.get(str(res.get("book_id"))) or res.get("thumb_url"),
                "description": res.get("abstract"),  # 小说简介
                "category": res.get("category"),  # 分类
                "score": res.get("score"),  # 评分
            }
            for res in search_results
            if res.get("book_id") is not None  # Ensure ID exists and is string
        ]
        return jsonify({"results": formatted_results}), 200
    except Exception as e:
        logger.error(f"Error during novel search for '{query}': {e}", exc_info=True)
        return jsonify(error="Internal server error during search"), 500


@app.route("/api/novels", methods=["POST"])
def add_novel_and_crawl():
    logger = current_app.logger
    user_id = 1  # Fixed user ID for internal API
    data = request.get_json()
    if not data or "novel_id" not in data:
        return jsonify(error="Missing 'novel_id' in request body"), 400

    try:
        novel_id_int = int(data["novel_id"])
    except (ValueError, TypeError):
        return jsonify(error="'novel_id' must be a valid integer"), 400

    # 可选参数: max_chapters 用于限制下载章节数量（如预览模式）
    max_chapters = data.get("max_chapters", None)
    if max_chapters is not None:
        try:
            max_chapters = int(max_chapters)
            if max_chapters < 1:
                return jsonify(error="'max_chapters' must be a positive integer"), 400
        except (ValueError, TypeError):
            return jsonify(error="'max_chapters' must be a valid integer"), 400

    logger.info(f"User {user_id} requested add/crawl for novel ID: {novel_id_int}" + 
                (f" (max_chapters: {max_chapters})" if max_chapters else ""))

    db_task_id = None
    try:
        # 检查 Novel 是否存在，如果不存在则创建基础记录
        novel = Novel.query.get(novel_id_int)
        if not novel:
            logger.info(f"Novel {novel_id_int} not found in DB, creating placeholder.")
            # 创建一个包含最少信息的 Novel 记录以满足外键约束
            novel = Novel(id=novel_id_int, title=f"Novel {novel_id_int}")
            _db.session.add(novel)
            # 注意：此时不 commit，让 Novel 和 DownloadTask 在同一个事务中提交

        # 检查是否已有进行中的任务
        existing_task = (
            DownloadTask.query.filter_by(user_id=user_id, novel_id=novel_id_int)
            .filter(
                DownloadTask.status.in_(
                    [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PROCESSING]
                )
            )
            .first()
        )
        if existing_task:
            logger.warning(
                f"User {user_id} task for novel {novel_id_int} already active (ID: {existing_task.id}, Status: {existing_task.status.name})"
            )
            return jsonify(
                error=f"Task is already active with status {existing_task.status.name}.",
                task=existing_task.to_dict(),
            ), 409  # Conflict

        # 创建 DownloadTask 记录
        new_db_task = DownloadTask(
            user_id=user_id,
            novel_id=novel_id_int,
            status=TaskStatus.PENDING,
            progress=0,
        )
        _db.session.add(new_db_task)

        # 在同一个事务中提交 Novel (如果是新建的) 和 DownloadTask
        _db.session.commit()
        db_task_id = new_db_task.id  # 在 commit 后获取 ID
        logger.info(
            f"Created DB task ID: {db_task_id} for novel {novel_id_int}, user {user_id}"
        )

    except Exception as db_err:
        _db.session.rollback()  # 出错时回滚
        logger.error(
            f"Failed to ensure Novel record or create DB task for novel {novel_id_int}: {db_err}",
            exc_info=True,
        )
        return jsonify(error="Failed to prepare task record in database"), 500

    try:
        # 准备任务参数
        task_kwargs = {
            "novel_id": novel_id_int,
            "user_id": user_id,
            "db_task_id": db_task_id,
        }
        if max_chapters is not None:
            task_kwargs["max_chapters"] = max_chapters

        celery_task = celery_app.send_task(
            "tasks.process_novel",
            kwargs=task_kwargs,
        )
        logger.info(f"Queued Celery task {celery_task.id} for DB Task {db_task_id}")

        new_db_task.celery_task_id = celery_task.id
        _db.session.commit()
        logger.info(f"Updated DB Task {db_task_id} with Celery ID {celery_task.id}")

        emit_task_update(user_id, new_db_task.to_dict())
        return jsonify(new_db_task.to_dict()), 202
    except Exception as e:
        logger.error(
            f"Failed to queue Celery task for DB Task {db_task_id}: {e}", exc_info=True
        )
        try:  # Cleanup preliminary DB task
            _db.session.delete(new_db_task)
            _db.session.commit()
        except:
            _db.session.rollback()
        return jsonify(error="Failed to queue background task"), 500


@app.route("/api/novels", methods=["GET"])
def list_novels():
    """
    List novels with filtering, search and sorting.
    
    Query Parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10, max: 50)
    - search: Search by title (partial match, case-insensitive)
    - tags: Filter by tags (comma-separated, e.g., "玄幻,都市")
    - status: Filter by status (e.g., "连载中", "已完结")
    - sort: Sort field (last_crawled_at, created_at, total_chapters, title)
    - order: Sort order (asc, desc) - default: desc
    """
    logger = current_app.logger
    
    # Pagination parameters
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 50)
    
    # Filter parameters
    search_query = request.args.get("search", "").strip()
    tags_filter = request.args.get("tags", "").strip()
    status_filter = request.args.get("status", "").strip()
    
    # Sort parameters
    sort_field = request.args.get("sort", "last_crawled_at").strip()
    sort_order = request.args.get("order", "desc").strip().lower()
    
    logger.info(
        f"Listing novels: page={page}, per_page={per_page}, "
        f"search='{search_query}', tags='{tags_filter}', status='{status_filter}', "
        f"sort={sort_field}, order={sort_order}"
    )
    
    try:
        # Start building query
        query = Novel.query
        
        # Apply title search filter
        if search_query:
            query = query.filter(Novel.title.ilike(f"%{search_query}%"))
        
        # Apply tags filter (match any of the provided tags)
        if tags_filter:
            tags_list = [tag.strip() for tag in tags_filter.split(",") if tag.strip()]
            if tags_list:
                # Match novels that contain ANY of the specified tags
                tag_filters = [Novel.tags.ilike(f"%{tag}%") for tag in tags_list]
                from sqlalchemy import or_
                query = query.filter(or_(*tag_filters))
        
        # Apply status filter
        if status_filter:
            query = query.filter(Novel.status == status_filter)
        
        # Apply sorting
        valid_sort_fields = {
            "last_crawled_at": Novel.last_crawled_at,
            "created_at": Novel.created_at,
            "total_chapters": Novel.total_chapters,
            "title": Novel.title,
        }
        
        if sort_field in valid_sort_fields:
            sort_column = valid_sort_fields[sort_field]
            
            # Handle NULL values for date fields - put them at the end
            if sort_field in ["last_crawled_at", "created_at"]:
                if sort_order == "asc":
                    query = query.order_by(
                        sort_column.is_(None),  # NULLs last
                        sort_column.asc()
                    )
                else:  # desc
                    query = query.order_by(
                        sort_column.is_(None),  # NULLs last
                        sort_column.desc()
                    )
            else:
                # For other fields, simple sorting
                if sort_order == "asc":
                    query = query.order_by(sort_column.asc())
                else:
                    query = query.order_by(sort_column.desc())
        else:
            # Default sorting if invalid sort field provided
            query = query.order_by(
                Novel.last_crawled_at.is_(None),
                Novel.last_crawled_at.desc(),
                Novel.created_at.desc(),
            )
        
        # Execute pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        novels_data = [
            {
                "id": str(n.id),
                "title": n.title,
                "author": n.author,
                "status": n.status,
                "tags": n.tags,
                "total_chapters": n.total_chapters,
                "last_crawled_at": n.last_crawled_at.isoformat()
                if n.last_crawled_at
                else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "cover_image_url": n.cover_image_url,
                "description": n.description,  # Include description in list
            }
            for n in pagination.items
        ]
        
        return jsonify(
            {
                "novels": novels_data,
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
                "filters": {
                    "search": search_query,
                    "tags": tags_filter,
                    "status": status_filter,
                    "sort": sort_field,
                    "order": sort_order,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error listing novels: {e}", exc_info=True)
        return jsonify(error="Database error fetching novels"), 500


@app.route("/api/novels/<int:novel_id>", methods=["GET"])
def get_novel_details(novel_id):
    logger = current_app.logger
    logger.info(f"Fetching details for novel ID: {novel_id}")
    try:
        novel = Novel.query.get_or_404(novel_id)
        chapter_count = Chapter.query.filter_by(novel_id=novel.id).count()
        return jsonify(
            {
                "id": str(novel.id),
                "title": novel.title,
                "author": novel.author,
                "description": novel.description,
                "status": novel.status,
                "tags": novel.tags,
                "total_chapters_source": novel.total_chapters,
                "chapters_in_db": chapter_count,
                "last_crawled_at": novel.last_crawled_at.isoformat()
                if novel.last_crawled_at
                else None,
                "created_at": novel.created_at.isoformat()
                if novel.created_at
                else None,
                "cover_image_url": novel.cover_image_url,
            }
        )
    except HTTPException as e:
        if e.code == 404:
            return jsonify(error=f"Novel with ID {novel_id} not found"), 404
        raise e
    except Exception as e:
        logger.error(f"Error fetching novel details {novel_id}: {e}", exc_info=True)
        return jsonify(error="Database error fetching novel details"), 500


@app.route("/api/novels/<int:novel_id>/chapters", methods=["GET"])
def get_novel_chapters(novel_id):
    logger = current_app.logger
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    logger.info(
        f"Fetching chapters for novel {novel_id}: page={page}, per_page={per_page}"
    )
    try:
        if not _db.session.query(Novel.id).filter_by(id=novel_id).scalar():
            abort(404, description=f"Novel with ID {novel_id} not found.")

        pagination = (
            Chapter.query.filter_by(novel_id=novel_id)
            .order_by(Chapter.chapter_index)
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        chapters_data = [
            {
                "id": str(c.id),
                "index": c.chapter_index,
                "title": c.title,
                "fetched_at": c.fetched_at.isoformat() if c.fetched_at else None,
            }
            for c in pagination.items
        ]
        return jsonify(
            {
                "chapters": chapters_data,
                "total": pagination.total,
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
                "novel_id": str(novel_id),
            }
        )
    except HTTPException as e:
        if e.code == 404:
            return jsonify(error=getattr(e, "description", "Not Found")), 404
        raise e
    except Exception as e:
        logger.error(
            f"Error fetching chapters for novel {novel_id}: {e}", exc_info=True
        )
        return jsonify(error="Database error fetching chapters"), 500


@app.route("/api/novels/<int:novel_id>/chapters/<int:chapter_id>", methods=["GET"])
def get_chapter_content(novel_id, chapter_id):
    logger = current_app.logger
    logger.info(f"Fetching content for novel {novel_id}, chapter {chapter_id}")
    try:
        chapter = Chapter.query.filter_by(
            novel_id=novel_id, id=chapter_id
        ).first_or_404()
        return jsonify(
            {
                "id": str(chapter.id),
                "novel_id": str(chapter.novel_id),
                "index": chapter.chapter_index,
                "title": chapter.title,
                "content": chapter.content,
            }
        )
    except HTTPException as e:
        if e.code == 404:
            return jsonify(
                error=f"Chapter {chapter_id} for novel {novel_id} not found"
            ), 404
        raise e
    except Exception as e:
        logger.error(
            f"Error fetching chapter content {novel_id}/{chapter_id}: {e}",
            exc_info=True,
        )
        return jsonify(error="Database error fetching chapter content"), 500


@app.route("/api/novels/<int:novel_id>/cover", methods=["GET"])
def get_novel_cover(novel_id):
    logger = current_app.logger
    novel = Novel.query.get(novel_id)
    if not novel or not novel.title:
        abort(404, description="Novel not found or missing title")

    if not DOWNLOADER_AVAILABLE:
        abort(503, description="Cover functionality unavailable (downloader missing)")

    try:
        if not GlobalContext.is_initialized():
            GlobalContext.initialize(get_downloader_config(), logger)

        cfg = GlobalContext.get_config()
        status_folder = cfg.status_folder_path(novel.title, str(novel.id))
        safe_book_name = re.sub(r'[\\/*?:"<>|]', "_", novel.title)
        cover_path = status_folder / f"{safe_book_name}.jpg"

        if cover_path.is_file():
            return send_file(str(cover_path), mimetype="image/jpeg")
        else:
            abort(404, description="Cover image not found locally")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error serving cover for novel {novel_id}: {e}", exc_info=True)
        abort(500, description="Error serving cover image")


@app.route("/api/tasks/list", methods=["GET"])
def list_user_tasks():
    logger = current_app.logger
    logger.info("Fetching all tasks (internal API)")
    try:
        tasks = (
            DownloadTask.query
            .options(_db.joinedload(DownloadTask.novel))
            .order_by(DownloadTask.created_at.desc())
            .all()
        )
        return jsonify(tasks=[task.to_dict() for task in tasks])
    except Exception as e:
        logger.error(f"Error fetching all tasks: {e}", exc_info=True)
        return jsonify(error="Database error fetching task list"), 500


@app.route("/api/tasks/<int:db_task_id>/terminate", methods=["POST"])
def terminate_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting termination for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # Get the real user_id for WebSocket notifications

        if not task.celery_task_id and task.status in [
            TaskStatus.PENDING,
            TaskStatus.DOWNLOADING,
            TaskStatus.PROCESSING,
        ]:
            task.status = TaskStatus.FAILED
            task.message = "No Celery task ID found to terminate."
            _db.session.commit()
            emit_task_update(user_id, task.to_dict())
            return jsonify(error="Task has no associated process ID"), 400

        if task.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.TERMINATED,
        ]:
            return jsonify(
                message="Task is already finished.", task=task.to_dict()
            ), 200

        logger.info(
            f"Terminating Celery task {task.celery_task_id} for DB Task {db_task_id}"
        )
        celery_app.control.revoke(task.celery_task_id, terminate=True, signal="SIGTERM")
        task.status = TaskStatus.TERMINATED
        task.progress = 0
        task.message = "Task terminated by user."
        _db.session.commit()
        logger.info(f"DB Task {db_task_id} status updated to TERMINATED.")
        emit_task_update(user_id, task.to_dict())
        return jsonify(message="Task termination signal sent.", task=task.to_dict())
    except Exception as e:
        _db.session.rollback()
        logger.error(f"Error terminating task {db_task_id}: {e}", exc_info=True)
        return jsonify(error="Failed to terminate task"), 500


@app.route("/api/tasks/<int:db_task_id>", methods=["DELETE"])
def delete_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting deletion for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # Get the real user_id for WebSocket notifications

        celery_id_to_forget = task.celery_task_id
        _db.session.delete(task)
        _db.session.commit()
        logger.info(f"Deleted DB Task {db_task_id} for user {user_id}.")

        if celery_id_to_forget:
            try:
                AsyncResult(celery_id_to_forget, app=celery_app).forget()
            except Exception as forget_err:
                logger.warning(
                    f"Could not forget Celery result {celery_id_to_forget}: {forget_err}"
                )

        emit_task_update(user_id, {"id": db_task_id, "deleted": True})
        return jsonify(message="Task deleted successfully.")
    except Exception as e:
        _db.session.rollback()
        logger.error(f"Error deleting task {db_task_id}: {e}", exc_info=True)
        return jsonify(error="Failed to delete task"), 500


@app.route("/api/tasks/<int:db_task_id>/redownload", methods=["POST"])
def redownload_task(db_task_id):
    logger = current_app.logger
    logger.info(f"Internal API requesting re-download for DB Task ID: {db_task_id}")
    try:
        task = DownloadTask.query.filter_by(id=db_task_id).first()
        if not task:
            return jsonify(error="Task not found"), 404
        
        user_id = task.user_id  # Get the real user_id for notifications

        if task.status in [
            TaskStatus.DOWNLOADING,
            TaskStatus.PROCESSING,
            TaskStatus.PENDING,
        ]:
            return jsonify(
                error=f"Cannot re-download active task ({task.status.name})."
            ), 409

        novel_id_to_redownload = task.novel_id
        logger.info(
            f"Re-downloading Novel {novel_id_to_redownload} for User {user_id} (Task {db_task_id})"
        )

        task.status = TaskStatus.PENDING
        task.progress = 0
        task.message = "Re-download requested."
        task.celery_task_id = None
        _db.session.commit()
        logger.info(f"Reset DB Task {db_task_id} to PENDING.")
        emit_task_update(user_id, task.to_dict())

        try:
            celery_task = celery_app.send_task(
                "tasks.process_novel",
                kwargs={
                    "novel_id": novel_id_to_redownload,
                    "user_id": user_id,
                    "db_task_id": db_task_id,
                },
            )
            logger.info(
                f"Queued new Celery task {celery_task.id} for re-download (DB Task {db_task_id})"
            )
            task.celery_task_id = celery_task.id
            _db.session.commit()
            logger.info(
                f"Updated DB Task {db_task_id} with new Celery ID {celery_task.id}"
            )
            return jsonify(message="Re-download task queued.", task=task.to_dict()), 202
        except Exception as queue_err:
            logger.error(
                f"Failed queue Celery re-download (DB Task {db_task_id}): {queue_err}",
                exc_info=True,
            )
            task.status = TaskStatus.FAILED
            task.message = f"Failed to queue re-download: {queue_err}"
            _db.session.commit()
            emit_task_update(user_id, task.to_dict())
            return jsonify(error="Failed to queue background task"), 500
    except Exception as e:
        _db.session.rollback()
        logger.error(
            f"Error during re-download for task {db_task_id}: {e}", exc_info=True
        )
        return jsonify(error="Failed to initiate re-download"), 500


@app.route("/api/tasks/status/<string:task_id>", methods=["GET"])
def get_task_status(task_id):
    if not task_id or len(task_id) > 64 or not task_id.replace("-", "").isalnum():
        return jsonify(error="Invalid Celery task ID format"), 400
    task_result = AsyncResult(task_id, app=celery_app)
    status = task_result.status
    result = task_result.result
    response = {"task_id": task_id, "status": status, "result": None, "meta": None}
    status_map = {
        "PENDING": "Task is waiting.",
        "STARTED": "Task started.",
        "PROGRESS": "Task in progress.",
        "SUCCESS": "Task completed.",
        "FAILURE": "Task failed.",
        "REVOKED": "Task terminated.",
    }
    response["result"] = status_map.get(status, f"Unknown state: {status}")
    if isinstance(result, dict):
        response["meta"] = result
    elif isinstance(result, Exception):
        response["meta"] = {
            "exc_type": type(result).__name__,
            "exc_message": str(result),
        }
    else:
        response["meta"] = task_result.info
    if (
        status == "FAILURE"
        and response["meta"] is None
        and hasattr(task_result, "traceback")
    ):
        response["traceback"] = task_result.traceback
    return jsonify(response)


# --- Stats Endpoints ---
@app.get("/api/stats/upload")
def upload_stats():
    sql = """
    SELECT DATE(created_at) as d, COUNT(*) as c FROM novel
    WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 29 DAY)
    GROUP BY d ORDER BY d;
    """
    try:
        rows = _db.session.execute(sql_text(sql)).fetchall()
        return jsonify([{"date": str(r[0]), "count": r[1]} for r in rows])
    except Exception as e:
        current_app.logger.error(f"Error fetching upload stats: {e}", exc_info=True)
        _db.session.rollback()
        return jsonify(error="Database error fetching upload stats"), 500


@app.get("/api/stats/genre")
def genre_stats():
    sql = "SELECT tags, COUNT(*) as c FROM novel GROUP BY tags;"
    try:
        rows = _db.session.execute(sql_text(sql)).fetchall()
        tag_counts = {}
        for tags_str, count in rows:
            primary_tag = (tags_str.split("|")[0].strip() if tags_str else "") or "未知"
            tag_counts[primary_tag] = tag_counts.get(primary_tag, 0) + count
        return jsonify(
            [{"name": tag, "value": value} for tag, value in tag_counts.items()]
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching genre stats: {e}", exc_info=True)
        _db.session.rollback()
        return jsonify(error="Database error fetching genre stats"), 500


@app.get("/api/stats/wordcloud/<int:novel_id>")
def wordcloud_img(novel_id):
    wordcloud_dir = current_app.config.get("WORDCLOUD_SAVE_PATH")
    if not wordcloud_dir:
        return jsonify(error="Server configuration error"), 500
    safe_filename = f"wordcloud_{novel_id}.png"
    path = os.path.abspath(os.path.join(wordcloud_dir, safe_filename))
    if not path.startswith(os.path.abspath(wordcloud_dir)):
        return jsonify(error="Invalid file path"), 400
    if os.path.isfile(path):
        try:
            return send_file(path, mimetype="image/png")
        except Exception as send_err:
            current_app.logger.error(
                f"Error sending file {path}: {send_err}", exc_info=True
            )
            return jsonify(error="Error sending file"), 500
    else:
        novel_exists = Novel.query.get(novel_id) is not None
        error_msg = (
            "Wordcloud not found. Analysis incomplete or failed."
            if novel_exists
            else f"Novel with ID {novel_id} not found."
        )
        return jsonify(error=error_msg), 404


@app.route("/api/novels/<int:novel_id>/download", methods=["GET"])
def download_novel_file(novel_id):
    logger = current_app.logger
    try:
        novel = Novel.query.get(novel_id)
        if not novel or not novel.title:
            abort(404, description="Novel not found or missing title")

        save_path_base = current_app.config.get("NOVEL_SAVE_PATH")
        novel_format = current_app.config.get("NOVEL_NOVEL_FORMAT", "epub")
        if not save_path_base:
            abort(500, description="Server configuration error: Save path not set.")

        safe_book_name = re.sub(r'[\\/*?:"<>|]', "_", novel.title)
        filename = f"{safe_book_name}.{novel_format}"
        full_path = os.path.abspath(os.path.join(save_path_base, filename))
        if not full_path.startswith(os.path.abspath(save_path_base)):
            abort(400, description="Invalid file path.")

        if os.path.isfile(full_path):
            mime_type = (
                "application/epub+zip" if novel_format == "epub" else "text/plain"
            )
            logger.info(f"Sending file: {filename} (MIME: {mime_type})")
            return send_file(
                full_path,
                mimetype=mime_type,
                as_attachment=True,
                download_name=filename,
            )
        else:
            task = (
                DownloadTask.query.filter_by(novel_id=novel_id)
                .order_by(DownloadTask.created_at.desc())
                .first()
            )
            status_msg = (
                f"Task status: {task.status.name}."
                if task
                else "No download task found."
            )
            description = f"Generated novel file ({filename}) not found. {status_msg}"
            abort(404, description=description)
    except HTTPException as e:
        logger.warning(
            f"HTTP Exception during download for novel {novel_id}: {e.code} - {e.description}"
        )
        return jsonify(error=e.description), e.code
    except Exception as e:
        logger.error(f"Error during novel download {novel_id}: {e}", exc_info=True)
        abort(500, description="Error serving novel file.")


# --- Error Handlers ---
@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(
        f"Not Found (404): {request.path} - {getattr(error, 'description', 'No description')}"
    )
    return jsonify(error=getattr(error, "description", "Resource not found")), 404


@app.errorhandler(500)
def internal_error(error):
    original_exception = getattr(error, "original_exception", error)
    app.logger.error(
        f"Internal Server Error (500): {request.path} - {original_exception}",
        exc_info=original_exception,
    )
    try:
        _db.session.rollback()
    except Exception as rb_err:
        app.logger.error(f"Error rolling back session during 500 handler: {rb_err}")
    return jsonify(error="内部服务器错误"), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    if isinstance(e, HTTPException):
        return jsonify(error=getattr(e, "description", "An error occurred")), e.code
    app.logger.error(f"Unhandled exception caught: {request.path} - {e}", exc_info=True)
    try:
        _db.session.rollback()
    except Exception as rb_err:
        app.logger.error(f"Error rolling back session: {rb_err}")
    return jsonify(error="发生意外错误"), 500


# --- Main ---
if __name__ == "__main__":
    app.logger.info("Starting Flask application directly (dev mode)")
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.logger.info(f"Running on http://{host}:{port}/ with debug={debug_mode}")
    socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=debug_mode)
