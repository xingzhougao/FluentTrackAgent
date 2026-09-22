"""
ConfirmationManager 异步人工确认管理器 (Step 5 Issue 11 定型标准)
为大文件/批量下载及写入等敏感操作提供安全拦截与 Human Confirmation 交互机制。
"""
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("AgentLogger")


class ConfirmationManager:
    """确认管理器"""

    def __init__(self, session_manager=None):
        self.session_manager = session_manager
        self.pending_confirmations: Dict[str, asyncio.Future] = {}

    def set_session_manager(self, session_manager):
        self.session_manager = session_manager

    async def request_confirmation(
        self,
        session_id: str,
        title: str,
        message: str,
        details: str = "",
        timeout: float = 60.0
    ) -> bool:
        """
        向客户端发起人工二次确认交互并异步挂起等待。
        返回: True (用户点击确认) / False (用户点击取消或超时)
        """
        if not self.session_manager:
            logger.warning("[ConfirmationManager] session_manager 未初始化，默认直接通过")
            return True

        confirm_id = f"conf_{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_confirmations[confirm_id] = future

        msg_payload = {
            "type": "confirmation_required",
            "confirm_id": confirm_id,
            "payload": {
                "title": title,
                "message": message,
                "details": details
            }
        }

        logger.info(f"[ConfirmationManager] 发起确认请求 confirm_id={confirm_id}, title='{title}'")
        await self.session_manager.send_json(session_id, msg_payload)

        try:
            confirmed = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"[ConfirmationManager] 收到确认响应: confirm_id={confirm_id}, confirmed={confirmed}")
            return bool(confirmed)
        except asyncio.TimeoutError:
            logger.warning(f"[ConfirmationManager] 确认请求超时 (timeout={timeout}s): confirm_id={confirm_id}")
            return False
        finally:
            self.pending_confirmations.pop(confirm_id, None)

    async def request_candidate_selection(
        self,
        session_id: str,
        query: str,
        artist: str,
        candidates: list,
        timeout: float = 120.0
    ) -> Optional[str]:
        """
        向客户端发起候选音源版本多选弹窗，并异步挂起等待用户选择。
        返回: 选中的 candidate_id，若用户点击取消或超时返回 None
        """
        if not candidates:
            return None

        # 若无活跃的客户端 WebSocket 长连接 (如离线单元测试)，自动选用首选项
        has_active = False
        if self.session_manager:
            if hasattr(self.session_manager, "has_session"):
                has_active = self.session_manager.has_session(session_id)
            elif hasattr(self.session_manager, "get_connection"):
                has_active = bool(self.session_manager.get_connection(session_id))
            elif hasattr(self.session_manager, "_active_connections"):
                has_active = session_id in getattr(self.session_manager, "_active_connections", {})

        if not has_active:
            logger.info(f"[ConfirmationManager] 无活跃客户端连接，自动选择首选项: {candidates[0].title} ({candidates[0].id})")
            return candidates[0].id

        confirm_id = f"sel_{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_confirmations[confirm_id] = future

        candidates_data = []
        for c in candidates:
            extra = getattr(c, "extra", {}) or {}
            v_tag = extra.get("version_tag", "原版音频")
            is_netdisk = bool(extra.get("is_netdisk", False))

            if c.provider == "soulseek_p2p":
                source_label = "Soulseek P2P"
            elif c.provider == "xiageba":
                source_label = "下歌吧 (刘明野)"
            else:
                source_label = "开放网络音源"

            sz_bytes = c.size_bytes or 0
            size_str = f"{sz_bytes / (1024 * 1024):.1f} MB" if sz_bytes > 0 else (
                "网盘转存" if is_netdisk else "320k"
            )

            candidates_data.append({
                "id": c.id,
                "title": c.title,
                "artist": c.artist,
                "album": c.album,
                "provider": c.provider,
                "source_label": source_label,
                "format": c.format.upper() if c.format else "MP3",
                "bitrate": f"{c.bitrate}k" if c.bitrate else "320k",
                "size_str": size_str,
                "is_netdisk": is_netdisk,
                "version_tag": v_tag,
                "url": c.url or ""
            })

        msg_payload = {
            "type": "candidate_selection_required",
            "confirm_id": confirm_id,
            "payload": {
                "title": "选择要下载的音乐版本",
                "query": query,
                "artist": artist,
                "candidates": candidates_data
            }
        }

        logger.info(f"[ConfirmationManager] 下发多选弹窗请求 confirm_id={confirm_id}, 共 {len(candidates_data)} 个候选")
        await self.session_manager.send_json(session_id, msg_payload)

        try:
            selected_id = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"[ConfirmationManager] 收到用户版本选择: confirm_id={confirm_id}, selected_id={selected_id}")
            return selected_id
        except asyncio.TimeoutError:
            logger.warning(f"[ConfirmationManager] 用户选歌超时 (timeout={timeout}s): confirm_id={confirm_id}")
            return None
        finally:
            self.pending_confirmations.pop(confirm_id, None)

    def handle_response(self, confirm_id: str, confirmed: bool) -> bool:
        """接收并分发 Qt 客户端传回的 confirmation_response"""
        future = self.pending_confirmations.get(confirm_id)
        if future and not future.done():
            future.set_result(confirmed)
            logger.info(f"[ConfirmationManager] 成功分发用户选择: confirm_id={confirm_id}, confirmed={confirmed}")
            return True
        logger.warning(f"[ConfirmationManager] 未找到待处理的确认 ID 或已过期: {confirm_id}")
        return False

    def handle_candidate_selection_response(self, confirm_id: str, selected_id: Optional[str], cancelled: bool = False) -> bool:
        """接收并分发 Qt 客户端传回的 candidate_selection_response"""
        future = self.pending_confirmations.get(confirm_id)
        if future and not future.done():
            future.set_result(None if cancelled else selected_id)
            logger.info(f"[ConfirmationManager] 成功分发选歌响应: confirm_id={confirm_id}, selected_id={selected_id}, cancelled={cancelled}")
            return True
        logger.warning(f"[ConfirmationManager] 未找到待处理的选歌确认 ID 或已过期: {confirm_id}")
        return False
