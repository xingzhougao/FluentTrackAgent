"""
服务配置中心与 Pydantic 模型
"""
import os
import secrets
from typing import Optional, Literal
from pydantic import BaseModel, Field


class LlmConfig(BaseModel):
    """LLM 访问配置"""
    provider_type: Literal["local", "cloud"] = "local"
    
    # 本地模型配置 (对接已安装的 Ollama qwen3.5:9b-q4_K_M)
    local_base_url: str = "http://127.0.0.1:11434"
    local_model: str = "qwen3.5:9b-q4_K_M"
    
    # 在线模型配置 (兼容 OpenAI deepseek 等)
    cloud_base_url: str = "https://api.deepseek.com/v1"
    cloud_api_key: str = ""
    cloud_model: str = "deepseek-flash"
    
    # 是否开启深度思考/思维链 (音乐助手默认 False，获得 1~2 秒极速体验；开启后可实时查看思考过程)
    enable_thinking: bool = False
    temperature: float = 0.6
    timeout_seconds: float = 120.0


class SoulseekConfig(BaseModel):
    """Soulseek / slskd P2P 配置"""
    enabled: bool = True
    api_base_url: str = "http://127.0.0.1:5030/api/v0"
    api_key: str = ""
    timeout_seconds: float = 4.0


class XiagebaConfig(BaseModel):
    """下歌吧 (刘明野) 配置"""
    enabled: bool = True
    base_url: str = "https://xiageba.liumingye.cn"
    timeout_seconds: float = 6.0


class ServiceConfig(BaseModel):
    """Agent 微服务运行时配置"""
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = Field(default_factory=lambda: secrets.token_hex(16))
    dev_mode: bool = True  # 开发模式下允许免 token 或空 token 访问

    max_history_turns: int = 10
    llm: LlmConfig = Field(default_factory=LlmConfig)
    soulseek: SoulseekConfig = Field(default_factory=SoulseekConfig)
    xiageba: XiagebaConfig = Field(default_factory=XiagebaConfig)

    log_level: str = "INFO"
    log_file: str = "agent.log"


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agent_config.json")


def load_config() -> ServiceConfig:
    """从磁盘加载持久化配置，若不存在则使用默认值"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                import json
                data = json.load(f)
                return ServiceConfig(**data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    return ServiceConfig()


def save_config(cfg: ServiceConfig):
    """持久化配置到磁盘"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(cfg.model_dump_json(indent=2))
    except Exception as e:
        print(f"保存配置文件失败: {e}")


# 全局单例配置实例
global_config = load_config()
