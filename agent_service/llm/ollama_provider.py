"""
本地 Ollama 原生协议 Provider
"""
import json
import logging
from typing import AsyncGenerator, List
import httpx

from .base import BaseLlmProvider, LlmCapabilities, ChatMessage

logger = logging.getLogger("AgentLogger")


class OllamaProvider(BaseLlmProvider):
    """
    针对本地运行的 Ollama 服务适配
    """

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model_name: str = "qwen2.5:7b", timeout: float = 60.0, enable_thinking: bool = False):
        super().__init__(base_url, model_name, api_key="", timeout=timeout)
        self.enable_thinking = enable_thinking
        is_reasoning = "r1" in model_name.lower() or "qwq" in model_name.lower() or enable_thinking
        self._last_avail_check = 0.0
        self._is_avail_cached = False

    async def check_availability(self) -> bool:
        """极速健康探测 (0.5s 超时)，避免离线时挂起 asyncio 事件循环"""
        import time
        now = time.time()
        if now - self._last_avail_check < 3.0:
            return self._is_avail_cached

        self._last_avail_check = now
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(1.0, connect=0.5)) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                self._is_avail_cached = (r.status_code == 200)
                return self._is_avail_cached
        except Exception:
            self._is_avail_cached = False
            return False

    @property
    def capabilities(self) -> LlmCapabilities:
        return self._capabilities

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.6,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        # 极速探测：若 Ollama 未启动，毫秒级直接返回，绝不阻塞整个系统的异步事件循环
        if not await self.check_availability():
            yield "【未检测到本地 Ollama 服务正在运行。您可以启动 Ollama 体验完整聊天互动，基础播放与搜索仍正常可用哦 🎵】"
            return

        # Ollama 原生 /api/chat 端点
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }
        # 如果未开启思维链，显式传递 think: False 以跳过数百至上千 token 的内部推理，获得 1~2 秒极速响应
        if not self.enable_thinking:
            payload["think"] = False

        timeout_config = httpx.Timeout(self.timeout, connect=1.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            try:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(f"Ollama Error {response.status_code}: {err_text.decode('utf-8', errors='ignore')}")
                        yield f"【本地 Ollama 响应错误: {response.status_code}】"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            # 提取思维链与正文内容
                            thinking = msg.get("thinking", "")
                            content = msg.get("content", "")
                            if thinking:
                                yield f"<think>{thinking}</think>"
                            elif content:
                                yield content
                            if chunk.get("done", False):
                                break
                        except Exception as e:
                            logger.debug(f"Ollama parse line error: {e}")
            except httpx.ConnectError:
                yield f"【未检测到本地 Ollama 服务正在运行，请启动 Ollama 或在设置中配置在线 API】"
            except httpx.TimeoutException:
                yield "【本地 Ollama 生成超时】"
            except Exception as e:
                logger.error(f"Ollama streaming error: {e}")
                yield f"【Ollama 异常: {str(e)}】"

    async def chat_complete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.6,
        **kwargs
    ) -> str:
        collected = []
        async for chunk in self.chat_stream(messages, temperature, **kwargs):
            collected.append(chunk)
        return "".join(collected)
