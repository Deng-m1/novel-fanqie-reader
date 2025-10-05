# backend/tasks.py
import logging
import re
import traceback
from datetime import datetime
from typing import Dict, Any
from flask import current_app

from celery import Task
from celery_init import celery_app
from celery.exceptions import Ignore  # Import Ignore exception

from database import db
from models import Novel, Chapter, WordStat, DownloadTask, TaskStatus

try:
    from novel_downloader.novel_src.base_system.context import GlobalContext
    from novel_downloader.novel_src.network_parser.network import NetworkClient
    from novel_downloader.novel_src.network_parser.downloader import ChapterDownloader
    from novel_downloader.novel_src.book_parser.book_manager import BookManager

    DOWNLOADER_AVAILABLE = True
except ImportError as e:
    logging.getLogger("celery.tasks.init").error(f"Failed novel_downloader import: {e}")
    DOWNLOADER_AVAILABLE = False

from analysis import update_word_stats
from config import get_downloader_config

try:
    # Import emit_task_update safely, provide fallback if running outside Flask app context
    from app import emit_task_update
except ImportError:

    def emit_task_update(user_id: int, task_data: dict):
        logger = logging.getLogger(f"celery.task.emit_fallback")
        logger.warning(
            f"emit_task_update fallback (Flask app context likely unavailable). User: {user_id}, Task: {task_data.get('id')}, Status: {task_data.get('status')}"
        )
        pass


# --- Helper Function to Update DB Task ---
def _update_db_task_status(
    db_task_id: int,
    user_id: int,
    status: TaskStatus,
    progress: int = None,
    message: str = None,
    celery_task_id: str = None,
):
    """Updates the DownloadTask status in the database and emits a SocketIO update."""
    # Use Flask logger if available, otherwise use standard logger
    logger = current_app.logger if current_app else logging.getLogger("celery.tasks")
    try:
        # Ensure we are in an app context if not already (important for standalone workers)
        _app = current_app._get_current_object() if current_app else None
        if _app:
            with _app.app_context():
                task = DownloadTask.query.get(db_task_id)
                if task:
                    task.status = status
                    if progress is not None:
                        task.progress = max(0, min(100, progress))
                    if message is not None:
                        task.message = (
                            (message[:250] + "...") if len(message) > 253 else message
                        )
                    if celery_task_id:
                        task.celery_task_id = celery_task_id
                    task.updated_at = datetime.utcnow()

                    db.session.commit()
                    emit_task_update(
                        user_id, task.to_dict()
                    )  # Emit only after successful commit
                    return True
                else:
                    logger.error(
                        f"DB Task ID {db_task_id} not found for update (User: {user_id}, Status: {status.name})."
                    )
                    return False
        else:
            logger.error(
                f"Flask app context not available for DB Task {db_task_id} update."
            )
            return False
    except Exception as e:
        # Rollback might fail if session is already broken, log anyway
        try:
            db.session.rollback()
        except Exception as rb_err:
            logger.error(f"Error during rollback for DB task {db_task_id}: {rb_err}")
        logger.error(
            f"Failed to update DB task {db_task_id} for user {user_id} to status {status.name}: {e}",
            exc_info=True,
        )
        return False


