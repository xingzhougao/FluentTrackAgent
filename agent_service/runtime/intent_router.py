"""
双轨意图识别与槽位提取路由器 (基于架构审查第 3 项与第 18 条)
"""
import re
import json
import logging
from typing import Tuple, Dict, Any, Optional
from llm.base import BaseLlmProvider, ChatMessage

logger = logging.getLogger("AgentLogger")


class IntentResult:
    """意图路由结果"""
    def __init__(self, intent_type: str, action: str = "", params: Optional[Dict[str, Any]] = None, confidence: float = 1.0):
        self.intent_type = intent_type  # "PLAYER_CONTROL" | "CHAT" | "UNKNOWN"
        self.action = action            # "set_volume", "pause", "resume", "next_track", etc.
        self.params = params or {}
        self.confidence = confidence

    def __repr__(self):
        return f"<IntentResult intent={self.intent_type} action={self.action} params={self.params} conf={self.confidence}>"


class IntentRouter:
    """
    意图路由器：
    1. 快速确定性规则层 (毫秒级，覆盖 90% 常见播放控制句式)
    2. LLM 结构化提取降级层 (处理句式多变但意图明确的复杂控制)
    """

    @classmethod
    def match_rule(cls, text: str) -> Optional[IntentResult]:
        clean = text.strip().lower()

        # 1. 播放状态与歌曲信息查询
        info_keywords = ["现在放的是什么歌", "这是什么歌", "现在播的什么", "正在放什么", "这是谁唱的", "谁唱的", "歌名是什么", "哪首歌", "当前歌曲", "播放信息"]
        if any(k in clean for k in info_keywords):
            return IntentResult(intent_type="PLAYER_CONTROL", action="get_player_state")

        # 2. 音量绝对控制 (例如: 音量调到30, 声音30%, 调为50)
        vol_match = re.search(r"(?:音量|声音|声量)(?:调到|调为|设为|设置成|改为|变为|到)?\s*(\d{1,3})\s*%?", clean)
        if vol_match:
            val = int(vol_match.group(1))
            val = max(0, min(100, val))
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": val})

        vol_match_alt = re.search(r"(\d{1,3})\s*%\s*(?:音量|声音)", clean)
        if vol_match_alt:
            val = int(vol_match_alt.group(1))
            val = max(0, min(100, val))
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": val})

        # 3. 音量相对控制
        if any(k in clean for k in ["大声点", "大声一点", "声音大一点", "音量加大", "声音调大", "调大音量", "太小声了"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"delta": 15})
        if any(k in clean for k in ["小声点", "小声一点", "声音小一点", "音量减小", "声音调小", "调小音量", "太吵了", "太吵", "声音太大了"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"delta": -15})
        if clean in ["静音", "闭嘴", "关掉声音"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_volume", params={"volume": 0})

        # 4. 暂停与恢复
        if clean in ["暂停", "暂停播放", "先别放了", "停一下", "别唱了", "别放了", "停止"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="pause")
        if clean in ["继续", "继续播放", "接着放", "开始播放", "放音乐"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="resume")

        # 5. 切歌 (下一首 / 上一首)
        if any(k in clean for k in ["下一首", "切歌", "切下一首", "换首歌", "换一首", "下一曲", "下一首歌曲"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="next_track")
        if any(k in clean for k in ["上一首", "切上一首", "上一曲", "回上一首", "退回上一首"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="previous_track")

        # 6. 歌曲收藏
        if any(k in clean for k in ["收藏这首歌", "喜欢这首歌", "加到我喜欢", "加入我喜欢", "收藏当前歌曲", "我喜欢这首歌"]):
            return IntentResult(intent_type="PLAYER_CONTROL", action="toggle_favorite")
        if clean in ["收藏", "喜欢", "取消收藏", "取消喜欢"]:
            return IntentResult(intent_type="PLAYER_CONTROL", action="toggle_favorite")

        # 7. 播放模式
        if "单曲循环" in clean:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 2})
        if "随机播放" in clean:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 1})
        if "顺序播放" in clean or "列表循环" in clean:
            return IntentResult(intent_type="PLAYER_CONTROL", action="set_play_mode", params={"mode": 0})

        return None

    @classmethod
    async def route_intent(cls, text: str, llm_provider: Optional[BaseLlmProvider] = None) -> IntentResult:
        """
        统一意图路由入口：先走快速规则，未命中且带有播放器相关词汇时，走 LLM 结构化提取
        """
        rule_result = cls.match_rule(text)
        if rule_result:
            logger.info(f"[IntentRouter] 命中确定性规则: {rule_result}")
            return rule_result

        # 如果连基本的音乐/控制关键词都没有，直接归为常规对话
        suspicious_keywords = ["音量", "声音", "放", "停", "切", "唱", "歌", "大声", "小声", "静音", "循环", "收藏", "喜欢"]
        if not any(k in text for k in suspicious_keywords) or not llm_provider:
            return IntentResult(intent_type="CHAT")

        # 降级：调用 LLM 做槽位提取
        try:
            prompt = f"""分析用户的指令是否属于音乐播放器控制指令。
可选 action 列表：
- set_volume: 调节音量，参数 {{"volume": 0-100}} 或 {{"delta": 相对增减量}}
- pause: 暂停播放
- resume: 继续播放
- next_track: 下一首
- previous_track: 上一首
- toggle_favorite: 收藏或取消喜欢
- get_player_state: 询问当前放什么歌或播放状态
- other: 不属于播放控制（如问候、聊天等）

用户指令: "{text}"

请严格以 JSON 格式输出，不要有任何多余文字：
{{"action": "对应动作或other", "params": {{}}}}
"""
            raw = await llm_provider.chat_complete([ChatMessage(role="user", content=prompt)], temperature=0.1)
            # 解析 JSON
            clean_json = raw.strip()
            if "{" in clean_json and "}" in clean_json:
                start = clean_json.index("{")
                end = clean_json.rindex("}") + 1
                data = json.loads(clean_json[start:end])
                action = data.get("action", "other")
                if action != "other":
                    return IntentResult(
                        intent_type="PLAYER_CONTROL",
                        action=action,
                        params=data.get("params", {})
                    )
        except Exception as e:
            logger.debug(f"[IntentRouter] LLM 意图降级提取异常: {e}")

        return IntentResult(intent_type="CHAT")
