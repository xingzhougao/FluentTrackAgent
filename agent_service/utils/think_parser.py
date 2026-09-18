"""
DeepSeek-R1 / 推理模型 <think> 标签流式与整块解析器
"""
import re
from typing import Tuple


class ThinkTagParser:
    """
    负责解析模型输出中的思维链标签 <think>...</think>
    支持整块内容提取和流式增量状态判定。
    """

    THINK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL)

    @classmethod
    def extract_think_and_answer(cls, raw_text: str) -> Tuple[str, str]:
        """
        从完整文本中拆分 (thinking_content, final_answer)
        """
        if not raw_text:
            return "", ""

        match = cls.THINK_REGEX.search(raw_text)
        if match:
            thinking = match.group(1).strip()
            answer = cls.THINK_REGEX.sub("", raw_text).strip()
            return thinking, answer

        # 如果只有未闭合的 <think>
        if "<think>" in raw_text and "</think>" not in raw_text:
            parts = raw_text.split("<think>", 1)
            return parts[1].strip(), parts[0].strip()

        return "", raw_text.strip()


class StreamingThinkTracker:
    """
    流式增量跟踪器：在逐 token 接收流式数据时，动态判断当前 chunk 属于思考过程还是正式回答。
    """

    def __init__(self):
        self.in_think = False
        self.think_buffer = []
        self.answer_buffer = []

    def feed(self, delta: str) -> Tuple[str, str]:
        """
        传入当前 delta 增量
        返回元组: (think_delta, answer_delta)
        """
        if not delta:
            return "", ""

        # 检查是否包含标签开闭
        combined = delta
        think_out = ""
        answer_out = ""

        if "<think>" in combined:
            parts = combined.split("<think>", 1)
            answer_out += parts[0]
            self.in_think = True
            combined = parts[1]

        if "</think>" in combined:
            parts = combined.split("</think>", 1)
            if self.in_think:
                think_out += parts[0]
            self.in_think = False
            answer_out += parts[1]
        else:
            if self.in_think:
                think_out += combined
            else:
                answer_out += combined

        if think_out:
            self.think_buffer.append(think_out)
        if answer_out:
            self.answer_buffer.append(answer_out)

        return think_out, answer_out

    @property
    def full_thinking(self) -> str:
        return "".join(self.think_buffer).strip()

    @property
    def full_answer(self) -> str:
        return "".join(self.answer_buffer).strip()
