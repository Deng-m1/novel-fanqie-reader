# backend/novel_downloader/novel_src/base_system/context.py
import os
import re
from logging import Logger  # <-- Import Logger type
from pathlib import Path
from typing import Dict, Any, Optional

# Keep BaseConfig, Field, ConfigError, LogSystem imports as they are
from .storge_system import BaseConfig, Field, ConfigError
from .log_system import LogSystem

_log_system_instance: Optional[LogSystem] = None  # <-- Rename for clarity
_logger: Optional[Logger] = None  # <-- Store the actual logger separately
_config: Optional["Config"] = None  # Forward declaration
_is_initialized = False


# --- Keep Config class definition with Fields mostly the same ---
class Config(BaseConfig):
    """Config 配置文件"""

    # Network config... (keep existing fields)
    max_workers: int = Field(default=3, description="最大并发线程数")
    request_timeout: int = Field(default=15, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    max_wait_time: int = Field(default=1200, description="最大冷却时间, 单位ms")
    min_wait_time: int = Field(default=1000, description="最小冷却时间, 单位ms")
    min_connect_timeout: float = Field(default=3.05, description="最小连接超时时间")
    force_exit_timeout: int = Field(default=5, description="强制退出等待时间")
    graceful_exit: bool = Field(
        default=True, description="是否启用优雅退出"
    )  # Less relevant in library mode

    # Save config... (keep existing fields)
    novel_format: str = Field(
        default="epub", description="保存小说格式, 可选: [txt, epub]"
    )
    bulk_files: bool = Field(default=False, description="是否以散装形式保存小说")
    auto_clear_dump: bool = Field(default=True, description="是否自动清理缓存文件")

    # Path config - THESE WILL BE OVERRIDDEN BY FLASK CONFIG
    save_path: str = Field(default="", description="保存路径 (由Flask提供)")
    status_folder_path_base: str = Field(
        default="", description="状态文件根路径 (由Flask提供)"
    )

    # API config... (keep existing fields)
    use_official_api: bool = Field(default=True, description="使用官方API")
    use_proxy_api: bool = Field(default=False, description="使用代理API（推荐）")
    iid: str = Field(default="", description="自动生成")
    iid_spawn_time: str = Field(default="", description="iid生成时间戳")
    api_endpoints: list = Field(
        default=[],
        description="API列表",
    )

    # --- Keep properties, maybe adapt path logic slightly ---
    @property
    def default_save_dir(self) -> Path:
        """获取默认保存目录路径对象 (Uses save_path from config)"""
        # Use Path directly, ensure it exists if needed by caller
        return (
            Path(self.save_path) if self.save_path else Path(os.getcwd())
        )  # Fallback might not be ideal

    @property
    def get_status_folder_path(self) -> Optional[Path]:
        """获取为特定书籍生成的 Folder_path (if status_folder_path was called)"""
        return getattr(self, "_current_status_folder", None)

    def status_folder_path(
        self, book_name: str, book_id: str, save_dir: str = None
    ) -> Path:
        """生成并设置书籍专属状态文件路径. Uses status_folder_path_base."""
        base_status_dir = (
            Path(self.status_folder_path_base)
            if self.status_folder_path_base
            else self.default_save_dir
        )
        # Clean book name for folder name (important!)
        safe_book_name = re.sub(r'[\\/*?:"<>|]', "_", book_name)  # More robust cleaning
        safe_book_id = re.sub(r"[^a-zA-Z0-9_]", "_", book_id)
        # Store the generated path for retrieval via get_status_folder_path
        self._current_status_folder = (
            base_status_dir / f"{safe_book_id}_{safe_book_name}"
        )
        self._current_status_folder.mkdir(parents=True, exist_ok=True)
        return self._current_status_folder

    # --- Add method to load config from dict ---
    @classmethod
    def load_from_dict(
        cls, config_data: Dict[str, Any], config_path: str = None
    ) -> "Config":
        """Loads configuration from a dictionary."""
        target_path = config_path or cls.__config_path__
        # Validate the passed dictionary against fields
        validated_data = cls._validate_config(config_data)
        # Create instance, passing the original config_path if specified
        instance = cls(config_path=target_path, **validated_data)
        return instance


class GlobalContext:
    @staticmethod
    def initialize(
        config_data: Dict[str, Any],
        logger: Optional[Logger] = None,
        debug: bool = False,
    ):
        """Initializes the context programmatically."""
        global _log_system_instance, _logger, _config, _is_initialized
        if _is_initialized:
            # **MODIFICATION START**: Check if _logger exists instead of _log_system.logger
            if _logger:
                _logger.warning("GlobalContext already initialized.")
            # **MODIFICATION END**
            return

        # Use provided logger or initialize LogSystem
        if logger:
            _logger = logger  # Assign Flask logger directly to _logger
            _log_system_instance = None  # Explicitly set LogSystem instance to None
        else:
            # Initialize own LogSystem if no logger is passed
            ls = LogSystem(debug=debug)
            _log_system_instance = ls  # Store the LogSystem instance
            _logger = ls.logger  # Get the logger instance from LogSystem

        try:
            # Use load_from_dict instead of load() which reads file
            _config = Config.load_from_dict(config_data)
            _is_initialized = True
            if _logger:  # Check if logger was successfully initialized
                _logger.info(
                    "novel_downloader GlobalContext initialized programmatically."
                )
        except ConfigError as e:
            if _logger:
                _logger.error(f"novel_downloader configuration error: {str(e)}")
            raise  # Re-raise to signal failure
        except Exception as e:
            if _logger:
                _logger.error(
                    f"novel_downloader context initialization failed: {str(e)}",
                    exc_info=True,
                )
            raise  # Re-raise to signal failure

    @staticmethod
    def get_logger() -> Logger:
        """获取logger"""
        if not _is_initialized or not _logger:  # <-- Check _logger
            raise RuntimeError(
                "GlobalContext not initialized or logger not available. Call GlobalContext.initialize first."
            )
        return _logger  # <-- Return the stored logger

    @staticmethod
    def get_log_system() -> Optional[LogSystem]:
        """获取log_system (Returns None if Flask logger was injected)"""
        if not _is_initialized:
            raise RuntimeError("GlobalContext not initialized.")
        # Return the stored LogSystem instance (which is None if external logger was used)
        return _log_system_instance  # <-- Return the stored instance

    @staticmethod
    def get_config() -> Config:
        """获取Config"""
        if not _is_initialized or not _config:
            raise RuntimeError(
                "GlobalContext not initialized. Call GlobalContext.initialize first."
            )
        return _config

    @staticmethod
    def is_initialized() -> bool:
        """Check if the context has been initialized."""
        return _is_initialized
