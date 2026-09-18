"""
可观测性与结构化日志体系 (基于架构审查第 12 项与第 50-51 条)
"""
import logging
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    """统一 Agent 追踪事件"""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str  # USER_MESSAGE, LLM_REQUEST, LLM_RESPONSE, TOOL_REQUEST, TOOL_RESULT, ERROR, LATENCY
    session_id: str = "default"
    request_id: str = ""
    duration_ms: Optional[float] = None
    success: bool = True
    error_code: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentLogger:
    """系统集中结构化日志管理器"""

    def __init__(self, log_file: str = "agent.log", level: int = logging.INFO):
        self.logger = logging.getLogger("AgentLogger")
        self.logger.setLevel(level)
        self.logger.handlers.clear()

        # 控制台输出格式
        console_handler = logging.StreamHandler(sys.stdout)
        console_fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [Agent] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_fmt)
        self.logger.addHandler(console_handler)

        # 文件输出
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            )
            file_handler.setFormatter(file_fmt)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not attach log file handler: {e}")

    def log_event(self, event: AgentEvent):
        """记录结构化事件并根据事件类型输出易读日志"""
        # 脱敏敏感字段 (如 api_key)
        safe_payload = {k: ("***" if "key" in k.lower() or "token" in k.lower() else v) for k, v in event.payload.items()}
        
        cost_str = f" ({event.duration_ms:.1f}ms)" if event.duration_ms is not None else ""
        status_str = "SUCCESS" if event.success else f"FAILED[{event.error_code}]"

        log_line = f"[{event.event_type}] [{status_str}]{cost_str} {safe_payload}"
        if event.success:
            self.logger.info(log_line)
        else:
            self.logger.error(log_line)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)


# 全局单例 logger
global_logger = AgentLogger()