# --- Download and Process Task ---
@celery_app.task(bind=True, name="tasks.process_novel")
def process_novel_task(
    self, novel_id: int, user_id: int, db_task_id: int, max_chapters: int = None
) -> Dict[str, Any]:
    """
    Celery task to download, process, and save a novel's chapters and metadata.
    Updates the corresponding DownloadTask record in the database.
    
    Args:
        novel_id: ID of the novel to process
        user_id: ID of the user requesting the download
        db_task_id: ID of the DownloadTask record
        max_chapters: Optional limit on number of chapters to download (e.g., 10 for preview)
    """
    # Use Flask logger if available, otherwise use standard logger
    logger = current_app.logger if current_app else logging.getLogger("celery.tasks")
    celery_task_id = self.request.id
    logger.info(
        f"Celery Task {celery_task_id}: Starting processing for Novel ID: {novel_id}, User ID: {user_id}, DB Task ID: {db_task_id}" + 
        (f" (max_chapters: {max_chapters})" if max_chapters else "")
    )

    # Initial status update
    if not _update_db_task_status(
        db_task_id,
        user_id,
        TaskStatus.DOWNLOADING,
        progress=0,
        message="Initializing download...",
        celery_task_id=celery_task_id,  # Ensure Celery ID is set early
    ):
        logger.error(
            f"Task {celery_task_id}: Failed initial DB status update for DB Task {db_task_id}. Aborting."
        )
        # Cannot easily update DB, return failure state for Celery
        return {"status": "FAILURE", "message": "Failed initial DB update"}

    # Check for revocation early
    # --- REVOCATION CHECK START ---
    if self.request.delivery_info.get("is_revoked"):
        logger.warning(f"Task {celery_task_id} termination requested before start.")
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.TERMINATED,
            message="Task terminated before start.",
        )
        self.update_state(
            task_id=self.request.id,
            state="REVOKED",
            meta={"reason": "Terminated before start"},
        )
        return {"status": "REVOKED", "message": "Task terminated before start"}
    # --- REVOCATION CHECK END ---

    if not DOWNLOADER_AVAILABLE:
        logger.error(
            f"Task {celery_task_id}: novel_downloader components not available. Aborting."
        )
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.FAILED,
            message="Downloader components missing.",
        )
        return {"status": "FAILURE", "message": "Downloader components missing"}

    # Initialize downloader context
    try:
        downloader_config = get_downloader_config()
        # Pass logger explicitly if outside Flask context, otherwise it picks up current_app.logger
        context_logger = logger if not current_app else current_app.logger
        GlobalContext.initialize(config_data=downloader_config, logger=context_logger)
    except Exception as init_e:
        logger.critical(
            f"Task {celery_task_id}: Failed novel_downloader context init: {init_e}",
            exc_info=True,
        )
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.FAILED,
            message=f"Downloader context init failed: {init_e}",
        )
        return {
            "status": "FAILURE",
            "message": f"Downloader context init failed: {init_e}",
        }

    network_client = NetworkClient()
    book_manager = None

    try:
        # --- 1. Fetch Book Info ---
        logger.info(f"Task {celery_task_id}: Fetching book info...")
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.DOWNLOADING,
            progress=5,
            message="Fetching book info...",
        )
        book_info_tuple = network_client.get_book_info(str(novel_id))
        if book_info_tuple is None:
            raise ValueError(f"Failed to fetch book info for ID {novel_id}.")
        book_name, author, description, tags, chapter_count_src = book_info_tuple

        # --- REVOCATION CHECK START ---
        if self.request.delivery_info.get("is_revoked"):
            logger.warning(f"Task {celery_task_id} terminated during info fetch.")
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.TERMINATED,
                message="Task terminated during info fetch.",
            )
            self.update_state(
                task_id=self.request.id,
                state="REVOKED",
                meta={"reason": "Terminated during info fetch"},
            )
            return {
                "status": "REVOKED",
                "message": "Task terminated during info fetch.",
            }
        # --- REVOCATION CHECK END ---

        # Determine cover URL
        cover_url = None
        try:
            cfg = GlobalContext.get_config()
            status_folder = cfg.status_folder_path(book_name, str(novel_id))
            safe_book_name = re.sub(r'[\\/*?:"<>|]', "_", book_name)
            cover_path = status_folder / f"{safe_book_name}.jpg"
            cover_url_api = (
                f"/api/novels/{novel_id}/cover"  # Relative URL for API access
            )
            if cover_path.exists():
                cover_url = cover_url_api
        except Exception as cover_path_err:
            logger.warning(
                f"Task {celery_task_id}: Could not determine cover path: {cover_path_err}"
            )

        logger.info(
            f"Task {celery_task_id}: Book Info: Name='{book_name}', Author='{author}', Chapters='{chapter_count_src}'"
        )

        # --- 2. Update Novel in DB ---
        # Use Flask app context for DB operations if available
        _app_context = current_app.app_context() if current_app else None
        if _app_context:
            _app_context.push()
        try:
            novel = Novel.query.get(novel_id)
            if not novel:
                # This case implies the placeholder wasn't created or was deleted.
                # Recreate it, though ideally it should exist from the API call.
                logger.warning(
                    f"Task {celery_task_id}: Novel {novel_id} placeholder missing, recreating."
                )
                novel = Novel(id=novel_id)
                db.session.add(novel)

            novel.title = book_name or f"小说 {novel_id}"
            novel.author = author
            novel.description = description
            novel.tags = "|".join(tags) if isinstance(tags, list) else tags
            novel.status = tags[0] if isinstance(tags, list) and tags else "未知"
            novel.total_chapters = chapter_count_src
            novel.cover_image_url = cover_url
            novel.last_crawled_at = datetime.utcnow()
            db.session.commit()
            logger.info(
                f"Task {celery_task_id}: Updated Novel {novel_id} details in DB."
            )
        except Exception as db_novel_err:
            logger.error(
                f"Task {celery_task_id}: Failed to update Novel {novel_id} in DB: {db_novel_err}",
                exc_info=True,
            )
            db.session.rollback()
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.FAILED,
                message=f"DB Novel update failed: {db_novel_err}",
            )
            return {"status": "FAILURE", "message": "DB Novel update failed"}
        finally:
            if _app_context:
                _app_context.pop()

        # --- 3. Fetch Chapter List ---
        logger.info(f"Task {celery_task_id}: Fetching chapter list...")
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.DOWNLOADING,
            progress=10,
            message="Fetching chapter list...",
        )
        chapters_list = network_client.fetch_chapter_list(str(novel_id))
        if chapters_list is None:
            raise ValueError(f"Failed to fetch chapter list for ID {novel_id}.")
        total_chapters_src = len(chapters_list)
        
        # 如果指定了 max_chapters，限制下载章节数量（用于预览模式）
        if max_chapters is not None and max_chapters > 0:
            original_count = total_chapters_src
            chapters_list = chapters_list[:max_chapters]
            total_chapters_src = len(chapters_list)
            logger.info(f"Task {celery_task_id}: Limited to {total_chapters_src} chapters (from {original_count}) for preview mode.")
        else:
            logger.info(f"Task {celery_task_id}: Found {total_chapters_src} chapters.")

        # --- REVOCATION CHECK START ---
        if self.request.delivery_info.get("is_revoked"):
            logger.warning(
                f"Task {celery_task_id} terminated during chapter list fetch."
            )
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.TERMINATED,
                message="Task terminated during chapter list fetch.",
            )
            self.update_state(
                task_id=self.request.id,
                state="REVOKED",
                meta={"reason": "Terminated during chapter list fetch"},
            )
            return {
                "status": "REVOKED",
                "message": "Task terminated during chapter list fetch.",
            }
        # --- REVOCATION CHECK END ---

        if not chapters_list:
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.COMPLETED,
                progress=100,
                message="No chapters found in source.",
            )
            return {
                "status": "SUCCESS",
                "message": "No chapters found",
                "chapters_processed": 0,
            }

        # --- 4. Download Chapters ---
        # Define progress callback
        chapters_to_download_count = total_chapters_src

        def report_download_progress(completed: int, total: int):
            if total > 0:
                # Calculate download progress (scaling from 15% to 85%)
                download_progress_percentage = 15 + int((completed / total) * (85 - 15))
                progress = max(15, min(85, download_progress_percentage))
                message = f"Downloading {completed}/{total} chapters..."
                _update_db_task_status(
                    db_task_id,
                    user_id,
                    TaskStatus.DOWNLOADING,
                    progress=progress,
                    message=message,
                )
            # Optional debug log for callback activation
            # logger.debug(f"Progress callback: {completed}/{total} chapters done.")

        # Prepare downloader and manager
        book_manager = BookManager(
            book_id=str(novel_id),
            book_name=book_name,
            author=author,
            tags=tags,
            description=description,
        )
        downloader = ChapterDownloader(str(novel_id), network_client)

        logger.info(f"Task {celery_task_id}: Starting chapter download...")
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.DOWNLOADING,
            progress=15,
            message=f"Downloading 0/{chapters_to_download_count} chapters...",
        )

        # Execute download with progress callback
        download_results = downloader.download_book(
            book_manager=book_manager,
            book_name=book_name,
            chapters=chapters_list,
            progress_callback=report_download_progress,
        )

        logger.info(f"Task {celery_task_id}: Download results: {download_results}")

        # --- REVOCATION CHECK START ---
        if self.request.delivery_info.get("is_revoked"):
            logger.warning(f"Task {celery_task_id} terminated after download.")
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.TERMINATED,
                message="Task terminated after download.",
            )
            self.update_state(
                task_id=self.request.id,
                state="REVOKED",
                meta={"reason": "Terminated after download"},
            )
            return {
                "status": "REVOKED",
                "message": "Task terminated after download.",
            }
        # --- REVOCATION CHECK END ---

        # --- 5. Process and Save Chapters to DB ---
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.PROCESSING,
            progress=85,
            message="Processing downloaded chapters...",
        )

        downloaded_data = book_manager.get_downloaded_data()
        downloaded_count_mgr = len(downloaded_data)
        logger.info(
            f"Task {celery_task_id}: Retrieved {downloaded_count_mgr} chapters from BookManager."
        )
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.PROCESSING,
            progress=90,
            message="Saving chapters to database...",
        )

        saved_count = 0
        chapters_with_errors = []
        # Use Flask app context for DB operations
        if _app_context:
            _app_context.push()
        try:
            # --- DB SAVE LOOP START ---
            with db.session.begin_nested():  # Use nested transaction
                # Delete old chapters first
                deleted_count = Chapter.query.filter_by(novel_id=novel_id).delete()
                if deleted_count > 0:
                    logger.info(
                        f"Task {celery_task_id}: Deleted {deleted_count} old chapters."
                    )

                # Iterate and save/merge new chapters
                for index, chapter_meta in enumerate(chapters_list):
                    # --- REVOCATION CHECK START (inside loop) ---
                    if index % 50 == 0 and self.request.delivery_info.get("is_revoked"):
                        logger.warning(
                            f"Task {celery_task_id} terminated during DB save loop."
                        )
                        self.update_state(
                            task_id=self.request.id,
                            state="REVOKED",
                            meta={"reason": "Terminated during DB save"},
                        )
                        raise Ignore("Terminated during DB save.")
                    # --- REVOCATION CHECK END (inside loop) ---

                    chapter_id_str = chapter_meta["id"]
                    chapter_data = downloaded_data.get(chapter_id_str)

                    if (
                        chapter_data
                        and isinstance(chapter_data, list)
                        and len(chapter_data) == 2
                    ):
                        ch_title, ch_content = chapter_data
                        ch_title = (
                            ch_title
                            or chapter_meta.get("title")
                            or f"Chapter {chapter_id_str}"
                        )
                        # Define error content more robustly
                        is_error_content = isinstance(ch_content, str) and (
                            "Error" in ch_content or ch_content == "Empty Content"
                        )

                        if ch_content and not is_error_content:
                            try:
                                chapter_id_db = int(chapter_id_str)
                                chapter_entry = Chapter(
                                    id=chapter_id_db,
                                    novel_id=novel_id,
                                    chapter_index=index,  # Use the loop index for ordering
                                    title=ch_title,
                                    content=ch_content,  # Store the actual content
                                    fetched_at=datetime.utcnow(),
                                )
                                # Use merge to handle potential re-runs or existing chapters
                                db.session.merge(chapter_entry)
                                saved_count += 1
                            except ValueError:
                                error_reason = "Invalid ID format for DB"
                                logger.warning(
                                    f"Task {celery_task_id}: Skipping chapter {chapter_id_str} ('{ch_title}'): {error_reason}"
                                )
                                chapters_with_errors.append(
                                    {
                                        "id": chapter_id_str,
                                        "title": ch_title,
                                        "reason": error_reason,
                                    }
                                )
                            except Exception as chapter_save_err:
                                error_reason = f"DB merge error: {chapter_save_err}"
                                logger.error(
                                    f"Task {celery_task_id}: Error merging chapter {chapter_id_str} to DB: {chapter_save_err}",
                                    exc_info=True,
                                )
                                chapters_with_errors.append(
                                    {
                                        "id": chapter_id_str,
                                        "title": ch_title,
                                        "reason": error_reason,
                                    }
                                )
                        else:
                            # Record chapters that had download errors or were empty
                            error_reason = (
                                ch_content
                                if isinstance(ch_content, str)
                                else "Download Error/Empty"
                            )
                            logger.warning(
                                f"Task {celery_task_id}: Skipping chapter {chapter_id_str} ('{ch_title}') due to error marker: {error_reason}"
                            )
                            chapters_with_errors.append(
                                {
                                    "id": chapter_id_str,
                                    "title": ch_title,
                                    "reason": error_reason,
                                }
                            )
                    else:
                        # Record chapters missing from downloaded data
                        ch_title = chapter_meta.get(
                            "title", f"Unknown Title {chapter_id_str}"
                        )
                        error_reason = (
                            "Missing from download data"
                            if not chapter_data
                            else "Incorrect data format"
                        )
                        logger.warning(
                            f"Task {celery_task_id}: Skipping chapter {chapter_id_str} ('{ch_title}'): {error_reason}"
                        )
                        chapters_with_errors.append(
                            {
                                "id": chapter_id_str,
                                "title": ch_title,
                                "reason": error_reason,
                            }
                        )

            # Commit the transaction for chapter saves
            db.session.commit()
            logger.info(
                f"Task {celery_task_id}: Saved/Merged {saved_count} chapters. {len(chapters_with_errors)} errors/missing."
            )
            # --- DB SAVE LOOP END ---
        except Ignore as term_signal:  # Catch Ignore raised within the loop
            db.session.rollback()  # Rollback partial saves
            logger.warning(f"Task {celery_task_id} DB save interrupted: {term_signal}")
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.TERMINATED,
                message=str(term_signal),  # Use the exception message
            )
            # State already set before Ignore was raised
            return {
                "status": "REVOKED",
                "message": str(term_signal),
            }
        except Exception as db_commit_err:
            db.session.rollback()  # Rollback on any other error during save
            logger.error(
                f"Task {celery_task_id}: DB transaction failed during chapter save: {db_commit_err}",
                exc_info=True,
            )
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.FAILED,
                message=f"DB transaction failed: {db_commit_err}",
            )
            # Reraise to mark Celery task as failed
            raise
        finally:
            if _app_context:
                _app_context.pop()  # Ensure context is popped

        # --- 6. Finalize Download Manager ---
        # Calculate total failed chapters (download + processing errors)
        total_failed_count = (
            download_results.get("failed", 0)
            if isinstance(download_results, dict)
            else 0
        ) + len(chapters_with_errors)
        if book_manager:
            try:
                book_manager.finalize_download(chapters_list, total_failed_count)
                logger.info(
                    f"Task {celery_task_id}: Finalized book manager (e.g., saved status/EPUB)."
                )
            except Exception as finalize_err:
                logger.error(
                    f"Task {celery_task_id}: Error finalizing book manager: {finalize_err}",
                    exc_info=True,
                )
                # Continue anyway, but log the error

        # --- 7. Run Analysis ---
        analysis_message = ""
        if saved_count > 0:
            _update_db_task_status(
                db_task_id,
                user_id,
                TaskStatus.PROCESSING,
                progress=95,
                message="Analyzing content...",
            )
            try:
                # Run analysis synchronously within this task
                analyze_novel_task(novel_id)  # Changed from delay to direct call
                analysis_message = "Analysis done."
                logger.info(f"Task {celery_task_id}: Content analysis completed.")
            except Exception as analysis_err:
                logger.error(
                    f"Task {celery_task_id}: Analysis failed: {analysis_err}",
                    exc_info=True,
                )
                analysis_message = f"Analysis failed: {analysis_err}"
        else:
            analysis_message = "Analysis skipped (no chapters saved)."
            logger.warning(
                f"Task {celery_task_id}: Skipping analysis as no chapters were saved."
            )
            # Clean up any potentially stale word stats
            if _app_context:
                _app_context.push()
            try:
                WordStat.query.filter_by(novel_id=novel_id).delete()
                db.session.commit()
            except Exception as e_stat:
                logger.error(
                    f"Task {celery_task_id}: Failed clear stale word stats: {e_stat}"
                )
                db.session.rollback()
            finally:
                if _app_context:
                    _app_context.pop()

        # --- 8. Final Status Update ---
        final_message = (
            f"Completed. Saved {saved_count}/{total_chapters_src}. {analysis_message}"
        )
        if chapters_with_errors:
            # Add summary of errors if any occurred
            error_reasons = set(e["reason"] for e in chapters_with_errors)
            final_message += f" ({len(chapters_with_errors)} errors/missing: {', '.join(list(error_reasons)[:2])}...)"
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.COMPLETED,
            progress=100,
            message=final_message,
        )
        logger.info(f"Task {celery_task_id}: Processing successful.")
        return {
            "status": "SUCCESS",
            "message": final_message,
            "chapters_processed_db": saved_count,
            "errors": len(chapters_with_errors),
        }

    except (
        Ignore
    ) as term_signal:  # Catch Ignore raised from deeper levels if not caught earlier
        # This block handles cases where Ignore was raised explicitly
        logger.warning(
            f"Task {celery_task_id} processing explicitly stopped due to termination signal: {term_signal}"
        )
        # Status should have been updated where Ignore was raised, but ensure TERMINATED status in DB
        _update_db_task_status(
            db_task_id,
            user_id,
            TaskStatus.TERMINATED,
            message=f"Task terminated: {term_signal}",
        )
        # Celery state should already be REVOKED if Ignore was used correctly
        return {"status": "REVOKED", "message": f"Task terminated: {term_signal}"}

    except Exception as e:
        # Catch-all for unexpected errors during the main try block
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"Task {celery_task_id}: FAILED processing novel {novel_id}. Error: {error_type} - {error_msg}",
            exc_info=True,
        )
        # Update DB task status to FAILED
        _update_db_task_status(
            db_task_id, user_id, TaskStatus.FAILED, message=f"{error_type}: {error_msg}"
        )
        # Reraise the exception so Celery marks the task as FAILURE
        raise


