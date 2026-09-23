"""
会话上下文管理器 (基于架构审查第 4 项与 Step 4 上下文实体继承要求)
支持多轮上下文滑动窗口管理，以及对话中提及曲目实体的追踪、继承与指代消歧。
"""
import re
import logging
from typing import List, Dict, Optional, Any
from llm.base import ChatMessage

logger = logging.getLogger("AgentLogger")

SYSTEM_PROMPT = """你是一个内嵌在 Fluent Music 桌面播放器中的智能音乐伙伴（Music AI Agent）。
你不仅是一个高效的音乐播放与控制助手，更是一位懂音乐、有共情力、有品味的心灵挚友。

【你的核心特质与能力】
1. 情感共鸣与心理洞察：当用户与你闲聊、倾诉心情（如“你猜我今天的心情如何”、“我今天好累”、“今天遇到了开心的事”）时，请以温暖、亲切、富有幽默感和洞察力的方式与用户互动。不要做机械的指令应答，而是像老朋友一样交流感受、探讨生活与心境。
2. 音乐纽带与智能推荐：在与用户聊天、揣测其心理或探讨话题时，你可以自然顺畅地引申并推荐契合此刻心境的音乐作品，并聊聊歌曲背后的故事、旋律风格或情感共鸣点。
3. 专业音乐素养：熟悉流行、摇滚、民谣、古典、爵士、电子等各类曲风与音乐家历史，能深入浅出地解答音乐知识。
4. 交互与表达：言谈真诚自然，富有感染力。当用户有明确点歌或播放指令时，清晰直接回应。
"""


