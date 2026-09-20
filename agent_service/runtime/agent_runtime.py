"""
AgentRuntime 核心分发与事件调度中心 (基于架构审查第 2 项 AgentRuntime 分层与第 3 项确定性工作流)
"""
import time
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any

from config import ServiceConfig, global_config, LlmConfig, save_config
from llm.llm_manager import LlmManager
from utils.think_parser import StreamingThinkTracker, ThinkTagParser
from .agent_logger import global_logger, AgentEvent
from .context_manager import ContextManager
from .session_manager import SessionManager
from .intent_router import IntentRouter
from workflows.player_command_workflow import PlayerCommandWorkflow

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

        # 全双工客户端原子工具调用等待映射表 (request_id -> asyncio.Future)
        self._pending_tool_requests: Dict[str, asyncio.Future] = {}
        # 确定性工作流实例
        self.player_workflow = PlayerCommandWorkflow(self)

    async def call_client_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
        timeout: float = 5.0
    ) -> dict:
        """
        通过同一 WebSocket 链路向 Qt 客户端发起原子工具调用请求，
        并异步等待客户端返回的 tool_result。
        """
        request_id = str(uuid.uuid4())
        tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_tool_requests[request_id] = future

        logger.info(f"[AgentRuntime] 下发 tool_request: {tool_name} (req_id={request_id})")

        sent = await self.session_manager.send_json(session_id, {
            "type": "tool_request",
            "request_id": request_id,
            "payload": {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments
            }
        })

        if not sent:
            self._pending_tool_requests.pop(request_id, None)
            return {"success": False, "error": "WebSocket 连接已中断，无法发送工具调用", "result": {}}

        try:
            result_payload = await asyncio.wait_for(future, timeout=timeout)
            return result_payload
        except asyncio.TimeoutError:
            logger.error(f"[AgentRuntime] 工具调用超时: {tool_name} (timeout={timeout}s)")
            return {"success": False, "error": f"调用工具 {tool_name} 响应超时", "result": {}}
        finally:
            self._pending_tool_requests.pop(request_id, None)

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
                save_config(self.config)
                await self.session_manager.send_json(session_id, {
                    "type": "config_updated",
                    "request_id": request_id,
                    "payload": {"status": "ok"}
                })
            except Exception as e:
                logger.error(f"更新配置失败: {e}")
            return

        if msg_type == "tool_result":
            # Qt 客户端回传原子工具执行结果，唤醒挂起的等待 Future
            logger.info(f"[AgentRuntime] 收到客户端 tool_result: {request_id}, success={payload.get('success')}")
            if request_id in self._pending_tool_requests:
                fut = self._pending_tool_requests[request_id]
                if not fut.done():
                    fut.set_result(payload)
            return

        if msg_type == "user_message":
            user_text = payload.get("text", "").strip()
            if not user_text:
                return
            await self._process_user_message(session_id, request_id, user_text)
            return

        logger.warning(f"未知或暂未处理的消息类型: {msg_type}")

    async def _process_user_message(self, session_id: str, request_id: str, user_text: str):
        """核心处理：意图路由、确定性工作流或自然语言流式生成"""
        start_time = time.perf_counter()
        session_ctx = self.context_manager.get_session(session_id)
        session_ctx.add_user_message(user_text)

        global_logger.log_event(AgentEvent(
            event_type="USER_MESSAGE",
            session_id=session_id,
            request_id=request_id,
            payload={"text": user_text}
        ))

        provider = self.llm_manager.get_provider()

        # Step 1: 意图识别 (双轨：快速规则 + LLM 降级)
        intent = await IntentRouter.route_intent(user_text, provider)

        # Step 2: 如果命中播放控制意图，由确定性 PlayerCommandWorkflow 闭环执行
        if intent.intent_type == "PLAYER_CONTROL":
            await self.session_manager.send_json(session_id, {
                "type": "status_update",
                "request_id": request_id,
                "payload": {"status": "thinking", "message": "正在执行控制指令..."}
            })

            wf_output = await self.player_workflow.execute(
                session_id=session_id,
                request_id=request_id,
                action=intent.action,
                params=intent.params
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            # 存入上下文历史
            session_ctx.add_assistant_message(wf_output.answer_text)

            # 发送流完成消息（附带 ToolCard 卡片列表）
            await self.session_manager.send_json(session_id, {
                "type": "assistant_message",
                "request_id": request_id,
                "payload": {
                    "content": wf_output.answer_text,
                    "thinking_content": "",
                    "duration_ms": int(duration_ms),
                    "tools": wf_output.tools
                }
            })

            # 状态更新通知客户端：已就绪
            await self.session_manager.send_json(session_id, {
                "type": "status_update",
                "request_id": request_id,
                "payload": {"status": "ready", "message": "已就绪"}
            })

            global_logger.log_event(AgentEvent(
                event_type="TOOL_EXECUTION",
                session_id=session_id,
                request_id=request_id,
                duration_ms=duration_ms,
                payload={
                    "action": intent.action,
                    "success": wf_output.success,
                    "tools_count": len(wf_output.tools)
                }
            ))
            return

        # Step 3: 普通自然语言对话（流式生成）
        await self.session_manager.send_json(session_id, {
            "type": "status_update",
            "request_id": request_id,
            "payload": {"status": "thinking", "message": "正在思考..."}
        })

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
                    "tools": []
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
