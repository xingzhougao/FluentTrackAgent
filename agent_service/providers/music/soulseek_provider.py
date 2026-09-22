"""
SoulseekMusicProvider (slskd P2P 独立外部集成 Provider)
基于 Step 5 架构与 Issue 08 定型标准：
将 slskd 定义为可选独立的外部守护进程，通过 HTTP API 通信。
支持繁简多轮检索、无损 FLAC 优先匹配、直通主曲库下载与精确状态追踪。
若未运行或不可达，优雅静默降级，不阻断主流程。
"""
import os
import uuid
import shutil
import asyncio
import logging
import httpx
from typing import List, Optional, Dict, Any, Callable
from .base import BaseMusicProvider, ProviderCapabilities, TrackCandidate

logger = logging.getLogger("AgentLogger")

# 音乐常用简繁汉字转换映射表（覆盖港台及海外无损 P2P 曲库常见字）
_SIMP_TO_TRAD = {
    '爱': '愛', '伦': '倫', '没': '沒', '国': '國', '风': '風', '乐': '樂', '华': '華',
    '杰': '傑', '听': '聽', '欢': '歡', '语': '語', '恋': '戀', '梦': '夢', '离': '離',
    '开': '開', '关': '關', '点': '點', '会': '會', '边': '邊', '头': '頭', '间': '間',
    '门': '門', '见': '見', '经': '經', '动': '動', '现': '現', '单': '單', '选': '選',
    '变': '變', '阳': '陽', '怀': '懷', '伤': '傷', '忆': '憶', '独': '獨', '寻': '尋',
    '尽': '盡', '泪': '淚', '觉': '覺', '编': '編', '飞': '飛', '归': '歸', '传': '傳',
    '声': '聲', '尘': '塵', '盏': '盞', '栈': '棧', '难': '難', '岁': '歲', '浅': '淺',
    '乱': '亂', '绝': '絕', '续': '續', '终': '終', '绿': '綠', '蓝': '藍', '红': '紅',
    '银': '銀', '钱': '錢', '铁': '鐵', '钟': '鐘', '镜': '鏡', '雾': '霧', '灵': '靈',
    '鸟': '鳥', '凤': '鳳', '鱼': '魚', '麦': '麥', '叶': '葉', '艺': '藝', '节': '節',
    '亲': '親', '誉': '譽', '誓': '誓', '转': '轉', '轮': '輪', '轻': '輕', '载': '載',
    '辉': '輝', '辑': '輯', '帅': '帥', '尔': '爾', '讯': '訊', '陈': '陳', '张': '張',
    '刘': '劉', '杨': '楊', '黄': '黃', '孙': '孫', '赵': '趙', '吴': '吳', '郑': '鄭',
    '王': '王', '林': '林', '李': '李', '晴': '晴', '天': '天', '春': '春', '秋': '秋'
}

def to_traditional(text: str) -> str:
    return "".join(_SIMP_TO_TRAD.get(ch, ch) for ch in text)


