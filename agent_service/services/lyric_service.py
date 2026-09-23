"""
LyricService 高精度同步打点歌词 (.lrc) 检索、配对与规整服务
实现：
1. 真实打点优先（坚决杜绝匀速伪造打点）
2. 全球高精度开放歌词库检索 (LRCLIB，支持时长容差约束 <= 5.0 秒)
3. 酷狗公有引擎并发检索 (带全曲时长强校验，过滤铃声片段)
4. 下歌吧原生打点直通校验
5. 优雅纯净的“暂无同步歌词”占位保底机制
"""
import os
import re
import base64
import logging
import asyncio
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("AgentLogger")

# 尝试引入 curl_cffi 增强网络健壮性，若无则优雅降级到 httpx
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import httpx


class LyricService:
    """真实同步打点歌词服务"""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "close"
        }

    async def fetch_paired_lrc(
        self,
        title: str,
        artist: str = "",
        duration_sec: float = 0.0,
        preset_lrc: str = ""
    ) -> Tuple[str, str]:
        """
        根据歌名、歌手与真实音频时长，检索并配对真实时间戳 LRC 歌词。
        严格杜绝匀速假时间戳，确保与音频 100% 节奏对齐。
        返回: (lrc_content, source_name)
        """
        clean_title = re.sub(r'\(.*?\)|\[.*?]|（.*?）|【.*?】', '', title).strip() or title.strip()
        clean_artist = artist.strip()

        # 1. 若已有预置歌词且包含有效时间戳，直接规整返回
        if preset_lrc and self._has_valid_time_tags(preset_lrc):
            normalized = self._normalize_lrc(preset_lrc, clean_title, clean_artist, duration_sec)
            if normalized:
                return normalized, "preset"

        # 2. 优先检索全球高精度开放歌词引擎 (LRCLIB: 精确时长与词曲双向约束)
        lrclib_lrc = await self._fetch_from_lrclib(clean_title, clean_artist, duration_sec)
        if lrclib_lrc:
            normalized = self._normalize_lrc(lrclib_lrc, clean_title, clean_artist, duration_sec)
            if normalized:
                return normalized, "lrclib"

        # 3. 尝试调用酷狗公有打点歌词引擎 (严格过滤铃声，时长偏差 <= 5s)
        kugou_lrc = await self._fetch_from_kugou(clean_title, clean_artist, duration_sec)
        if kugou_lrc:
            normalized = self._normalize_lrc(kugou_lrc, clean_title, clean_artist, duration_sec)
            if normalized:
                return normalized, "kugou"

        # 4. 尝试从下歌吧获取原生打点歌词 (若下歌吧返回的歌词包含真实打点)
        xiageba_lrc = await self._fetch_from_xiageba_synced(clean_title, clean_artist)
        if xiageba_lrc:
            normalized = self._normalize_lrc(xiageba_lrc, clean_title, clean_artist, duration_sec)
            if normalized:
                return normalized, "xiageba"

        # 5. 优雅保底：宁缺毋滥，绝不捏造假时间戳，生成标准“暂无同步歌词”占位 LRC
        logger.info(f"[LyricService] 《{clean_title}》未检索到高精打点歌词，启用标准暂无歌词保底")
        fallback = self._generate_fallback_lrc(clean_title, clean_artist, duration_sec)
        return fallback, "placeholder"

    def _has_valid_time_tags(self, text: str) -> bool:
        """检查文本中是否包含真正的 LRC 打点标签，至少出现 2 次有效时间戳"""
        if not text:
            return False
        pattern = re.compile(r'\[\d{1,2}:\d{2}(?:\.\d{1,3})?\]')
        matches = pattern.findall(text)
        return len(matches) >= 2

    async def _fetch_from_lrclib(self, title: str, artist: str, duration_sec: float) -> Optional[str]:
        """
        调用 LRCLIB 高精度歌词库 (带时长精确校验)
        """
        loop = asyncio.get_running_loop()

        def _do_lrclib_request():
            # 1. 尝试精确 get
            try:
                params = {"track_name": title}
                if artist:
                    params["artist_name"] = artist
                if duration_sec > 30:
                    params["duration"] = int(duration_sec)

                if HAS_CURL_CFFI:
                    r = curl_requests.get("https://lrclib.net/api/get", params=params, impersonate="chrome120", timeout=5)
                else:
                    r = httpx.get("https://lrclib.net/api/get", params=params, headers=self.headers, timeout=5)

                if r.status_code == 200:
                    data = r.json()
                    synced = data.get("syncedLyrics")
                    if synced and self._has_valid_time_tags(synced):
                        logger.info(f"[LyricService] LRCLIB 精确命中《{title}》真实同步歌词")
                        return synced
            except Exception as e:
                logger.debug(f"[LyricService] LRCLIB get 跳过: {e}")

            # 2. 尝试模糊 search
            try:
                kw = f"{artist} {title}".strip() if artist else title
                if HAS_CURL_CFFI:
                    r_s = curl_requests.get("https://lrclib.net/api/search", params={"q": kw}, impersonate="chrome120", timeout=5)
                else:
                    r_s = httpx.get("https://lrclib.net/api/search", params={"q": kw}, headers=self.headers, timeout=5)

                if r_s.status_code == 200:
                    cands = r_s.json()
                    if isinstance(cands, list):
                        for c in cands:
                            synced = c.get("syncedLyrics")
                            if not synced or not self._has_valid_time_tags(synced):
                                continue
                            c_track = c.get("trackName", "").strip().lower()
                            t_lower = title.lower()
                            if t_lower not in c_track and c_track not in t_lower:
                                continue
                            # 歌曲时长误差严格控制在 5.0 秒以内
                            if duration_sec > 30:
                                c_dur = float(c.get("duration", 0))
                                if abs(c_dur - duration_sec) > 5.0:
                                    continue
                            logger.info(f"[LyricService] LRCLIB 搜索命中《{title}》同步打点歌词")
                            return synced
            except Exception as e:
                logger.debug(f"[LyricService] LRCLIB search 跳过: {e}")

            return None

        try:
            return await loop.run_in_executor(None, _do_lrclib_request)
        except Exception:
            return None

    async def _fetch_from_kugou(self, title: str, artist: str, duration_sec: float) -> Optional[str]:
        """从酷狗公有接口检索并下载打点歌词，严格匹配整曲时长与歌名"""
        kw = f"{artist} - {title}" if artist else title
        search_url = "http://lyrics.kugou.com/search"
        params = {
            "ver": 1,
            "man": "yes",
            "client": "pc",
            "keyword": kw,
            "hash": ""
        }

        loop = asyncio.get_running_loop()

        def _do_kugou_request():
            try:
                if HAS_CURL_CFFI:
                    resp = curl_requests.get(search_url, params=params, impersonate="chrome120", timeout=5)
                else:
                    resp = httpx.get(search_url, params=params, headers=self.headers, timeout=5)

                if resp.status_code != 200:
                    return None
                data = resp.json()
                cands = data.get("candidates", [])
                if not cands:
                    return None

                matched_cand = None
                t_lower = title.lower()
                a_lower = artist.lower() if artist else ""

                for c in cands:
                    c_song = str(c.get("song", "")).lower()
                    c_singer = str(c.get("singer", "")).lower()
                    c_dur_sec = float(c.get("duration", 0)) / 1000.0

                    # 1. 歌名必须对齐
                    if t_lower not in c_song and c_song not in t_lower:
                        continue
                    # 2. 若指定歌手，歌手必须包含
                    if a_lower and (a_lower not in c_singer and c_singer not in a_lower):
                        continue
                    # 3. 过滤片段、铃声等劣质资源
                    if any(k in c_song for k in ["片段", "铃声", "24秒", "降调", "慢摇", "串烧", "dj"]):
                        continue
                    # 4. 时长强校验：若已知真实时长，误差必须在 5 秒内；若未知时长，至少 > 90 秒
                    if duration_sec > 30:
                        if abs(c_dur_sec - duration_sec) > 5.0:
                            continue
                    elif c_dur_sec < 90:
                        continue

                    matched_cand = c
                    break

                if not matched_cand:
                    return None

                cid = matched_cand.get("id")
                key = matched_cand.get("accesskey")
                if not cid or not key:
                    return None

                dl_url = "http://lyrics.kugou.com/download"
                dl_params = {
                    "ver": 1,
                    "client": "pc",
                    "id": cid,
                    "accesskey": key,
                    "fmt": "lrc",
                    "charset": "utf8"
                }

                if HAS_CURL_CFFI:
                    dl_resp = curl_requests.get(dl_url, params=dl_params, impersonate="chrome120", timeout=5)
                else:
                    dl_resp = httpx.get(dl_url, params=dl_params, headers=self.headers, timeout=5)

                if dl_resp.status_code == 200:
                    b64_content = dl_resp.json().get("content", "")
                    if b64_content:
                        raw_bytes = base64.b64decode(b64_content)
                        raw_text = raw_bytes.decode("utf-8", errors="ignore")
                        if self._has_valid_time_tags(raw_text):
                            logger.info(f"[LyricService] 成功从酷狗命中《{title}》真实歌词 (行数={len(raw_text.splitlines())})")
                            return raw_text
            except Exception as e:
                logger.debug(f"[LyricService] 检索酷狗歌词异常: {e}")

            return None

        try:
            return await loop.run_in_executor(None, _do_kugou_request)
        except Exception:
            return None

    async def _fetch_from_xiageba_synced(self, title: str, artist: str) -> Optional[str]:
        """从下歌吧 API 获取真实打点歌词（仅当其包含合法时间戳时才采纳）"""
        kw = f"{artist} {title}".strip() if artist else title
        loop = asyncio.get_running_loop()

        def _do_xiageba():
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://xiageba.liumingye.cn/"
                }
                search_url = "https://xiageba.liumingye.cn/api/music/search"
                if HAS_CURL_CFFI:
                    resp = curl_requests.get(search_url, params={"q": kw, "page": 1, "pageSize": 3}, headers=headers, impersonate="chrome120", timeout=5)
                else:
                    resp = httpx.get(search_url, params={"q": kw, "page": 1, "pageSize": 3}, headers=headers, timeout=5)

                if resp.status_code == 200:
                    items = resp.json().get("data", [])
                    if items:
                        item_id = items[0].get("id")
                        if item_id:
                            det_url = f"https://xiageba.liumingye.cn/api/music/{item_id}"
                            if HAS_CURL_CFFI:
                                det_resp = curl_requests.get(det_url, headers=headers, impersonate="chrome120", timeout=5)
                            else:
                                det_resp = httpx.get(det_url, headers=headers, timeout=5)
                            if det_resp.status_code == 200:
                                lyrics = det_resp.json().get("lyrics", "")
                                # 核心原则：只有包含真实打点时间戳才采纳，绝不使用纯文本伪造打点
                                if lyrics and self._has_valid_time_tags(lyrics):
                                    logger.info(f"[LyricService] 从下歌吧成功获取《{title}》原生同步打点歌词")
                                    return lyrics
            except Exception as e:
                logger.debug(f"[LyricService] 下歌吧歌词获取跳过: {e}")
            return None

        try:
            return await loop.run_in_executor(None, _do_xiageba)
        except Exception:
            return None

    def _normalize_lrc(self, raw_lrc: str, title: str, artist: str, duration_sec: float) -> str:
        """规整已带打点的 LRC 歌词，补齐头部元数据与尾部播放结束标记"""
        lines = [line.strip() for line in raw_lrc.splitlines() if line.strip()]
        cleaned_lines = []
        has_ti = False
        has_ar = False
        max_time_sec = 0.0

        time_tag_pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]')

        for line in lines:
            if line.startswith("[ti:"):
                has_ti = True
            elif line.startswith("[ar:"):
                has_ar = True
            elif line.startswith("[id:") or line.startswith("[offset:"):
                continue

            m = time_tag_pattern.search(line)
            if m:
                mm = int(m.group(1))
                ss = int(m.group(2))
                frac = m.group(3) or "0"
                ms = int(frac.ljust(3, "0")[:3])
                t_sec = mm * 60 + ss + ms / 1000.0
                if t_sec > max_time_sec:
                    max_time_sec = t_sec

            cleaned_lines.append(line)

        header_lines = []
        if not has_ti and title:
            header_lines.append(f"[ti:{title}]")
        if not has_ar and artist:
            header_lines.append(f"[ar:{artist}]")

        result = header_lines + cleaned_lines

        final_dur = max(duration_sec, max_time_sec + 3.0)
        if final_dur > max_time_sec + 2.0 and final_dur > 30:
            mm = int(final_dur // 60)
            ss = int(final_dur % 60)
            result.append(f"[{mm:02d}:{ss:02d}.00]（播放完毕）")

        return "\n".join(result)

    def _generate_fallback_lrc(self, title: str, artist: str, duration_sec: float) -> str:
        """
        优雅的暂无同步歌词保底标准结构。
        宁缺毋滥：绝不拼接其他曲目歌词，绝不伪造虚假均分打点。
        """
        total_dur = duration_sec if duration_sec > 30 else 240.0
        mm = int(total_dur // 60)
        ss = int(total_dur % 60)
        art_display = f" - {artist}" if artist and artist != "未知歌手" else ""
        return "\n".join([
            f"[ti:{title}]",
            f"[ar:{artist}]" if artist else f"[ar:未知歌手]",
            f"[00:00.00]《{title}》{art_display}",
            "[00:02.00]（暂无同步歌词，请欣赏音乐）",
            f"[{mm:02d}:{ss:02d}.00]（播放完毕）"
        ])


# 全局单例
lyric_service = LyricService()
