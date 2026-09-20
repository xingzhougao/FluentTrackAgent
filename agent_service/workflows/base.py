"""
确定性业务工作流抽象基类 (基于架构审查第 3 项：确定性工作流约束)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel


class WorkflowOutput(BaseModel):
    """工作流执行产物"""
    answer_text: str
    tools: List[Dict[str, Any]] = []
    success: bool = True
    error: str = ""


class BaseWorkflow(ABC):
    """业务工作流抽象基类"""

    @abstractmethod
    async def execute(self, session_id: str, request_id: str, **kwargs) -> WorkflowOutput:
        """执行工作流闭环"""
        pass
