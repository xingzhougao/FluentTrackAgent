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

    def handle_response(self, confirm_id: str, confirmed: bool) -> bool:
        """接收并分发 Qt 客户端传回的 confirmation_response"""
        future = self.pending_confirmations.get(confirm_id)
        if future and not future.done():
            future.set_result(confirmed)
            logger.info(f"[ConfirmationManager] 成功分发用户选择: confirm_id={confirm_id}, confirmed={confirmed}")
            return True
        logger.warning(f"[ConfirmationManager] 未找到待处理的确认 ID 或已过期: {confirm_id}")
        return False
