"""
WebSocket 连接与会话生命周期管理器 (基于架构审查第 10 项：Token 鉴权)
"""
import logging
from typing import Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger("AgentLogger")


class SessionManager:
    """管理与 Qt 客户端的单个全双工 WebSocket 连接与鉴权"""

    def __init__(self, auth_token: str = "", dev_mode: bool = True):
        self.auth_token = auth_token
        self.dev_mode = dev_mode
        self._active_connections: Dict[str, WebSocket] = {}

    def verify_token(self, token: Optional[str]) -> bool:
        """鉴权校验：开发模式下允许免 token 或匹配 token"""
        if self.dev_mode:
            return True
        if not self.auth_token:
            return True
        return token == self.auth_token

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._active_connections[session_id] = websocket
        logger.info(f"客户端已接入长连接: session_id={session_id}")

    def disconnect(self, session_id: str):
        if session_id in self._active_connections:
            del self._active_connections[session_id]
            logger.info(f"客户端已断开长连接: session_id={session_id}")

    def get_connection(self, session_id: str) -> Optional[WebSocket]:
        return self._active_connections.get(session_id)

    async def send_json(self, session_id: str, data: dict) -> bool:
        ws = self.get_connection(session_id)
        if ws:
            try:
                await ws.send_json(data)
                return True
            except Exception as e:
                logger.error(f"WebSocket 发送消息失败: {e}")
                self.disconnect(session_id)
        return False