class SoulseekMusicProvider(BaseMusicProvider):
    """Soulseek / slskd P2P 发现与下载 Provider"""

    def __init__(
        self,
        api_base_url: str = "http://127.0.0.1:5030/api/v0",
        api_key: str = "",
        timeout: float = 6.0
    ):
        super().__init__(
            name="soulseek_p2p",
            capabilities=ProviderCapabilities(
                can_search=True,
                can_resolve=True,
                can_stream=False,
                can_download=True
            )
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._is_available: Optional[bool] = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def check_availability(self) -> bool:
        """探针检测 slskd 独立进程是否就绪，若未启动则通过伴生守护进程自动拉起"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(
                    f"{self.api_base_url}/application",
                    headers=self._get_headers()
                )
                if resp.status_code == 200:
                    self._is_available = True
                    return True
        except Exception:
            pass

        # 若本地未在运行，尝试静默自启伴生服务
        try:
            from services.slskd_daemon import slskd_daemon
            started = await slskd_daemon.start()
            if started:
                self._is_available = True
                return True
        except Exception as e:
            logger.debug(f"[SoulseekProvider] 自动拉起伴生守护服务失败: {e}")

        self._is_available = False
        return False

    async def ensure_logged_in(self, max_wait: float = 12.0) -> bool:
        """确保 slskd 已成功连接并完成 Soulseek 登录握手"""
        elapsed = 0.0
        while elapsed < max_wait:
            try:
                async with httpx.AsyncClient(timeout=1.5) as client:
                    resp = await client.get(f"{self.api_base_url}/application", headers=self._get_headers())
                    if resp.status_code == 200:
                        server = resp.json().get("server", {})
                        if server.get("isLoggedIn") and not server.get("isLoggingIn"):
                            return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
            elapsed += 0.5
        return False

    async def search(self, query: str, artist: str = "", limit: int = 5) -> List[TrackCandidate]:
        """向 slskd 提交 P2P 检索并轮询获取优质结果 (支持简繁优化与多 Peer 汇聚)"""
        if not await self.check_availability():
            logger.debug("[SoulseekProvider] slskd 未就绪，跳过 P2P 检索")
            return []

        # 检查是否已完成中央服务器登录
        is_ready = await self.ensure_logged_in(max_wait=6.0)
        if not is_ready:
            logger.info("[SoulseekProvider] P2P 服务器处于初始连接或重连中，本次检索优雅跳过")
            return []

        clean_q = query.strip()
        clean_art = artist.strip()
        if not clean_q and not clean_art:
            return []

        # 确定主检索关键词：海外及港台无损 P2P 曲库几乎全部使用繁体字，优先使用繁体检索
        trad_q = to_traditional(clean_q)
        primary_term = trad_q if trad_q != clean_q else clean_q
        fallback_term = clean_q if trad_q != clean_q else ""

        results: List[TrackCandidate] = []
        seen_filenames = set()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                terms_to_try = [primary_term]
                for term in terms_to_try:
                    post_resp = await client.post(
                        f"{self.api_base_url}/searches",
                        json={"searchText": term},
                        headers=self._get_headers()
                    )

                    retry_count = 0
                    while post_resp.status_code == 409 and retry_count < 3:
                        retry_count += 1
                        await asyncio.sleep(1.2)
                        post_resp = await client.post(
                            f"{self.api_base_url}/searches",
                            json={"searchText": term},
                            headers=self._get_headers()
                        )

                    if post_resp.status_code not in [200, 201]:
                        continue

                    search_data = post_resp.json()
                    search_id = search_data.get("id") if isinstance(search_data, dict) else str(search_data).strip('"')
                    if not search_id:
                        continue

                    # slskd 的 /responses 端点只在搜索完成 (Completed) 后才返回数据，
                    # 因此先轮询 /searches/{id} 的 state 与 responseCount，
                    # 确认搜索完成后再一次性拉取 /responses 完整结果。
                    responses = []
                    max_poll_secs = 24.0
                    poll_step = 0.8
                    elapsed_poll = 0.0
                    search_has_results = False

                    while elapsed_poll < max_poll_secs:
                        await asyncio.sleep(poll_step)
                        elapsed_poll += poll_step
                        try:
                            status_resp = await client.get(
                                f"{self.api_base_url}/searches/{search_id}",
                                headers=self._get_headers()
                            )
                            if status_resp.status_code != 200:
                                continue
                            s_data = status_resp.json()
                            state = s_data.get("state", "")
                            resp_count = s_data.get("responseCount", 0)
                            file_count = s_data.get("fileCount", 0)

                            if resp_count > 0:
                                search_has_results = True

                            # 搜索已完成（含 TimedOut / Errored 等均算结束）
                            if "Completed" in state:
                                break
                        except Exception:
                            continue

                    # 搜索完成后一次性拉取 /responses
                    if search_has_results:
                        try:
                            resp_list = await client.get(
                                f"{self.api_base_url}/searches/{search_id}/responses",
                                headers=self._get_headers()
                            )
                            if resp_list.status_code == 200:
                                data = resp_list.json()
                                if isinstance(data, list):
                                    responses = data
                                elif isinstance(data, dict) and data.get("responses"):
                                    responses = data.get("responses")
                        except Exception:
                            pass

                    # 汇聚所有匹配的候选文件，并记录 Peer 列表
                    peer_candidates: List[Dict[str, Any]] = []
                    for resp in responses:
                        username = resp.get("username", "Soulseek User")
                        files = resp.get("files", [])
                        for f in files:
                            filename = f.get("filename", "")
                            ext = os.path.splitext(filename)[1].lower()
                            if ext not in [".mp3", ".flac", ".m4a", ".wav"]:
                                continue

                            # 验证文件名是否包含目标关键词 (简繁任一包含均匹配)
                            fn_lower = filename.lower()
                            q_simp_l = clean_q.lower()
                            q_trad_l = to_traditional(clean_q).lower()
                            if clean_q and (q_simp_l not in fn_lower and q_trad_l not in fn_lower):
                                continue

                            size = f.get("size", 0)
                            bitrate = f.get("bitRate", 320)
                            length_sec = f.get("length", 240)
                            peer_candidates.append({
                                "username": username,
                                "remote_filename": filename,
                                "size": size,
                                "bitrate": bitrate or (960 if ext in [".flac", ".wav"] else 320),
                                "ext": ext,
                                "format": "flac" if ext == ".flac" else ("wav" if ext == ".wav" else "mp3"),
                                "length": length_sec
                            })

                    # 按品质排序：无损 FLAC 优先，码率高优先
                    peer_candidates.sort(key=lambda p: (p["ext"] in [".flac", ".wav"], p["bitrate"], p["size"]), reverse=True)

                    for p in peer_candidates:
                        fn = p["remote_filename"]
                        if fn in seen_filenames:
                            continue
                        seen_filenames.add(fn)

                        fn_base = os.path.basename(fn)
                        fn_lower = fn_base.lower()

                        # 识别版本特征标签与是否属于翻唱/DJ混音
                        is_remix = any(k in fn_lower for k in ["remix", "rmx", "electro", "manyao", "慢摇", "串烧", "dj", "club mix", "热血版"])
                        is_cover = any(k in fn_lower for k in ["cover", "翻唱", "翻自", "原唱：", "原唱:"])
                        is_inst = any(k in fn_lower for k in ["伴奏", "inst", "instrumental", "karaoke"])
                        is_live = any(k in fn_lower for k in ["live", "现场版", "演唱会"])

                        if is_remix:
                            version_tag = "DJ混音"
                        elif is_cover:
                            version_tag = "翻唱版"
                        elif is_inst:
                            version_tag = "伴奏"
                        elif is_live:
                            version_tag = "现场版"
                        elif ext in [".flac", ".wav"]:
                            version_tag = "原版无损"
                        else:
                            version_tag = "原版音频"

                        # 真实歌手与标题提取 (避免翻唱者或串烧制作者被强行标记为目标歌手原唱)
                        clean_title = clean_q or os.path.splitext(fn_base)[0]
                        clean_artist_str = clean_art

                        # 检查目标歌手是否真实出现在路径或文件名中
                        art_in_file = False
                        if clean_art:
                            art_simp = clean_art.lower()
                            art_trad = to_traditional(clean_art).lower()
                            if art_simp in fn_lower or art_trad in fn_lower or art_simp in fn.lower():
                                art_in_file = True

                        if not art_in_file and clean_art:
                            # 文件名中并非目标歌手 (例如: 刘大壮 - 一吻天荒)
                            # 尝试解析真实歌手
                            base_no_ext = os.path.splitext(fn_base)[0]
                            if " - " in base_no_ext:
                                parts = base_no_ext.split(" - ", 1)
                                parsed_artist = re.sub(r'^\d+[\s\-_]*', '', parts[0]).strip()
                                clean_artist_str = parsed_artist or clean_art
                            else:
                                clean_artist_str = f"翻唱/未知歌手"

                        # 评分机制：原版无损最高，翻唱与慢摇降权
                        if is_remix:
                            conf = 0.50
                        elif is_cover or (not art_in_file and clean_art):
                            conf = 0.60
                        elif ext in [".flac", ".wav"]:
                            conf = 0.98
                        else:
                            conf = 0.92

                        results.append(TrackCandidate(
                            id=f"slsk_{uuid.uuid4().hex[:8]}",
                            title=clean_title,
                            artist=clean_artist_str,
                            album="Soulseek P2P 共享曲库",
                            duration=p["length"],
                            bitrate=p["bitrate"],
                            format=p["format"],
                            size_bytes=p["size"],
                            url=fn,
                            provider=self.name,
                            source_type="p2p",
                            confidence=min(0.99, conf),
                            capabilities=self.capabilities.to_list(),
                            extra={
                                "username": p["username"],
                                "remote_filename": fn,
                                "size": p["size"],
                                "version_tag": version_tag,
                                "is_remix": is_remix,
                                "is_cover": is_cover,
                                "peers": peer_candidates  # 附带所有 Peer 列表供自动容灾切换
                            }
                        ))
                        if len(results) >= limit:
                            break

                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.debug(f"[SoulseekProvider] P2P 检索异常: {e}")

        # 优先保留高保真无损与高比特率
        results.sort(key=lambda c: (c.confidence, c.bitrate), reverse=True)
        return results[:limit]

    async def start_download(self, username: str, remote_filename: str, size: int) -> Optional[str]:
        """向 slskd 提交排队下载请求，返回 transfer_id (若成功)"""
        # 确保已登录中央服务器
        await self.ensure_logged_in(max_wait=8.0)

        # 保持远程 Peer 返回的原生文件路径，严禁人为前置反斜杠避免触发 File not shared
        norm_filename = remote_filename

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.api_base_url}/transfers/downloads/{username}"
                payload = [{"filename": norm_filename, "size": size}]
                resp = await client.post(url, json=payload, headers=self._get_headers())
                if resp.status_code in [200, 201, 202]:
                    data = resp.json()
                    enqueued = data.get("enqueued", [])
                    if enqueued:
                        return enqueued[0].get("id")
                    return "ok"
        except Exception as e:
            logger.warning(f"[SoulseekProvider] 提交下载任务报错: {e}")
        return None

    async def download_track(
        self,
        candidate: TrackCandidate,
        target_path: str,
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        负责调度 slskd 完成 P2P 传输并支持多 Peer 自动容灾切换
        """
        if not await self.check_availability():
            logger.warning("[SoulseekProvider] slskd 服务不可用，无法执行 P2P 下载")
            return False

        extra = candidate.extra or {}
        main_user = extra.get("username")
        main_file = extra.get("remote_filename") or candidate.url
        main_size = extra.get("size") or candidate.size_bytes or 0

        # 构建 Peer 候选尝试序列
        peers_to_try = []
        if main_user and main_file:
            peers_to_try.append({"username": main_user, "remote_filename": main_file, "size": main_size})

        for ap in extra.get("peers", []):
            u = ap.get("username")
            f = ap.get("remote_filename")
            s = ap.get("size", 0)
            if u and f and not any(p["username"] == u and p["remote_filename"] == f for p in peers_to_try):
                peers_to_try.append({"username": u, "remote_filename": f, "size": s})

        # 采用并发多 Peer 竞速下载策略：
        # 同时向排名前 3 的有效 Peer 提交排队下载请求，以最先开始传输并完成的 Peer 为准，
        # 避免因单一 Peer 排队 (Queued, Remotely) 或内部拒绝而导致整体等待超时。
        active_transfers = []
        batch_size = min(3, len(peers_to_try))
        for p_idx in range(batch_size):
            peer = peers_to_try[p_idx]
            u = peer["username"]
            rf = peer["remote_filename"]
            sz = peer["size"]
            tb = os.path.basename(rf.replace("\\", "/"))
            logger.info(f"[SoulseekProvider] 并发提交 Peer [{p_idx+1}/{len(peers_to_try)}]: 用户={u}, 文件={rf}")
            tid = await self.start_download(u, rf, sz)
            if tid:
                active_transfers.append({
                    "username": u,
                    "remote_filename": rf,
                    "size": sz,
                    "target_base": tb,
                    "transfer_id": tid
                })

        if not active_transfers:
            logger.warning("[SoulseekProvider] 所有候选 Peer 排队入队均未成功")
            return False

        poll_interval = 0.8
        max_wait = 60.0
        elapsed = 0.0
        best_progress_bytes = 0

        async with httpx.AsyncClient(timeout=4.0) as client:
            while elapsed < max_wait and active_transfers:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                try:
                    resp = await client.get(
                        f"{self.api_base_url}/transfers/downloads",
                        headers=self._get_headers()
                    )
                    if resp.status_code != 200:
                        continue
                    transfers = resp.json()

                    winner = None
                    failed_users = set()

                    for at in active_transfers:
                        u = at["username"]
                        tb = at["target_base"]
                        tid = at["transfer_id"]
                        sz = at["size"]
                        fi = self._find_transfer_file(transfers, u, tb, tid if tid != "ok" else None)
                        if not fi:
                            continue

                        state = str(fi.get("state", ""))
                        bytes_done = fi.get("bytesTransferred", 0)
                        total_bytes = fi.get("size", sz) or sz

                        if bytes_done > best_progress_bytes:
                            best_progress_bytes = bytes_done
                            if on_progress and total_bytes > 0:
                                import inspect
                                if inspect.iscoroutinefunction(on_progress):
                                    await on_progress(bytes_done, total_bytes)
                                else:
                                    on_progress(bytes_done, total_bytes)

                        # 成功判定：Completed 且无报错异常，或字节已传输完毕
                        is_success_state = "Completed" in state and not any(
                            err in state for err in ["Errored", "Rejected", "Cancelled", "TimedOut", "Aborted"]
                        )
                        is_fully_transferred = total_bytes > 100000 and bytes_done >= total_bytes

                        if is_success_state or is_fully_transferred:
                            winner = at
                            break

                        if any(err in state for err in ["Errored", "Cancelled", "TimedOut", "Rejected", "Aborted"]):
                            failed_users.add(u)

                    if winner:
                        logger.info(f"[SoulseekProvider] Peer [{winner['username']}] P2P 传输成功完成: {winner['target_base']}")
                        completed_src = await self._locate_slskd_completed_file(winner["target_base"])
                        if completed_src and os.path.exists(completed_src) and os.path.getsize(completed_src) > 100000:
                            if os.path.abspath(completed_src) != os.path.abspath(target_path):
                                shutil.copy2(completed_src, target_path)
                            logger.info(f"[SoulseekProvider] P2P 完整文件已存入目标路径: {target_path} ({os.path.getsize(target_path)} 字节)")
                            # 取消其他竞争 Peer，释放网络资源
                            for other in active_transfers:
                                if other["username"] != winner["username"]:
                                    try:
                                        await client.delete(
                                            f"{self.api_base_url}/transfers/downloads/{other['username']}/{other['transfer_id']}",
                                            headers=self._get_headers()
                                        )
                                    except Exception:
                                        pass
                            return True

                    # 清理已失败的 Peer，并尝试补位剩余 Peer
                    if failed_users:
                        active_transfers = [at for at in active_transfers if at["username"] not in failed_users]
                        already_tried = {p["username"] for p in active_transfers} | failed_users
                        for peer in peers_to_try:
                            if peer["username"] not in already_tried and len(active_transfers) < 3:
                                u = peer["username"]
                                rf = peer["remote_filename"]
                                sz = peer["size"]
                                tb = os.path.basename(rf.replace("\\", "/"))
                                tid = await self.start_download(u, rf, sz)
                                if tid:
                                    active_transfers.append({
                                        "username": u,
                                        "remote_filename": rf,
                                        "size": sz,
                                        "target_base": tb,
                                        "transfer_id": tid
                                    })
                                    already_tried.add(u)

                except Exception as e:
                    logger.debug(f"[SoulseekProvider] 轮询传输状态异常: {e}")

        # 超时后最后兜底检查一次本地磁盘是否已有已完成文件
        for peer in peers_to_try:
            tb = os.path.basename(peer["remote_filename"].replace("\\", "/"))
            completed_src = await self._locate_slskd_completed_file(tb)
            if completed_src and os.path.exists(completed_src) and os.path.getsize(completed_src) > 100000:
                if os.path.abspath(completed_src) != os.path.abspath(target_path):
                    shutil.copy2(completed_src, target_path)
                logger.info(f"[SoulseekProvider] 兜底检索成功定位已完成音频文件: {target_path}")
                return True

        return False

    def _find_transfer_file(
        self,
        transfers: List[Dict[str, Any]],
        target_user: str,
        target_base: str,
        target_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        candidate_files = []
        for t in transfers:
            if t.get("username") == target_user:
                for d in t.get("directories", []):
                    for f in d.get("files", []):
                        if target_id and f.get("id") == target_id:
                            return f
                        fn = f.get("filename", "").replace("\\", "/")
                        if target_base == os.path.basename(fn) or target_base in fn:
                            candidate_files.append(f)
        if candidate_files:
            # 优先返回处于活跃传输状态或成功状态的条目，避免命中历史报错或拒绝记录
            candidate_files.sort(key=lambda item: (
                2 if "Completed" in str(item.get("state", "")) and not any(k in str(item.get("state", "")) for k in ["Errored", "Rejected", "Cancelled"]) else
                (1 if any(s in str(item.get("state", "")) for s in ["InProgress", "Requested", "Queued", "Running", "Initializing"]) else 0)
            ), reverse=True)
            return candidate_files[0]
        return None

    async def _get_slskd_download_dir(self) -> Optional[str]:
        """动态向 slskd 查询当前配置的下载完成主目录"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.api_base_url}/options", headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    dirs = data.get("directories", {})
                    return dirs.get("downloads")
        except Exception:
            pass
        return None

    async def _locate_slskd_completed_file(self, filename: str) -> Optional[str]:
        """从 slskd 配置目录及常见路径寻找已下载完成的音频文件 (排除临时 incomplete 目录)"""
        candidate_dirs = []
        configured_dir = await self._get_slskd_download_dir()
        if configured_dir:
            candidate_dirs.append(configured_dir)

        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        candidate_dirs.append(os.path.join(proj_root, "qml", "music_resource", "loadmusic_by_default"))
        candidate_dirs.append(os.path.join(proj_root, "downloaded_songs"))

        for d in candidate_dirs:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d):
                    if "incomplete" in root.lower():
                        continue
                    for fn in files:
                        if filename == fn or filename in fn:
                            return os.path.join(root, fn)
        return None

    async def resolve_download_url(self, candidate: TrackCandidate) -> Optional[str]:
        """解析 P2P 传输下载标识"""
        return candidate.url or f"{self.api_base_url}/transfers/downloads"
