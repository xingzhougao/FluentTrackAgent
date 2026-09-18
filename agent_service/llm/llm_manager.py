"""
LLM 管理器：负责根据配置动态初始化与切换 Provider
"""
import logging
from typing import Optional
from config import LlmConfig, global_config
from .base import BaseLlmProvider
from .openai_compatible import OpenAICompatibleProvider
from .ollama_provider import OllamaProvider

logger = logging.getLogger("AgentLogger")


class LlmManager:
    """全局 LLM 单例管理器"""

    def __init__(self, config: Optional[LlmConfig] = None):
        self.config = config or global_config.llm
        self._provider: Optional[BaseLlmProvider] = None
        self._init_provider()

    def _init_provider(self):
        if self.config.provider_type == "local":
            logger.info(f"初始化本地模型 Provider: {self.config.local_model} @ {self.config.local_base_url}")
            # 如果本地是 /v1 格式，可用 OpenAI 兼容；否则用原生 Ollama
            if "/v1" in self.config.local_base_url:
                self._provider = OpenAICompatibleProvider(
                    base_url=self.config.local_base_url,
                    model_name=self.config.local_model,
                    api_key="",
                    timeout=self.config.timeout_seconds
                )
            else:
                self._provider = OllamaProvider(
                    base_url=self.config.local_base_url,
                    model_name=self.config.local_model,
                    timeout=self.config.timeout_seconds,
                    enable_thinking=self.config.enable_thinking
                )
        else:
            logger.info(f"初始化云端模型 Provider: {self.config.cloud_model} @ {self.config.cloud_base_url}")
            self._provider = OpenAICompatibleProvider(
                base_url=self.config.cloud_base_url,
                model_name=self.config.cloud_model,
                api_key=self.config.cloud_api_key,
                timeout=self.config.timeout_seconds
            )

    def get_provider(self) -> BaseLlmProvider:
        if self._provider is None:
            self._init_provider()
        return self._provider

    def update_config(self, new_config: LlmConfig):
        self.config = new_config
        self._init_provider()
        logger.info("LLM Provider 配置已更新并重新加载")
