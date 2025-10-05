# -------------------------------
# downloader.py - 核心下载模块
# 职责：实现多线程下载和任务管理
# -------------------------------
# backend/novel_downloader/novel_src/network_parser/downloader.py
import re
import time
import json
import requests
import random
import threading
import signal
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import List, Dict, Optional, Tuple, Callable

from .network import NetworkClient
from .proxy_downloader import ProxyChapterDownloader
from ..offical_tools.downloader import download_chapter_official, spawn_iid
from ..offical_tools.epub_downloader import fetch_chapter_for_epub
from ..book_parser.book_manager import BookManager
from ..book_parser.parser import ContentParser
from ..base_system.context import GlobalContext
from ..base_system.log_system import (
    TqdmLoggingHandler,
    LogSystem,
)


class APIManager:
    def __init__(self, api_endpoints, config, network_status):
        self.api_queue = queue.Queue()
        self.config = config
        self.network_status = network_status
        for ep in api_endpoints:
            self.api_queue.put(ep)

    def get_api(self, timeout=1.0):
        while True:
            try:
                ep = self.api_queue.get(timeout=timeout)
            except queue.Empty:
                time.sleep(0.05)
                continue
            st = self.network_status.get(ep, {})
            if time.time() < st.get("cooldown_until", 0):
                self.api_queue.put(ep)
                time.sleep(0.05)
                continue
            return ep

    def release_api(self, ep):
        self.api_queue.put(ep)