# --- Analysis Task (kept separate for potential future async use) ---
@celery_app.task(bind=True, name="tasks.analyze_novel")
def analyze_novel_task(self, novel_id: int) -> Dict[str, Any]:
    """
    Celery task to perform word frequency analysis and generate a word cloud for a novel.
    Note: Currently called synchronously from process_novel_task.
    """
    # Use Flask logger if available, otherwise use standard logger
    logger = current_app.logger if current_app else logging.getLogger("celery.tasks")
    task_id = self.request.id  # Use self.request.id for Celery task ID
    logger.info(f"Analysis Task {task_id}: Starting analysis for novel ID: {novel_id}")

    # Use Flask app context for DB operations if available
    _app_context = current_app.app_context() if current_app else None
    if _app_context:
        _app_context.push()

    try:
        # Call the analysis function (which interacts with DB)
        image_path = update_word_stats(novel_id)
        message = (
            "Analysis complete. Wordcloud generated."
            if image_path
            else "Analysis complete. Wordcloud not generated (no data or error)."
        )
        logger.info(f"Analysis Task {task_id}: {message}")
        return {"status": "SUCCESS", "message": message, "image_path": image_path}

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"Analysis Task {task_id}: FAILED analysis for novel {novel_id}. Error: {error_type} - {error_msg}",
            exc_info=True,
        )
        # Reraise the exception so Celery marks the task as FAILURE
        raise
    finally:
        if _app_context:
            _app_context.pop()  # Ensure context is popped
