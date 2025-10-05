"""
番茄小说代理API下载器
使用第三方代理服务器绕过官方API的限制
"""
import time
import random
import requests
from typing import Dict, Tuple, List
from ..base_system.context import GlobalContext

# 代理服务器地址（来自妍希书源）
PROXY_BASE_URL = "https://fanqie.hnxianxin.cn"


class ProxyChapterDownloader:
    """使用代理API下载章节"""
    
    def __init__(self):
        self.logger = GlobalContext.get_logger()
        self.config = GlobalContext.get_config()
        self.session = requests.Session()
        
    def download_chapter(self, item_id: str, chapter_title: str = "") -> Tuple[str, str]:
        """
        下载单个章节
        
        Args:
            item_id: 章节ID
            chapter_title: 章节标题（用于日志）
            
        Returns:
            (content, title): 章节内容和标题
        """
        req_id = f"{item_id[:4]}-{random.randint(1000, 9999)}"
        
        retry = 0
        while retry < self.config.max_retries:
            try:
                # 构造请求URL
                url = f"{PROXY_BASE_URL}/content?item_id={item_id}"
                
                # 添加随机延迟
                wait_time = random.randint(
                    self.config.min_wait_time, 
                    self.config.max_wait_time
                ) / 1000.0
                time.sleep(wait_time)
                
                # 发起请求
                self.logger.info(f"[{req_id}] Requesting chapter via proxy: {chapter_title}")
                self.logger.info(f"[{req_id}] URL: {url}")
                
                response = requests.get(
                    url,
                    timeout=(
                        self.config.min_connect_timeout,
                        self.config.request_timeout
                    ),
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                self.logger.info(f"[{req_id}] Response status: {response.status_code}, length: {len(response.content)}")
                
                # 解析响应 - 代理API返回格式: {success: true, item_id: xxx, content: xxx}
                if data.get("success") and "content" in data:
                    content = data.get("content", "")
                    # 从HTML中提取标题
                    import re
                    title_match = re.search(r'<div class="tt-title">(.+?)</div>', content)
                    title = title_match.group(1) if title_match else chapter_title
                    
                    # 清理水印
                    content = content.replace("妍希", "")
                    
                    if content:
                        self.logger.info(f"[{req_id}] Successfully downloaded: {title}")
                        return content, title
                    else:
                        self.logger.warning(f"[{req_id}] Empty content for: {title}")
                        return "Error: Empty Content", title
                else:
                    error_msg = data.get("message", "API request failed")
                    self.logger.error(f"[{req_id}] API error: {error_msg}")
                    return f"Error: {error_msg}", chapter_title
                    
            except requests.exceptions.Timeout:
                self.logger.warning(
                    f"[{req_id}] Timeout for {chapter_title}, retry {retry + 1}/{self.config.max_retries}"
                )
                retry += 1
                time.sleep(0.5 * (2 ** retry))
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[{req_id}] Request error for {chapter_title}: {e}")
                retry += 1
                time.sleep(0.5 * (2 ** retry))
                
            except Exception as e:
                self.logger.error(
                    f"[{req_id}] Unexpected error for {chapter_title}: {e}",
                    exc_info=True
                )
                retry += 1
                time.sleep(0.5 * (2 ** retry))
        
        self.logger.error(f"[{req_id}] Failed after {self.config.max_retries} retries: {chapter_title}")
        return "Error: Max Retries", chapter_title
    
    def download_multi_chapters(self, chapters: List[Dict]) -> Dict[str, Tuple[str, str]]:
        """
        批量下载多个章节
        
        Args:
            chapters: 章节列表，每个包含 id 和 title
            
        Returns:
            {chapter_id: (content, title)}
        """
        results = {}
        
        for chapter in chapters:
            item_id = chapter.get("id")
            title = chapter.get("title", f"Chapter {item_id}")
            
            content, final_title = self.download_chapter(item_id, title)
            results[item_id] = (content, final_title)
            
        return results