class ChapterDownloader:
    def __init__(self, book_id: str, network_client: NetworkClient):
        self.book_id = book_id
        self.network = network_client
        self.logger = GlobalContext.get_logger()
        self.log_system: Optional[LogSystem] = GlobalContext.get_log_system()
        self.config = GlobalContext.get_config()

        self._stop_event = threading.Event()
        self._orig_handler = signal.getsignal(signal.SIGINT)
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
        except ValueError:  # Cannot set SIGINT handler in non-main thread
            pass

        # Only initialize APIManager if we have endpoints and not using proxy API
        if self.config.api_endpoints and not (hasattr(self.config, 'use_proxy_api') and self.config.use_proxy_api):
            self.api_manager = APIManager(
                api_endpoints=self.config.api_endpoints,
                config=self.config,
                network_status=self.network._api_status,
            )
        else:
            self.api_manager = None

    def _handle_signal(self, signum, frame):
        self.logger.warning("Received Ctrl-C, preparing graceful exit...")
        self._stop_event.set()
        # Restore handler immediately only if it was originally set
        if (
            self._orig_handler is not None
            and self._orig_handler != signal.SIG_IGN
            and self._orig_handler != signal.SIG_DFL
        ):
            try:
                signal.signal(signal.SIGINT, self._orig_handler)
            except ValueError:
                pass

    def download_book(
        self,
        book_manager: BookManager,
        book_name: str,
        chapters: List[Dict],
        progress_callback: Optional[
            Callable[[int, int], None]
        ] = None,  # Accept callback
    ) -> Dict[str, int]:
        if self.config.use_official_api and not self.config.iid:
            spawn_iid()

        orig_handlers = []
        if self.log_system:
            orig_handlers = self.logger.handlers.copy()
            for h in orig_handlers:
                if not isinstance(h, TqdmLoggingHandler):
                    try:
                        self.logger.removeHandler(h)
                    except ValueError:
                        pass

        results = {"success": 0, "failed": 0, "canceled": 0}
        to_download = [
            ch
            for ch in chapters
            if (ch["id"] not in book_manager.downloaded)
            or (
                book_manager.downloaded.get(ch["id"], [None, "Error"])[1] == "Error"
            )  # Safer default
        ]
        tasks_count = len(to_download)  # This is the count for THIS download run

        if not tasks_count:
            self.logger.info(f"No chapters to download for '{book_name}'.")
            return results  # Return early if nothing to do

        # 优先使用代理API模式
        if hasattr(self.config, 'use_proxy_api') and self.config.use_proxy_api:
            self.logger.info(f"Using Proxy API mode for download")
            max_workers = min(self.config.max_workers, tasks_count)
            max_workers = max(1, max_workers)
            
            def get_submit(exe):
                return {exe.submit(self._download_proxy, ch): ch for ch in to_download}
            
            desc = f"Downloading '{book_name}' (Proxy API)"
        elif self.config.use_official_api:
            # 改为单章下载模式，提高稳定性
            batch_size = 1  # 一次下载一章，避免批量API限流问题
            groups = [to_download[i : i + batch_size] for i in range(0, len(to_download), batch_size)]
            max_workers = min(self.config.max_workers, tasks_count)  # 限制并发数

            def get_submit(exe):
                return {
                    exe.submit(self._download_official_batch, grp): grp
                    for grp in groups
                }

            desc = f"Downloading '{book_name}' (Official Batch)"
        else:
            # For single-chapter mode, ensure max_workers is at least 1
            # If api_endpoints is configured, limit by its length
            if self.config.api_endpoints:
                max_workers = min(
                    self.config.max_workers, len(self.config.api_endpoints), tasks_count
                )
            else:
                max_workers = min(self.config.max_workers, tasks_count)
            max_workers = max(1, max_workers)  # Ensure at least 1 worker

            def get_submit(exe):
                return {exe.submit(self._download_single, ch): ch for ch in to_download}

            desc = f"Downloading '{book_name}'"

        with ThreadPoolExecutor(max_workers=max_workers) as exe:
            futures = get_submit(exe)
            pbar = tqdm(total=tasks_count, desc=desc)  # Use tasks_count for total
            if self.log_system:
                self.log_system.enable_tqdm_handler(pbar)

            try:
                for future in as_completed(futures):
                    if self._stop_event.is_set():
                        self._cancel_pending(futures)  # Attempt to cancel
                        break

                    task_info = futures[future]  # chapter dict or list of chapter dicts
                    batch_success_count = 0
                    try:
                        # 判断是否为官方API批量模式
                        is_official_batch = (self.config.use_official_api and 
                                           not (hasattr(self.config, 'use_proxy_api') and self.config.use_proxy_api))
                        
                        if is_official_batch:
                            batch_out: Dict[str, Tuple[str, str]] = future.result()
                            for cid, chapter_result in batch_out.items():
                                if (
                                    isinstance(chapter_result, tuple)
                                    and len(chapter_result) == 2
                                ):
                                    content, title = chapter_result
                                    if content == "Error" or "Error" in str(content):
                                        book_manager.save_error_chapter(
                                            cid, title or cid, str(content)
                                        )
                                        results["failed"] += 1
                                    else:
                                        book_manager.save_chapter(cid, title, content)
                                        results["success"] += 1
                                        batch_success_count += (
                                            1  # Count success within this batch
                                        )
                                else:
                                    self.logger.warning(
                                        f"Unexpected result format for official chapter {cid}: {chapter_result}"
                                    )
                                    book_manager.save_error_chapter(
                                        cid, cid, "Format Error"
                                    )
                                    results["failed"] += 1
                        else:  # Non-official API (single chapter)
                            result_tuple = future.result()
                            if (
                                isinstance(result_tuple, tuple)
                                and len(result_tuple) == 2
                            ):
                                content, title = result_tuple
                                cid = task_info["id"]
                                if content == "Error" or "Error" in str(content):
                                    book_manager.save_error_chapter(
                                        cid,
                                        title or task_info.get("title", cid),
                                        str(content),
                                    )
                                    results["failed"] += 1
                                else:
                                    book_manager.save_chapter(cid, title, content)
                                    results["success"] += 1
                                    batch_success_count = (
                                        1  # Single chapter is a "batch" of 1
                                    )
                            else:
                                cid = task_info["id"]
                                self.logger.warning(
                                    f"Unexpected result format for non-official chapter {cid}: {result_tuple}"
                                )
                                book_manager.save_error_chapter(
                                    cid, task_info.get("title", cid), "Format Error"
                                )
                                results["failed"] += 1

                        # --- Call progress callback ---
                        if batch_success_count > 0 and progress_callback:
                            try:
                                progress_callback(results["success"], tasks_count)
                            except Exception as cb_err:
                                self.logger.error(
                                    f"Progress callback failed: {cb_err}", exc_info=True
                                )
                        # --- End callback ---

                    except KeyboardInterrupt:
                        self._stop_event.set()  # Set stop event on first Ctrl+C
                        self.logger.warning("Graceful stop initiated...")
                        self._cancel_pending(futures)
                        break  # Exit the loop
                    except Exception as inner_e:
                        self.logger.error(
                            f"Error processing future result: {inner_e}", exc_info=True
                        )
                        failed_ids = []
                        if self.config.use_official_api and isinstance(task_info, list):
                            failed_ids = [ch.get("id", "unknown") for ch in task_info]
                        elif not self.config.use_official_api and isinstance(
                            task_info, dict
                        ):
                            failed_ids = [task_info.get("id", "unknown")]
                        for fid in failed_ids:
                            ch_title = (
                                task_info.get("title", fid)
                                if isinstance(task_info, dict)
                                else fid
                            )
                            book_manager.save_error_chapter(
                                fid,
                                ch_title,
                                f"Processing Error: {type(inner_e).__name__}",
                            )
                            results["failed"] += 1

                    # 更新进度条
                    is_proxy_or_single = (hasattr(self.config, 'use_proxy_api') and self.config.use_proxy_api) or \
                                        (not self.config.use_official_api)
                    pbar.update(
                        1 if is_proxy_or_single else len(task_info)
                    )  # Update pbar correctly

            finally:
                if self.log_system:
                    self.log_system.disable_tqdm_handler()
                pbar.close()

        canceled_count = tasks_count - results["success"] - results["failed"]
        results["canceled"] = max(0, canceled_count)

        book_manager.save_download_status()
        # Note: finalize_download is now called in the Celery task after DB save
        # book_manager.finalize_download(chapters, results["failed"] + results["canceled"])

        if self.log_system and orig_handlers:
            for h in orig_handlers:
                try:
                    if h not in self.logger.handlers:
                        self.logger.addHandler(h)
                except Exception as add_h_err:
                    self.logger.error(f"Failed to re-add handler {h}: {add_h_err}")

        if (
            self._orig_handler is not None
            and self._orig_handler != signal.SIG_IGN
            and self._orig_handler != signal.SIG_DFL
        ):
            try:
                signal.signal(signal.SIGINT, self._orig_handler)
            except ValueError:
                pass

        return results

    def _cancel_pending(self, futures):
        canceled_count = 0
        for f in futures:
            if not f.done():
                if f.cancel():
                    canceled_count += 1
        if canceled_count > 0:
            self.logger.info(
                f"Attempted to cancel {canceled_count} pending download tasks."
            )

    def _download_single(self, chapter: dict) -> Tuple[str, str]:
        chapter_id = chapter["id"]
        chapter_title = chapter.get("title") or f"Chapter {chapter_id}"
        req_id = f"{chapter_id[:4]}-{random.randint(1000, 9999)}"
        # self.logger.debug(f"[{req_id}] Downloading {chapter_title}") # Reduced verbosity

        retry = 0
        tried = set()
        while retry < self.config.max_retries:
            if self._stop_event.is_set():
                self.logger.warning(
                    f"[{req_id}] Download cancelled for {chapter_title}"
                )
                return "Error: Cancelled", chapter_title

            ep = None
            api_check_count = 0
            max_api_checks = len(self.config.api_endpoints) * 2
            while api_check_count < max_api_checks:
                cand = self.api_manager.get_api(timeout=0.1)
                if not cand:
                    time.sleep(0.1)
                    api_check_count += 1
                    continue
                if cand in tried:
                    self.api_manager.release_api(cand)
                    time.sleep(0.05)
                    api_check_count += 1
                    continue
                ep = cand
                break
            else:
                self.logger.error(
                    f"[{req_id}] No available API endpoints found for {chapter_title}."
                )
                return "Error: No API", chapter_title

            tried.add(ep)
            stt = self.network._api_status.get(ep, {})  # Get status dict safely

            try:
                base_url = ep.rstrip("/")
                url = f"{base_url}/content?item_id={chapter_id}"
                dt = random.randint(
                    self.config.min_wait_time, self.config.max_wait_time
                )
                time.sleep(dt / 1000.0)
                st_time = time.time()
                resp = requests.get(
                    url,
                    headers=self.network.get_headers(),
                    timeout=(
                        self.config.min_connect_timeout,
                        self.config.request_timeout,
                    ),
                )
                rt = time.time() - st_time

                if ep in self.network._api_status:  # Check if ep still valid
                    stt = self.network._api_status[ep]
                    stt["response_time"] = stt.get("response_time", rt) * 0.7 + rt * 0.3
                else:
                    stt = {}  # API status gone, can't update

                resp.raise_for_status()
                data = resp.json()

                # Expecting {chapter_id: {content, title}} structure from ContentParser
                parsed_content = ContentParser.extract_api_content({chapter_id: data})
                if chapter_id in parsed_content:
                    content, title_from_api = parsed_content[chapter_id]
                    final_title = title_from_api or chapter_title
                    if not content or content == "Error":
                        self.logger.warning(
                            f"[{req_id}] Parsed empty/error content for: {final_title}"
                        )
                        # Still release API, but return error
                        self.api_manager.release_api(ep)
                        return "Error: Empty/API Error", final_title
                else:
                    self.logger.error(
                        f"[{req_id}] Failed to extract content for {chapter_id} from API."
                    )
                    # Still release API, but return error
                    self.api_manager.release_api(ep)
                    return "Error: Parsing Failed", chapter_title

                if stt:  # Update status only if dict exists
                    stt["failure_count"] = 0
                    stt["last_success"] = time.time()

                # self.logger.info(f"[{req_id}] Success: {final_title} ({rt:.2f}s)") # Reduced verbosity
                self.api_manager.release_api(ep)
                return content, final_title

            except requests.exceptions.Timeout:
                self.logger.warning(
                    f"[{req_id}] Timeout for {chapter_title}, retry {retry + 1}/{self.config.max_retries}"
                )
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[{req_id}] Network error for {chapter_title}: {e}")
                if (
                    hasattr(e, "response")
                    and e.response is not None
                    and e.response.status_code == 404
                ):
                    self.logger.error(
                        f"[{req_id}] Chapter {chapter_id} not found (404)."
                    )
                    self.api_manager.release_api(ep)
                    return "Error: Not Found", chapter_title
            except json.JSONDecodeError:
                self.logger.error(f"[{req_id}] JSON decode error for {chapter_title}.")
            except Exception as e:
                self.logger.error(
                    f"[{req_id}] Unexpected error for {chapter_title}: {e}",
                    exc_info=True,
                )

            if stt:  # Cooldown logic only if dict exists
                stt["failure_count"] = stt.get("failure_count", 0) + 1
                if stt["failure_count"] > 5:
                    cooldown_time = random.randint(10, 30)
                    stt["cooldown_until"] = time.time() + cooldown_time
                    self.logger.warning(
                        f"[{req_id}] API {ep} failed {stt['failure_count']} times, cooling down for {cooldown_time}s."
                    )

            self.api_manager.release_api(ep)  # Release API after failure/retry logic
            time.sleep(0.5 * (2**retry))
            retry += 1

        self.logger.error(
            f"[{req_id}] Failed {chapter_title} after {self.config.max_retries} retries."
        )
        return "Error: Max Retries", chapter_title

    def _download_proxy(self, chapter: dict) -> Tuple[str, str]:
        """使用代理API下载单个章节"""
        proxy_downloader = ProxyChapterDownloader()
        chapter_id = chapter["id"]
        chapter_title = chapter.get("title") or f"Chapter {chapter_id}"
        return proxy_downloader.download_chapter(chapter_id, chapter_title)
    
    def _download_official_batch(
        self, chapters: List[dict]
    ) -> Dict[str, Tuple[str, str]]:
        if not chapters:
            return {}
        ids = ",".join(ch["id"] for ch in chapters)
        first_id_prefix = chapters[0]["id"][:4] if chapters[0].get("id") else "xxxx"
        req_id = f"{first_id_prefix}-{random.randint(1000, 9999)}"
        # self.logger.debug(f"[{req_id}] Batch download {len(chapters)} chapters") # Reduced verbosity

        dt = random.randint(self.config.min_wait_time, self.config.max_wait_time)
        time.sleep(dt / 1000.0)
        start_time = time.time()
        try:
            if self._stop_event.is_set():
                raise InterruptedError("Cancelled before batch fetch")

            raw_data = fetch_chapter_for_epub(
                ids
            )  # Assumes this handles its own retries/errors if necessary
            chapters_dict = ContentParser.extract_api_content(raw_data)
            elapsed = time.time() - start_time
            # self.logger.info(f"[{req_id}] Batch download complete ({elapsed:.2f}s)") # Reduced verbosity

            final_result = {}
            for ch in chapters:
                cid = ch["id"]
                if cid in chapters_dict:
                    content, title = chapters_dict[cid]
                    if not content or content == "Error" or "Error" in str(content):
                        final_result[cid] = (
                            "Error: Content Issue",
                            title or ch.get("title", cid),
                        )
                    else:
                        final_result[cid] = (content, title or ch.get("title", cid))
                else:
                    self.logger.warning(
                        f"[{req_id}] Chapter ID {cid} missing in official batch result."
                    )
                    final_result[cid] = (
                        "Error: Missing in Result",
                        ch.get("title", cid),
                    )
            return final_result

        except InterruptedError:
            self.logger.warning(f"[{req_id}] Batch download cancelled.")
            return {
                ch["id"]: ("Error: Cancelled", ch.get("title", ch["id"]))
                for ch in chapters
            }
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(
                f"[{req_id}] Batch download failed after {elapsed:.2f}s: {e}",
                exc_info=True,
            )
            return {
                ch["id"]: (
                    f"Error: Batch Failed ({type(e).__name__})",
                    ch.get("title", ch["id"]),
                )
                for ch in chapters
            }
