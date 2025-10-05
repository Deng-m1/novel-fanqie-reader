# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file
import pymysql

pymysql.install_as_MySQLdb()


class Settings:
    # --- Database Settings ---
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = (
        os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true"
    )  # For debugging DB queries

    # --- JWT Settings ---
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "a-very-secret-key-please-change"
    )  # Use a strong, unique secret
    JWT_ACCESS_TOKEN_EXPIRES = (
        int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 60)) * 60
    )  # In seconds

    # --- Celery Settings ---
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TIMEZONE = (
        "Asia/Shanghai"  # Or your preferred timezone e.g., 'Asia/Shanghai'
    )
    CELERY_ENABLE_UTC = True
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True  # Good practice

    # --- File Storage Paths ---
    # Base path for generated data
    DATA_BASE_PATH = os.getenv(
        "DATA_BASE_PATH", os.path.join(os.path.dirname(__file__), "data")
    )

    # Word Cloud Image Save Path
    WORDCLOUD_SAVE_SUBDIR = "wordclouds"
    WORDCLOUD_SAVE_PATH = os.path.join(DATA_BASE_PATH, WORDCLOUD_SAVE_SUBDIR)

    # --- novel_downloader Configuration Mapping ---
    # These keys should match the fields expected by novel_downloader's Config class
    # We'll construct a dict from these to pass to GlobalContext.initialize

    # Paths (required)
    NOVEL_SAVE_PATH = os.getenv(
        "NOVEL_SAVE_PATH", os.path.join(DATA_BASE_PATH, "novel_downloads")
    )
    NOVEL_STATUS_PATH = os.getenv(
        "NOVEL_STATUS_PATH", os.path.join(DATA_BASE_PATH, "novel_status")
    )

    # Core Settings
    NOVEL_MAX_WORKERS = int(
        os.getenv("NOVEL_MAX_WORKERS", 5)
    )  # Increased default slightly
    NOVEL_REQUEST_TIMEOUT = int(
        os.getenv("NOVEL_REQUEST_TIMEOUT", 20)
    )  # Increased default slightly
    NOVEL_MAX_RETRIES = int(os.getenv("NOVEL_MAX_RETRIES", 3))
    NOVEL_MIN_WAIT_TIME = int(
        os.getenv("NOVEL_MIN_WAIT_TIME", 800)
    )  # Adjusted defaults
    NOVEL_MAX_WAIT_TIME = int(
        os.getenv("NOVEL_MAX_WAIT_TIME", 1500)
    )  # Adjusted defaults
    NOVEL_MIN_CONNECT_TIMEOUT = float(os.getenv("NOVEL_MIN_CONNECT_TIMEOUT", 3.1))
    NOVEL_NOVEL_FORMAT = os.getenv("NOVEL_FORMAT", "epub").lower()
    NOVEL_BULK_FILES = os.getenv("NOVEL_BULK_FILES", "False").lower() == "true"
    NOVEL_AUTO_CLEAR_DUMP = os.getenv("NOVEL_AUTO_CLEAR", "True").lower() == "true"
    # Proxy API Mode (推荐使用)
    NOVEL_USE_PROXY_API = (
        os.getenv("NOVEL_USE_PROXY_API", "True").lower() == "true"
    )
    
    # Official API (已失效)
    NOVEL_USE_OFFICIAL_API = (
        os.getenv("NOVEL_USE_OFFICIAL_API", "False").lower() == "true"
    )
    NOVEL_IID = os.getenv("NOVEL_IID", "")  # Allow setting via env if needed
    NOVEL_IID_SPAWN_TIME = os.getenv("NOVEL_IID_SPAWN_TIME", "")

    # API Endpoints (allow comma-separated list from env)
    NOVEL_API_ENDPOINTS_STR = os.getenv("NOVEL_API_ENDPOINTS", "")
    NOVEL_API_ENDPOINTS = [
        url.strip() for url in NOVEL_API_ENDPOINTS_STR.split(",") if url.strip()
    ]
    # --- End novel_downloader Configuration Mapping ---

    # --- General App Settings ---
    DEBUG = os.getenv("FLASK_ENV", "production") == "development"
    SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY", "another-secret-key-please-change"
    )  # For Flask session etc.

    # --- Ensure directories exist ---
    @staticmethod
    def _ensure_dir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create directory {path}: {e}")

    _ensure_dir(DATA_BASE_PATH)
    _ensure_dir(WORDCLOUD_SAVE_PATH)
    _ensure_dir(NOVEL_SAVE_PATH)
    _ensure_dir(NOVEL_STATUS_PATH)


settings = Settings()


# Helper function to get downloader config as dict
def get_downloader_config():
    return {
        "save_path": settings.NOVEL_SAVE_PATH,
        "status_folder_path_base": settings.NOVEL_STATUS_PATH,
        "max_workers": settings.NOVEL_MAX_WORKERS,
        "request_timeout": settings.NOVEL_REQUEST_TIMEOUT,
        "max_retries": settings.NOVEL_MAX_RETRIES,
        "max_wait_time": settings.NOVEL_MAX_WAIT_TIME,
        "min_wait_time": settings.NOVEL_MIN_WAIT_TIME,
        "min_connect_timeout": settings.NOVEL_MIN_CONNECT_TIMEOUT,
        "novel_format": settings.NOVEL_NOVEL_FORMAT,
        "bulk_files": settings.NOVEL_BULK_FILES,
        "auto_clear_dump": settings.NOVEL_AUTO_CLEAR_DUMP,
        "use_proxy_api": settings.NOVEL_USE_PROXY_API,  # 代理模式
        "use_official_api": settings.NOVEL_USE_OFFICIAL_API,
        "api_endpoints": settings.NOVEL_API_ENDPOINTS,
        "iid": settings.NOVEL_IID,  # Pass these through
        "iid_spawn_time": settings.NOVEL_IID_SPAWN_TIME,
        # Add other fields from novel_downloader's Config if needed
    }
