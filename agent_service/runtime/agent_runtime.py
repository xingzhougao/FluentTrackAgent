"""
AgentRuntime 核心分发与事件调度中心 (基于架构审查第 2 项 AgentRuntime 分层)
"""
import time
import uuid
import logging
from typing import Optional, Dict, Any

from config import ServiceConfig, global_config, LlmConfig
from llm.llm_manager import LlmManager
from utils.think_parser import StreamingThinkTracker, ThinkTagParser
from .agent_logger import global_logger, AgentEvent
from .context_manager import ContextManager
from .session_manager import SessionManager

logger = logging.getLogger("AgentLogger")


class AgentRuntime:
    """Agent 运行时调度引擎"""

    def __init__(self, config: Optional[ServiceConfig] = None):
        self.config = config or global_config
        self.session_manager = SessionManager(
            auth_token=self.config.token,
            dev_mode=self.config.dev_mode
        )
        self.context_manager = ContextManager(
            max_turns=self.config.max_history_turns
        )
        self.llm_manager = LlmManager(self.config.llm)

    async def handle_inbound_message(self, session_id: str, message_data: dict):
        """处理来自 WebSocket 客户端的所有上行消息"""
        msg_type = message_data.get("type", "")
        request_id = message_data.get("request_id", str(uuid.uuid4()))
        payload = message_data.get("payload", {})

        if msg_type == "ping":
            await self.session_manager.send_json(session_id, {
                "type": "pong",
                "request_id": request_id,
                "payload": {"time": time.time()}
            })
            return

        if msg_type == "clear_context":
            self.context_manager.clear_session(session_id)
            global_logger.log_event(AgentEvent(
                event_type="CLEAR_CONTEXT",
                session_id=session_id,
                request_id=request_id,
                payload={}
            ))
            await self.session_manager.send_json(session_id, {
                "type": "context_cleared",
                "request_id": request_id,
                "payload": {"status": "ok"}
            })
            return

        if msg_type == "update_llm_config":
            try:
                new_llm = LlmConfig(**payload)
                self.config.llm = new_llm
                self.llm_manager.update_config(new_llm)
                from config import save_config
                save_config(self.config)
                await self.session_manager.send_json(session_id, {
                    "type": "config_updated",
                    "request_id": request_id,
                    "payload": {"status": "ok"}
                })
            except Exception as e:
                logger.error(f"更新配置失败: {e}")
            return

        if msg_type == "user_message":
            user_text = payload.get("text", "").strip()
            if not user_text:
                return
            await self._process_user_message(session_id, request_id, user_text)
            return

        logger.warning(f"未知或暂未处理的消息类型: {msg_type}")

    async def _process_user_message(self, session_id: str, request_id: str, user_text: str):
        """核心处理：用户自然语言对话流式生成"""
        start_time = time.perf_counter()
        session_ctx = self.context_manager.get_session(session_id)
        session_ctx.add_user_message(user_text)

        global_logger.log_event(AgentEvent(
            event_type="USER_MESSAGE",
            session_id=session_id,
            request_id=request_id,
            payload={"text": user_text}
        ))

        # 状态更新通知客户端：思考中
        await self.session_manager.send_json(session_id, {
            "type": "status_update",
            "request_id": request_id,
            "payload": {"status": "thinking", "message": "正在深度思考..."}
        })

        provider = self.llm_manager.get_provider()
        tracker = StreamingThinkTracker()

        try:
            async for chunk in provider.chat_stream(
                messages=session_ctx.messages,
                temperature=self.config.llm.temperature
            ):
                think_delta, answer_delta = tracker.feed(chunk)

                # 推送思考过程增量
                if think_delta:
                    await self.session_manager.send_json(session_id, {
                        "type": "assistant_delta",
                        "request_id": request_id,
                        "payload": {"delta_type": "think", "text": think_delta}
                    })

                # 推送正式回答增量
                if answer_delta:
                    await self.session_manager.send_json(session_id, {
                        "type": "assistant_delta",
                        "request_id": request_id,
                        "payload": {"delta_type": "answer", "text": answer_delta}
                    })

            duration_ms = (time.perf_counter() - start_time) * 1000
            full_thinking = tracker.full_thinking
            full_answer = tracker.full_answer

            # 兜底：如果模型没有流式分离但在文本中输出了完整 <think>
            if not full_thinking and "<think>" in full_answer:
                parsed_think, parsed_ans = ThinkTagParser.extract_think_and_answer(full_answer)
                if parsed_think:
                    full_thinking = parsed_think
                    full_answer = parsed_ans

            # 存入上下文历史
            session_ctx.add_assistant_message(full_answer)

            # 发送流完成消息
            await self.session_manager.send_json(session_id, {
                "type": "assistant_message",
                "request_id": request_id,
                "payload": {
                    "content": full_answer,
                    "thinking_content": full_thinking,
                    "duration_ms": int(duration_ms),
                    "tools": []  # Step 2 为基础对话，Step 3 接入原子控制 Tool
                }
            })

            # 状态更新通知客户端：已就绪
            await self.session_manager.send_json(session_id, {
                "type": "status_update",
                "request_id": request_id,
                "payload": {"status": "ready", "message": "已就绪"}
            })

            global_logger.log_event(AgentEvent(
                event_type="LLM_RESPONSE",
                session_id=session_id,
                request_id=request_id,
                duration_ms=duration_ms,
                payload={
                    "answer_len": len(full_answer),
                    "has_thinking": bool(full_thinking)
                }
            ))

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"处理对话出错: {e}", exc_info=True)
            global_logger.log_event(AgentEvent(
                event_type="ERROR",
                session_id=session_id,
                request_id=request_id,
                duration_ms=duration_ms,
                success=False,
                error_code="LLM_EXECUTION_ERROR",
                payload={"error": str(e)}
            ))
            await self.session_manager.send_json(session_id, {
                "type": "error",
                "request_id": request_id,
                "payload": {"message": f"处理请求异常: {str(e)}"}
            })
            await self.session_manager.send_json(session_id, {
                "type": "status_update",
                "request_id": request_id,
                "payload": {"status": "ready", "message": "已就绪"}
            })
