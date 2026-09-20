"""
Agent 工具定义与结果基类 (基于架构审查第 6 项与第 16 条)
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    """工具元数据定义"""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_read_only: bool = True  # 是否为只读快照操作 (读写分离护栏)


class ToolResult(BaseModel):
    """工具执行回执标准对象"""
    tool_call_id: str
    tool_name: str
    success: bool
    result: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""
