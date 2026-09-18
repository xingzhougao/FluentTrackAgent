"""
OpenAI 兼容协议 Provider (通用覆盖 DeepSeek, Qwen, 通义千问, SiliconFlow, vLLM 等)
"""
import json
import logging
from typing import AsyncGenerator, List, Any
import httpx

from .base import BaseLlmProvider, LlmCapabilities, ChatMessage

logger = logging.getLogger("AgentLogger")


class OpenAICompatibleProvider(BaseLlmProvider):
    """
    通用 OpenAI 兼容接口，支持所有符合 /chat/completions 规范的云端或本地端点。
    """

    def __init__(self, base_url: str, model_name: str, api_key: str = "", timeout: float = 45.0):
        super().__init__(base_url, model_name, api_key, timeout)
        # 自动识别模型特性
        is_reasoning = "r1" in model_name.lower() or "reasoner" in model_name.lower() or "qwq" in model_name.lower()
        self._capabilities = LlmCapabilities(
            streaming=True,
            native_tools=not is_reasoning,  # 推理模型通常通过思维链直接规划
            structured_output=True,
            reasoning=is_reasoning,
            context_window=65536 if "deepseek" in model_name.lower() else 32768
        )

    @property
    def capabilities(self) -> LlmCapabilities:
        return self._capabilities

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_url(self) -> str:
        base = self.base_url.strip().rstrip("/")
        # 容错：如果用户在 DeepSeek 官方域名后误拼了模型名称(如 /deepseek-flash)
        if "deepseek.com" in base:
            if not (base.endswith("/v1") or base == "https://api.deepseek.com" or base == "http://api.deepseek.com"):
                logger.warning(f"检测到非法的 DeepSeek 路径 '{base}'，已自动纠正为标准地址: https://api.deepseek.com/v1")
                base = "https://api.deepseek.com/v1"

        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.6,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        url = self._build_url()
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                    if response.status_code != 200:
                        err_bytes = await response.aread()
                        err_str = err_bytes.decode("utf-8", errors="ignore")
                        logger.error(f"LLM API Error {response.status_code}: {err_str}")
                        detail = ""
                        try:
                            err_json = json.loads(err_str)
                            if "error" in err_json:
                                detail = err_json["error"].get("message", "")
                        except Exception:
                            pass

                        tip = ""
                        if response.status_code == 404:
                            tip = " (未找到端点，请检查 API 地址是否为 https://api.deepseek.com/v1)"
                        elif response.status_code == 401:
                            tip = " (密钥认证失败，请检查 API Key)"
                        elif response.status_code == 402:
                            tip = " (账户余额不足)"

                        err_hint = f"【模型调用错误 HTTP {response.status_code}{tip}"
                        if detail:
                            err_hint += f": {detail}"
                        err_hint += "】"
                        yield err_hint
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    # 处理常规 content
                                    content = delta.get("content", "")
                                    # 处理 DeepSeek 官方 API 特有的 reasoning_content
                                    reasoning = delta.get("reasoning_content", "")
                                    if reasoning:
                                        yield f"<think>{reasoning}</think>"
                                    elif content:
                                        yield content
                            except Exception as e:
                                logger.debug(f"Chunk parse error: {e}")
            except httpx.ConnectError:
                yield f"【无法连接至大模型服务: {self.base_url}，请检查服务是否开启】"
            except httpx.TimeoutException:
                yield "【大模型响应超时，请稍后重试】"
            except Exception as e:
                logger.error(f"LLM streaming unexpected error: {e}")
                yield f"【大模型生成异常: {str(e)}】"

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
