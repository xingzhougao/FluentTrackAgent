"""
双轨意图识别与槽位提取路由器 (基于 Step 4 多意图与跨轮上下文要求)
涵盖：
1. PLAYER_CONTROL: 播放/暂停/音量/切歌/收藏/模式等硬件级控制
2. SEARCH_AND_PLAY: 精准/模糊曲目点歌、歌手点歌、跨轮指代开播（如“你给我播放呀”）
3. SMART_PLAYLIST: 场景、情绪与多维标签智能歌单生成与开播
4. CHAT: 音乐知识与普通问候闲聊
"""
import re
import json
import logging
from typing import Tuple, Dict, Any, Optional
from llm.base import BaseLlmProvider, ChatMessage

logger = logging.getLogger("AgentLogger")


class IntentResult:
    """意图路由结果"""
    def __init__(
        self,
        intent_type: str,
        action: str = "",
        params: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0
    ):
        self.intent_type = intent_type  # "PLAYER_CONTROL" | "SEARCH_AND_PLAY" | "SMART_PLAYLIST" | "CHAT"
        self.action = action
        self.params = params or {}
        self.confidence = confidence

    def __repr__(self):
        return f"<IntentResult intent={self.intent_type} action={self.action} params={self.params} conf={self.confidence}>"


class IntentRouter:
    """
    双轨意图路由器：
    - 快速规则层 (毫秒级，覆盖高频控制、点歌、场景歌单及上下文指代)
    - LLM 结构化提取降级层 (复杂多变句式)
    """

    @classmethod
    def match_rule(cls, text: str) -> Optional[IntentResult]:
        clean = text.strip()
        lower = clean.lower()

        # 0. 跨轮指代消歧（最高优先级拦截，防止被误判为常规播放或 resume）
        referential_phrases = [
            "你给我播放呀", "给我播放呀", "给我放呀", "怎么不放呀", "放呀", "播放啊",
            "播放刚刚说的歌", "播放刚刚说的", "播放刚才说的歌", "播放刚才说的",
            "放刚才说的歌", "放刚才说的", "放刚刚说的歌", "放刚刚说的",
            "放你刚刚推荐的歌", "放你刚才推荐的歌", "播放你推荐的歌", "播放推荐的",
            "放这首歌", "播放它", "放它", "播放这首", "放这首", "放上面那首",
            "播放刚才那首", "放刚才那首", "播放刚才说的歌曲", "放刚刚说的歌曲",
            "刚才推荐的那首", "刚才推荐的", "刚刚推荐的", "刚才说的", "刚刚说的",
            "你倒是放啊", "快放", "快播放", "播放呀"
        ]
        if any(p in lower for p in referential_phrases) or (
            any(k in lower for k in ["刚才推荐", "刚刚推荐", "之前推荐", "刚才说", "刚刚说", "之前说"])
        ) or (
            any(w in lower for w in ["放", "播", "听"]) and any(ord_k in lower for ord_k in ["第一首", "第1首", "第二首", "第2首", "第三首", "第3首", "最后一首"])
        ):
            return IntentResult(
                intent_type="SEARCH_AND_PLAY",
                action="search_and_play",
                params={"query": "", "is_context_referential": True}
            )

        # 1. 播放状态与歌曲信息查询
        info_keywords = ["现在放的是什么歌", "这是什么歌", "现在播的什么", "正在放什么", "这是谁唱的", "谁唱的", "歌名是什么", "哪首歌", "当前歌曲", "播放信息"]
        if any(k in lower for k in info_keywords):
            return IntentResult(intent_type="PLAYER_CONTROL", action="get_player_state")

        # 2. 音量绝对控制
        vol_match = re.search(r"(?:音量|声音|声量)(?:调到|调为|设为|设置成|改为|变为|到)?\s*(\d{1,3})\s*%?", lower)
        if vol_match:
            val = int(vol_match.group(1))
            val = max(0, min(100, val))
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": val})

        vol_match_alt = re.search(r"(\d{1,3})\s*%\s*(?:音量|声音)", lower)
        if vol_match_alt:
            val = int(vol_match_alt.group(1))
            val = max(0, min(100, val))
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": val})

        # 3. 音量相对控制与静音
        if any(k in lower for k in ["大声点", "大声一点", "声音大一点", "音量加大", "声音调大", "调大音量", "太小声了"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"delta": 15})
        if any(k in lower for k in ["小声点", "小声一点", "声音小一点", "音量减小", "声音调小", "调小音量", "太吵了", "太吵", "声音太大了"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"delta": -15})
        if lower in ["静音", "闭嘴", "关掉声音"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": 0})

        # 4. 暂停与恢复
        if lower in ["暂停", "暂停播放", "先别放了", "停一下", "别唱了", "别放了", "停止"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="pause")
        if lower in ["继续", "继续播放", "接着放", "开始播放"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="resume")

        # 5. 切歌 (下一首 / 上一首)
        if any(k in lower for k in ["下一首", "切歌", "切下一首", "换首歌", "换一首", "下一曲", "下一首歌曲"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="next_track")
        if any(k in lower for k in ["上一首", "切上一首", "上一曲", "回上一首", "退回上一首"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="previous_track")

        # 6. 歌曲收藏
        if any(k in lower for k in ["收藏这首歌", "喜欢这首歌", "加到我喜欢", "加入我喜欢", "收藏当前歌曲", "我喜欢这首歌"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="toggle_favorite")
        if lower in ["收藏", "喜欢", "取消收藏", "取消喜欢"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="toggle_favorite")

        # 7. 播放模式
        if "单曲循环" in lower:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 2})
        if "随机播放" in lower:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 1})
        if "顺序播放" in lower or "列表循环" in lower:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 0})

        # 8. 场景与情绪智能歌单 (SMART_PLAYLIST)
        # 例如：“我今天有点不开心 给我播放一首能让我心情愉悦的歌曲”
        # “我要写代码了，来几首轻快的中文歌”
        # “放点适合助眠的纯音乐”
        mood_scene_keywords = [
            "不开心", "难过", "伤心", "心情愉悦", "心情好", "心情不好", "郁闷", "压抑", "烦躁",
            "开心", "欢快", "轻快", "治愈", "高能", "兴奋",
            "写代码", "敲代码", "编程", "写程序", "工作", "专注", "办公",
            "助眠", "睡觉", "催眠", "失眠",
            "运动", "跑步", "健身", "锻炼",
            "通勤", "散步", "开车", "自驾"
        ]
        has_music_trigger = any(w in lower for w in ["播放", "放", "推荐", "听", "来", "歌", "曲"])
        if any(kw in lower for kw in mood_scene_keywords) and has_music_trigger:
            return IntentResult(
                intent_type="SMART_PLAYLIST",
                action="smart_playlist",
                params={"raw_text": clean}
            )

        # 9. 精准与模糊点歌 (SEARCH_AND_PLAY)
        # 匹配书名号，例如 “播放《晴天》”
        title_in_quotes = re.search(r"《([^》]+)》", clean)
        if title_in_quotes and any(w in lower for w in ["播放", "放", "听", "播"]):
            return IntentResult(
                intent_type="SEARCH_AND_PLAY",
                action="search_and_play",
                params={"query": title_in_quotes.group(1).strip()}
            )

        # 匹配 “播放[歌名]” / “放一首[歌名]” / “我想听[歌名]”
        # 排除纯控制词汇
        not_song_names = ["音乐", "歌曲", "歌", "声音", "音量", "伴奏", "下一首", "上一首"]

        # 匹配歌手点歌，例如 “放一首周杰伦的歌” / “放周杰伦的歌” / “来首陈奕迅的歌”
        artist_song_match = re.search(r"(?:播放|放一首|来一首|听一首|放|听|播|来首)\s*([^\s，,。！？的]+)的(?:歌|歌曲)", clean)
        if artist_song_match:
            art = artist_song_match.group(1).strip()
            if art not in not_song_names:
                return IntentResult(
                    intent_type="SEARCH_AND_PLAY",
                    action="search_and_play",
                    params={"artist": art, "query": ""}
                )

        # 匹配 “播放[歌名]” / “放[歌名]”
        play_match = re.search(r"^(?:播放|放一首|来一首|放首|听一首|听听|我想听|来首|播放歌曲|放)\s*([^\s，,。！？]{2,15})$", clean)
        if play_match:
            song_candidate = play_match.group(1).strip()
            if song_candidate not in not_song_names:
                # 检查是否包含歌手与歌名组合，例如 "周杰伦的晴天"
                if "的" in song_candidate:
                    parts = song_candidate.split("的", 1)
                    return IntentResult(
                        intent_type="SEARCH_AND_PLAY",
                        action="search_and_play",
                        params={"artist": parts[0].strip(), "query": parts[1].strip()}
                    )
                return IntentResult(
                    intent_type="SEARCH_AND_PLAY",
                    action="search_and_play",
                    params={"query": song_candidate}
                )

        return None

    @classmethod
    async def route_intent(
        cls,
        text: str,
        llm_provider: Optional[BaseLlmProvider] = None,
        context_session = None
    ) -> IntentResult:
        """
        统一意图路由入口：
        1. 快速确定性规则
        2. 若未命中且带音乐相关词汇，由 LLM 做结构化意图槽位识别
        """
        rule_result = cls.match_rule(text)
        if rule_result:
            # 如果是上下文指代且传入了 context，立刻尝试预解析
            if rule_result.intent_type == "SEARCH_AND_PLAY" and rule_result.params.get("is_context_referential"):
                if context_session:
                    resolved = context_session.resolve_song_from_context(text)
                    if resolved:
                        rule_result.params["query"] = resolved
            logger.info(f"[IntentRouter] 命中确定性规则: {rule_result}")
            return rule_result

        # 如果没有明显的音乐/控制/交互词汇，直接归为常规对话
        suspicious_keywords = [
            "音量", "声音", "放", "停", "切", "唱", "歌", "大声", "小声",
            "静音", "循环", "收藏", "喜欢", "听", "播", "曲", "推荐", "心情", "首"
        ]
        if not any(k in text for k in suspicious_keywords) or not llm_provider:
            return IntentResult(intent_type="CHAT")

        # 降级：调用 LLM 做结构化意图与槽位提取
        try:
            prompt = f"""你是一个桌面音乐播放器的意图理解分析器。分析用户的指令属于哪类意图并提取关键参数。

意图类别与 action 规范：
1. PLAYER_CONTROL (基础控制):
   - set_volume: {{"volume": 0-100}} 或 {{"delta": 相对变化}}
   - pause: 暂停
   - resume: 继续
   - next_track: 下一首
   - previous_track: 上一首
   - toggle_favorite: 收藏或喜欢
   - get_player_state: 查询当前放什么歌或播放状态
2. SEARCH_AND_PLAY (指定曲目或歌手点歌):
   - search_and_play: {{"query": "歌名", "artist": "歌手"}}
3. SMART_PLAYLIST (根据心情、情绪、工作学习场景推荐并播放):
   - smart_playlist: {{"mood": "情绪关键词", "scene": "场景关键词", "language": "语种", "count": 数量}}
4. CHAT (常规聊天、问答、与播放操作无关):
   - chat: {{}}

用户指令: "{text}"

请严格输出 JSON 对象，绝不要输出额外解释或 markdown 以外的文字：
{{"intent_type": "PLAYER_CONTROL|SEARCH_AND_PLAY|SMART_PLAYLIST|CHAT", "action": "...", "params": {{}}}}
"""
            raw = await llm_provider.chat_complete(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.1
            )
            clean_json = raw.strip()
            if "{" in clean_json and "}" in clean_json:
                start = clean_json.index("{")
                end = clean_json.rindex("}") + 1
                data = json.loads(clean_json[start:end])
                intent_type = data.get("intent_type", "CHAT")
                action = data.get("action", "")
                params = data.get("params", {})
                if intent_type in ["PLAYER_CONTROL", "SEARCH_AND_PLAY", "SMART_PLAYLIST"]:
                    return IntentResult(
                        intent_type=intent_type,
                        action=action,
                        params=params
                    )
        except Exception as e:
            logger.debug(f"[IntentRouter] LLM 意图降级提取异常: {e}")

        return IntentResult(intent_type="CHAT")
