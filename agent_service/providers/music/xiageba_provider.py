"""
XiagebaProvider 下歌吧 (刘明野) 核心音乐源 Provider
基于 Step 5 架构规范：
对接 https://xiageba.liumingye.cn/ 作为核心免费音乐源之一，
提供高准确率歌曲搜索、原版高清封面图、多音质资源获取与直接下载能力。
"""
import os
import re
import uuid
import logging
import asyncio
import httpx
from typing import List, Optional, Dict, Any, Callable
from .base import BaseMusicProvider, ProviderCapabilities, TrackCandidate

logger = logging.getLogger("AgentLogger")


class XiagebaProvider(BaseMusicProvider):
    """下歌吧 (刘明野) 网络音乐检索与音源解析 Provider"""

    def __init__(
        self,
        base_url: str = "https://xiageba.liumingye.cn",
        timeout: float = 8.0
    ):
        super().__init__(
            name="xiageba",
            capabilities=ProviderCapabilities(
                can_search=True,
                can_resolve=True,
                can_stream=True,
                can_download=True
            )
        )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://xiageba.liumingye.cn/",
            "Accept": "application/json, text/plain, */*"
        }

    async def check_availability(self) -> bool:
        """探针检测下歌吧站点连通性"""
        try:
            async with httpx.AsyncClient(timeout=4.0, verify=False, http2=False) as client:
                resp = await client.get(f"{self.base_url}/api/music/search?q=test&page=1&pageSize=1", headers=self.headers)
                return resp.status_code == 200
        except Exception as e:
            logger.debug(f"[XiagebaProvider] 探针检测失败: {e}")
            return False

    async def search(self, query: str, artist: str = "", limit: int = 5) -> List[TrackCandidate]:
        """
        在下歌吧平台并发检索音乐曲目
        """
        clean_q = query.strip()
        clean_art = artist.strip()
        if not clean_q and not clean_art:
            return []

        search_kw = f"{clean_art} {clean_q}".strip() if (clean_art and clean_q) else (clean_q or clean_art)
        results: List[TrackCandidate] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False, http2=False, trust_env=True) as client:
                search_url = f"{self.base_url}/api/music/search"
                params = {
                    "q": search_kw,
                    "page": 1,
                    "pageSize": max(limit * 2, 10),
                    "exact": "false"
                }
                resp = None
                for attempt in range(2):
                    try:
                        resp = await client.get(search_url, params=params, headers=self.headers, timeout=self.timeout)
                        if resp.status_code == 200:
                            break
                    except Exception as conn_err:
                        if attempt == 1:
                            logger.debug(f"[XiagebaProvider] 检索连接异常: {conn_err}")
                        await asyncio.sleep(0.3)

                if not resp or resp.status_code != 200:
                    logger.debug(f"[XiagebaProvider] 下歌吧站点暂无响应或返回状态: {resp.status_code if resp else 'None'}")
                    return []

                res_json = resp.json()
                items = res_json.get("data", [])
                if not items:
                    logger.info(f"[XiagebaProvider] 未检索到相关曲目: {search_kw}")
                    return []

                # 1. 筛选匹配歌名的优质候选 (避免不相关曲目耗费网络)
                matched_items = []
                for item in items:
                    item_id = item.get("id")
                    title = item.get("title", "").strip()
                    if not title or not item_id:
                        continue

                    t_lower = title.lower()
                    q_lower = clean_q.lower() if clean_q else ""
                    if q_lower and (q_lower not in t_lower and t_lower not in q_lower):
                        continue
                    matched_items.append(item)
                    if len(matched_items) >= limit:
                        break

                if not matched_items:
                    logger.info(f"[XiagebaProvider] 搜索结果中无完全匹配歌名: {clean_q}")
                    return []

                # 2. 并发异步获取各候选详情
                async def fetch_item_detail(iid: str) -> Dict[str, Any]:
                    try:
                        det_resp = await client.get(f"{self.base_url}/api/music/{iid}", headers=self.headers, timeout=6.0)
                        if det_resp.status_code == 200:
                            return det_resp.json()
                    except Exception as ex:
                        logger.debug(f"[XiagebaProvider] 并发获取详情跳过 ({iid}): {ex}")
                    return {}

                detail_tasks = [fetch_item_detail(it.get("id")) for it in matched_items]
                details_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

                for idx, item in enumerate(matched_items):
                    item_id = item.get("id")
                    title = item.get("title", "").strip()
                    item_artist = item.get("artist", "").strip()
                    detail_data = details_results[idx] if (idx < len(details_results) and isinstance(details_results[idx], dict)) else {}

                    t_lower = title.lower()
                    a_lower = item_artist.lower()
                    q_lower = clean_q.lower() if clean_q else ""
                    art_lower = clean_art.lower() if clean_art else ""

                    score = 0.85
                    if q_lower and q_lower == t_lower:
                        score += 0.10
                    elif q_lower and (q_lower in t_lower or t_lower in q_lower):
                        score += 0.05
                    if art_lower and (art_lower in a_lower or a_lower in art_lower):
                        score += 0.04
                    score = min(0.99, score)

                    cover_url = detail_data.get("cover") or item.get("cover") or ""
                    play_url = detail_data.get("playUrl", "").strip()
                    downloads = detail_data.get("downloads", [])

                    qualities = item.get("quality", [])
                    has_flac = any("flac" in str(q).lower() or "wav" in str(q).lower() for q in qualities)
                    audio_fmt = "flac" if has_flac else "mp3"
                    bitrate = 960 if has_flac else 320

                    candidate_url = play_url
                    is_netdisk = False
                    if not candidate_url and downloads:
                        for d in downloads:
                            d_url = d.get("url", "")
                            if d_url.lower().endswith((".mp3", ".flac", ".wav", ".m4a")):
                                candidate_url = d_url
                                break
                        if not candidate_url:
                            candidate_url = downloads[0].get("url", "")
                            if "pan.baidu.com" in candidate_url or "pan.quark.cn" in candidate_url:
                                is_netdisk = True
                                # 网盘资源评分适当下调，优先让位给可直接下载/播放的直链或 P2P 音频
                                score = min(score, 0.78)

                    is_remix = any(k in t_lower for k in ["remix", "rmx", "electro", "慢摇", "串烧", "dj", "热血版"])
                    is_cover = any(k in t_lower or k in a_lower for k in ["cover", "翻唱", "翻自"])
                    is_inst = any(k in t_lower for k in ["伴奏", "inst", "instrumental"])

                    if is_netdisk:
                        version_tag = "网盘转存 (无损)" if has_flac else "网盘转存"
                    elif is_remix:
                        version_tag = "DJ混音"
                    elif is_cover:
                        version_tag = "翻唱版"
                    elif is_inst:
                        version_tag = "伴奏"
                    elif has_flac:
                        version_tag = "原版无损"
                    else:
                        version_tag = "原版音频"

                    candidate = TrackCandidate(
                        id=f"xiageba_{item_id}",
                        title=title,
                        artist=item_artist or clean_art or "下歌吧音乐人",
                        album=item.get("album") or f"《{title}》",
                        duration=240,
                        bitrate=bitrate,
                        format=audio_fmt,
                        size_bytes=10485760 if has_flac else 8388608,
                        url=candidate_url,
                        cover_url=cover_url or None,
                        provider=self.name,
                        source_type="web",
                        confidence=score,
                        capabilities=self.capabilities.to_list(),
                        extra={
                            "is_netdisk": is_netdisk,
                            "version_tag": version_tag,
                            "is_remix": is_remix,
                            "is_cover": is_cover,
                            "raw_downloads": downloads
                        }
                    )
                    results.append(candidate)

        except Exception as e:
            logger.debug(f"[XiagebaProvider] 检索流程捕获异常: {e}")

        results.sort(key=lambda c: c.confidence, reverse=True)
        return results[:limit]

    async def resolve_download_url(self, candidate: TrackCandidate) -> Optional[str]:
        """解析歌曲真实直链"""
        if candidate.url and candidate.url.startswith("http"):
            return candidate.url
        return None

    async def download_track(
        self,
        candidate: TrackCandidate,
        target_path: str,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        通过下歌吧下载曲目至本地 target_path
        支持 HTTP 分块流式下载并实时反馈进度
        """
        direct_url = await self.resolve_download_url(candidate)
        if not direct_url:
            logger.warning(f"[XiagebaProvider] 《{candidate.title}》暂无直接可下载的 HTTP 直链")
            return False

        # 如果直链属于百度网盘/夸克网盘链接，非直接音频流
        if "pan.baidu.com" in direct_url or "pan.quark.cn" in direct_url:
            logger.info(f"[XiagebaProvider] 《{candidate.title}》为网盘转存资源: {direct_url}")
            return False

        try:
            async with httpx.AsyncClient(timeout=25.0, verify=False, http2=False, follow_redirects=True) as client:
                async with client.stream("GET", direct_url, headers=self.headers) as resp:
                    if resp.status_code != 200:
                        logger.warning(f"[XiagebaProvider] 直链响应状态码非 200: {resp.status_code}")
                        return False

                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/html" in content_type or "application/json" in content_type:
                        logger.warning(f"[XiagebaProvider] URL 返回非音频内容: {content_type}")
                        return False

                    total = int(resp.headers.get("content-length", 0)) or candidate.size_bytes or 8388608
                    downloaded = 0
                    last_report = 0

                    with open(target_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=32768):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if on_progress and (downloaded - last_report >= 131072 or downloaded >= total):
                                last_report = downloaded
                                import inspect
                                if inspect.iscoroutinefunction(on_progress):
                                    await on_progress(downloaded, total)
                                else:
                                    on_progress(downloaded, total)

                    # 校验文件大小与头部
                    if os.path.exists(target_path) and os.path.getsize(target_path) > 100000:
                        with open(target_path, "rb") as f_check:
                            head = f_check.read(16)
                            if head.startswith(b"ID3") or head.startswith(b"fLaC") or b"\xff\xfb" in head or b"\xff\xfa" in head:
                                logger.info(f"[XiagebaProvider] 成功下载合法音频: {target_path} ({downloaded} 字节)")
                                return True

                    logger.warning(f"[XiagebaProvider] 下载的文件不合法或过小: {downloaded} 字节")
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    return False

        except Exception as e:
            logger.warning(f"[XiagebaProvider] 下载执行异常: {e}")
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            return False
