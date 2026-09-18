"""
LLM 抽象基类与能力元数据描述 (基于架构审查第 5 项与第 25 条)
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from pydantic import BaseModel, Field


class LlmCapabilities(BaseModel):
    """
    模型能力元数据：
    驱动 Agent Runtime 决策是采用 Native Tool Calling 还是基于确定性工作流 / Prompt Slot 提取。
    """
    streaming: bool = True
    native_tools: bool = True
    structured_output: bool = True
    reasoning: bool = False  # 是否为 DeepSeek-R1 / QwQ 等推理思维链模型
    context_window: int = 32768


class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class BaseLlmProvider(ABC):
    """统一 LLM 协议抽象提供者"""

    def __init__(self, base_url: str, model_name: str, api_key: str = "", timeout: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout

    @property
    @abstractmethod
    def capabilities(self) -> LlmCapabilities:
        """返回该模型的能力矩阵"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.6,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        异步流式生成增量内容 (yield delta 文本片段)
        """
        pass

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.6,
        **kwargs
    ) -> str:
        """
        整包生成最终回复文本
        """
        pass
