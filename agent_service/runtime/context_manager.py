"""
会话上下文管理器 (基于架构审查第 4 项与第 20 条：Context 与 PlayerState 严格解耦)
"""
from typing import List, Dict
from llm.base import ChatMessage

SYSTEM_PROMPT = """你是一个内嵌在 Fluent Music 桌面播放器中的智能音乐助手。
你的目标是理解用户的音乐需求并提供流畅、优雅、耐心的回应。

【你的核心职责】
1. 播放与硬件控制：音量调节、暂停/恢复、上一首/下一首、播放模式、歌曲收藏。
2. 本地曲库搜索与精准点歌：根据歌名、歌手查找本地音乐文件。
3. 智能场景与情绪歌单：根据用户的工作学习、运动、助眠、通勤、放松等场景与心情，推荐并生成歌单。
4. 网络音乐发现：当本地曲库没有收录时，协助用户搜索在线资源并在确认后下载入库。

【交互守则】
- 保持回答精炼友好，避免冗长废话。
- 如果用户输入播放控制或搜歌指令，优先执行操作，给出直接肯定的反馈。
- 如果使用具备思维链推理的模型，可在思考过程中分析用户意图与曲目信息。
"""


class SessionContext:
    """单个会话的上下文状态容器"""

    def __init__(self, session_id: str, max_turns: int = 10):
        self.session_id = session_id
        self.max_turns = max_turns
        self.messages: List[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT)
        ]
        self.last_user_query: str = ""

    def add_user_message(self, content: str):
        self.last_user_query = content
        self.messages.append(ChatMessage(role="user", content=content))
        self._trim_history()

    def add_assistant_message(self, content: str):
        self.messages.append(ChatMessage(role="assistant", content=content))
        self._trim_history()

    def clear(self):
        """重置当前会话"""
        self.messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        self.last_user_query = ""

    def _trim_history(self):
        """滑动窗口裁剪：保留 system prompt，保留最近 2 * max_turns 条消息"""
        if len(self.messages) <= 1 + 2 * self.max_turns:
            return
        system_msg = self.messages[0]
        recent = self.messages[-(2 * self.max_turns):]
        self.messages = [system_msg] + recent


class ContextManager:
    """全局会话上下文管理中心"""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._sessions: Dict[str, SessionContext] = {}

    def get_session(self, session_id: str = "default") -> SessionContext:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionContext(session_id, self.max_turns)
        return self._sessions[session_id]

    def clear_session(self, session_id: str = "default"):
        if session_id in self._sessions:
            self._sessions[session_id].clear()