class SessionContext:
    """单个会话的上下文状态容器，附带实体记忆槽位"""

    def __init__(self, session_id: str, max_turns: int = 10):
        self.session_id = session_id
        self.max_turns = max_turns
        self.messages: List[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT)
        ]
        self.last_user_query: str = ""

        # Step 4 实体记忆槽位
        self.last_recommended_tracks: List[Dict[str, Any]] = []
        self.last_played_track: Optional[Dict[str, Any]] = None
        self.last_action: Optional[str] = None
        # 会话偏好设置 (如 auto_download 等)
        self.preferences: Dict[str, Any] = {"auto_download": False}

    def add_user_message(self, content: str):
        self.last_user_query = content
        self.messages.append(ChatMessage(role="user", content=content))
        self._trim_history()

    def add_assistant_message(self, content: str, recommended_tracks: Optional[List[Dict[str, Any]]] = None):
        self.messages.append(ChatMessage(role="assistant", content=content))
        self._trim_history()

        # 优先使用显式传入的推荐曲目实体列表
        if recommended_tracks:
            self.last_recommended_tracks = recommended_tracks
        else:
            # 自动从文本中提取《...》中的歌曲名称与对应歌手作为候选实体
            extracted_tracks = self.extract_song_entities_with_artist(content)
            if extracted_tracks:
                self.last_recommended_tracks = extracted_tracks

    def record_played_track(self, track: Dict[str, Any]):
        """记录当前成功播放的曲目"""
        self.last_played_track = track

    def record_recommended_tracks(self, tracks: List[Dict[str, Any]]):
        """记录本轮推荐的曲目实体列表"""
        self.last_recommended_tracks = tracks

    def clear(self):
        """重置当前会话及实体记忆"""
        self.messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        self.last_user_query = ""
        self.last_recommended_tracks.clear()
        self.last_played_track = None
        self.last_action = None

    def extract_song_entities_from_text(self, text: str) -> List[str]:
        """从自然语言文本中提取书名号《》中的歌曲名"""
        matches = re.findall(r"《([^》]+)》", text)
        return [m.strip() for m in matches if m.strip()]

    def extract_song_entities_with_artist(self, text: str) -> List[Dict[str, str]]:
        """从自然语言文本中提取书名号《》中的歌曲名以及对应关联的歌手"""
        results: List[Dict[str, str]] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or "《" not in line or "》" not in line:
                continue
            for match in re.finditer(r"《([^》]+)》", line):
                title = match.group(1).strip()
                if not title:
                    continue
                artist = ""
                # 1. 优先尝试从《...》后侧提取歌手，如 《海阔天空》—— Beyond, 《晴天》- 周杰伦, 《红日》(李克勤)
                post_part = line[match.end():].strip()
                post_clean = re.sub(r"^(?:[—–\-—~]+|by|歌手[:：]?|\s*[:：])\s*", "", post_part).strip()
                paren_match = re.match(r"^[(（]([A-Za-z0-9\u4e00-\u9fa5\s]+)[)）]", post_clean)
                if paren_match:
                    artist_cand = paren_match.group(1).strip()
                else:
                    artist_cand = re.split(r"[,，。！？!?；;\n]|(?:\s+[-—–])", post_clean)[0].strip()
                    if len(artist_cand) > 15 or any(w in artist_cand for w in ["这首", "非常", "适合", "推荐", "因为", "经典"]):
                        artist_cand = ""

                # 2. 如果后侧未提取到，尝试从《...》前侧提取歌手，如 "Beyond 的《海阔天空》", "周杰伦《晴天》"
                if not artist_cand:
                    pre_part = line[:match.start()].strip()
                    pre_clean = re.sub(r"^(?:###\s*)?(?:[🎵0-9一二两三四五六七八九十\.\s、\-—–:]+)?(?:第[0-9一二两三四五六七八九十]+首[:：\s]*)?", "", pre_part).strip()
                    pre_clean = re.sub(r"(?:唱的|的)?$", "", pre_clean).strip()
                    if pre_clean and len(pre_clean) <= 15:
                        artist_cand = pre_clean

                if artist_cand:
                    invalid_art = {"歌曲", "音乐", "单曲", "第一首", "第二首", "第三首", "第四首", "推荐", "理由"}
                    if artist_cand not in invalid_art and len(artist_cand) <= 15:
                        artist = artist_cand

                results.append({"title": title, "artist": artist})

        # 保序去重
        seen = set()
        unique_results = []
        for r in results:
            key = (r["title"], r["artist"])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        return unique_results

    def get_candidate_tracks(self) -> List[Dict[str, str]]:
        """获取当前活跃的候选推荐曲目列表（自适应缓存或从最近的 assistant 消息中反向解析）"""
        if self.last_recommended_tracks:
            return self.last_recommended_tracks
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                extracted = self.extract_song_entities_with_artist(msg.content)
                if extracted:
                    self.last_recommended_tracks = extracted
                    return extracted
        return []

    def resolve_track_from_context(self, user_text: str) -> Optional[Dict[str, str]]:
        """
        跨轮上下文意图与决策实体解析：
        支持“帮我播放你这四首歌中你最推荐的”、“播放第二首”、“放最后一首”、“放刚才推荐的”等指令，
        返回包含 title 和 artist 的字典。
        """
        clean = user_text.strip().lower()
        candidates = self.get_candidate_tracks()
        if not candidates:
            return None

        # 1. 决策类识别（最推荐、最好听、帮我选、挑一首、你决定）
        decision_keywords = [
            "最推荐", "最好听", "最火", "最经典", "最好", "最喜欢",
            "帮我选", "你选", "你挑", "帮我挑", "挑一首", "选一首", "选首", "挑首",
            "你做决定", "你决定", "你觉得哪首好", "哪首好听就放哪首", "哪首最推荐",
            "首选"
        ]
        if any(k in clean for k in decision_keywords):
            return candidates[0]

        # 2. 序号提取（第一首、第二首、第N首、最后一首）
        if any(k in clean for k in ["最后一首", "最后首", "最后那首", "最后的一首"]):
            return candidates[-1]

        ord_match = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*(?:首|个|曲)(?:歌曲|歌|曲目)?", clean)
        if ord_match:
            from runtime.intent_router import parse_ordinal_num
            idx = parse_ordinal_num(ord_match.group(1))
            if idx is not None:
                if idx < len(candidates):
                    return candidates[idx]
                return candidates[-1]

        # 3. 泛指代匹配词库
        referential_phrases = [
            "播放刚刚说的歌", "播放刚刚说的", "播放刚才说的歌", "播放刚才说的",
            "放刚才说的歌", "放刚才说的", "放刚刚说的歌", "放刚刚说的",
            "放你刚刚推荐的歌", "放你刚才推荐的歌", "播放你推荐的歌", "播放推荐的",
            "放推荐的", "放刚才推荐的", "播放刚才推荐的", "放刚才推荐", "播放刚才推荐",
            "你给我播放呀", "给我播放呀", "给我放呀", "怎么不放呀", "放呀", "播放啊",
            "放这首歌", "播放它", "放它", "播放这首", "放这首", "放上面那首",
            "播放刚才那首", "放刚才那首", "播放刚才说的歌曲", "放刚刚说的歌曲",
            "刚才推荐的那首", "刚才推荐的", "刚刚推荐的", "刚才说的", "刚刚说的",
            "你倒是放啊", "快放", "快播放", "播放呀"
        ]
        if any(p in clean for p in referential_phrases) or clean in ["播放", "放", "开播", "听这首"]:
            return candidates[0]

        if any(k in clean for k in ["刚才推荐", "刚刚推荐", "之前推荐", "刚才说", "刚刚说", "之前说"]):
            return candidates[0]

        return None

    def resolve_song_from_context(self, user_text: str) -> Optional[str]:
        """向后兼容接口：仅返回目标歌名"""
        track = self.resolve_track_from_context(user_text)
        return track.get("title") if track else None

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
