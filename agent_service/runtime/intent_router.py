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


def parse_ordinal_num(num_str: str) -> Optional[int]:
    num_str = num_str.strip()
    if num_str.isdigit():
        val = int(num_str)
        return val - 1 if val >= 1 else None

    c_map = {
        "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
    }
    if num_str in c_map:
        return c_map[num_str] - 1

    if num_str.startswith("十") and len(num_str) == 2 and num_str[1] in c_map:
        return 10 + c_map[num_str[1]] - 1

    if len(num_str) >= 2 and num_str[0] in c_map and num_str[1] == "十":
        tens = c_map[num_str[0]] * 10
        if len(num_str) == 3 and num_str[2] in c_map:
            return tens + c_map[num_str[2]] - 1
        return tens - 1

MODIFIERS_LIST = [
    # 动作/副词/指代
    "一下", "一首", "首", "个", "点", "曲", "一曲",
    "那首", "那一首", "这首", "这一首", "哪首",
    # 评价/热度/流行度/地位
    "代表作歌曲", "代表作品", "代表作", "成名之作", "成名曲", "主打单曲", "主打歌", "主打曲",
    "经典歌曲", "经典老歌", "经典之作", "传世之作", "经典名曲", "经典",
    "热门歌曲", "热门单曲", "热门曲目", "热门",
    "最火的那首", "最火这首", "最火的歌", "最火歌曲", "最火的", "最火",
    "比较火的", "挺火的", "很火的歌", "很火的", "超火的", "超火", "很火", "爆款",
    "比较出名的", "很有名的", "出名的歌", "出名的", "著名的", "知名", "比较出名", "很有名", "出名",
    "特别好听的", "很好听的", "好听的那首", "好听的歌", "好听的", "动听的", "优美的", "好听",
    "脍炙人口的", "红极一时的", "耳熟能详的", "家喻户晓的", "脍炙人口", "耳熟能详",
    # 类别/属性/载体
    "最新歌曲", "最新单曲", "最新出的", "最新", "流行歌曲", "老歌", "新歌", "单曲", "神曲",
    "主题曲", "片头曲", "片尾曲", "背景音乐", "原声带", "配乐", "插曲", "原声", "ost", "bgm",
    "现场版", "演唱会版", "live版", "原版", "无损版", "高清版",
    # 年代/时间/版本
    "当年的", "以前的", "曾经的", "小时候听的", "那时候的", "早期的", "当年", "曾经", "以前",
    # 谓语/演唱行为修饰
    "唱的那首", "唱的这首", "演唱的那首", "演唱的这首", "唱的", "演唱的", "表演的", "翻唱的", "改编的", "原唱的", "合唱的",
    "演唱", "原唱", "翻唱", "合唱", "唱得", "唱",
    # 冗余通用词
    "这首歌曲", "这首歌", "歌曲", "音乐", "曲目", "单曲", "歌",
    # 程度副词
    "特别", "非常", "格外", "相当", "超级", "挺", "很", "比较",
    # 引导连接词
    "名字叫", "名为", "叫做", "叫", "是", "为"
]
MODIFIERS_LIST.sort(key=len, reverse=True)

MODIFIERS_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(m) for m in MODIFIERS_LIST) + r")\s*",
    re.IGNORECASE
)

ARTIST_CLEANER_PATTERN = re.compile(
    r"(?:"
    r"^(?:一下|一首|首|个|点|曲|歌手|音乐人|组合|乐队)\s*|"
    r"(?:\d{4}年(?:出的?|发行的?|发布的?|发表的?)?)$|"
    r"\s*(?:" + "|".join(re.escape(m) for m in MODIFIERS_LIST) + r")$"
    r")",
    re.IGNORECASE
)

MIDDLE_MODIFIERS = [m for m in MODIFIERS_LIST if len(m) >= 2 and m not in {"特别", "非常", "格外", "相当", "超级", "比较", "单曲", "歌曲", "音乐", "曲目"}]
MIDDLE_MODIFIERS.sort(key=len, reverse=True)

NOT_SONG_NAMES = {"音乐", "歌曲", "歌", "声音", "音量", "伴奏", "下一首", "上一首"}

CORRECTION_PREFIX_PATTERNS = [
    re.compile(r"^(?:不是啊?|不对啊?|不对|不是|错了啊?|给错了啊?|放错了啊?|搞错了啊?|弄错了啊?|不是这首啊?|不要这首啊?|换一首啊?)[,，!！\s]*", re.IGNORECASE),
    re.compile(r"^(?:你给错了啊?|你放错了啊?|你弄错了啊?|你搞错了啊?|你找错了啊?|给错了|放错了|弄错了|搞错了)[,，!！\s]*", re.IGNORECASE),
    re.compile(r"^(?:我说的是|我是说|我要的是|我想听的是|我叫你放的是|我让你放的是|叫你放|让你放|叫你搜|让你搜)[,，!！\s]*", re.IGNORECASE),
    re.compile(r"^(?:哎呀|哎|啊|喂|是|必须是|快给我|给我)[,，!！\s]*", re.IGNORECASE),
]

DIRECTIVE_SUFFIX_PATTERNS = [
    re.compile(r"[,，!！\s]*(?:你要去搜索本地没有|你去搜索本地没有|去搜索本地没有|你要去搜索|你去搜索|本地没有你要去搜索|去网上搜吧?|去网络搜索吧?|去网上搜一下|去网络搜一下|全网搜索吧?|去网上找找|去网上找吧?|去搜吧?|去下载吧?|去下吧?|快去搜|快去下载)$", re.IGNORECASE),
    re.compile(r"[,，!！\s]*(?:本地没有啊?|本地搜不到啊?|曲库没有啊?|曲库搜不到啊?|本地没这歌|本地没这首|没这首|没有这首|没有这歌|本地没有这个|没有这首歌)$", re.IGNORECASE),
    re.compile(r"[,，!！\s]*(?:网上有|网络上有|网上能搜到|全网有|你去搜|你去搜搜|你搜搜看|你去查查)$", re.IGNORECASE),
]

INVALID_ARTIST_SUBSTRINGS = ["不是", "错", "给", "没有", "搜索", "本地", "刚才", "刚刚", "推荐", "喜欢", "怎么", "什么", "为什么", "歌曲", "音乐", "去搜", "曲库"]

INVALID_ARTIST_EXACT = {
    "迷人", "动听", "好听", "难听", "优美", "伤感", "悲伤", "欢快", "快乐",
    "温柔", "残酷", "美丽", "孤独", "最初", "最长", "不能说", "被风吹过",
    "反方向", "蒲公英", "夏天", "冬天", "盛夏", "彩虹", "春天", "秋天",
    "你", "我", "他", "她", "它", "你们", "我们", "他们", "自己", "谁", "大家",
    "你猜", "我猜", "今天", "昨天", "明天", "现在", "刚才", "刚刚", "曾经", "以前",
    "你猜我", "你猜我今天", "这", "那", "这个", "那个", "心情", "心情如何",
    "你好", "您好", "在吗", "哈喽", "谢谢", "再见"
}

KNOWN_TITLES_WITH_DE = {
    "迷人的危险", "最初的梦想", "最长的电影", "不能说的秘密", "反方向的钟",
    "夜的第七章", "蒲公英的约定", "手写的从前", "彩虹的微笑", "夏天的风",
    "冬天的秘密", "盛夏的果实", "残酷的温柔", "温柔的慈悲", "会呼吸的痛",
    "给自己的歌", "爱的代价", "爱的供养", "你的背包", "你的微笑",
    "你的答案", "你的眼神", "你的名字", "我的歌声里", "我的秘密",
    "我们的歌", "我们的爱", "该死的温柔", "风吹过的夏天", "被风吹过的夏天"
}


def is_valid_artist_name(name: str) -> bool:
    """校验提取出的歌手名是否合法真实，杜绝把对话吐槽、代词、形容词误当歌手"""
    if not name or len(name) > 10:
        return False
    if name in INVALID_ARTIST_EXACT:
        return False
    if any(ch in name for ch in "，,。！？!?；;:：\n"):
        return False
    if any(sub in name for sub in INVALID_ARTIST_SUBSTRINGS):
        return False
    return True


def clean_song_title(raw: str) -> str:
    """循环剥离所有前置修饰语、量词、定语与尾部指令"""
    text = raw.strip().strip('《》"\'“”：: -_')
    for pat in DIRECTIVE_SUFFIX_PATTERNS:
        text = pat.sub("", text).strip().strip('《》"\'“”：: -_')
    while True:
        stripped = MODIFIERS_PATTERN.sub("", text).strip().strip('《》"\'“”：: -_')
        if stripped == text:
            break
        text = stripped
    for pat in DIRECTIVE_SUFFIX_PATTERNS:
        text = pat.sub("", text).strip().strip('《》"\'“”：: -_')
    return text


def clean_artist_name(raw: str) -> str:
    """清理歌手名前缀与后置修饰语（如 '张杰唱的' -> '张杰', '周杰伦最火' -> '周杰伦', '林俊杰2008年出' -> '林俊杰'）"""
    text = raw.strip().strip('《》"\'“”：: ')
    for pat in CORRECTION_PREFIX_PATTERNS:
        text = pat.sub("", text).strip()
    while True:
        stripped = ARTIST_CLEANER_PATTERN.sub("", text).strip()
        stripped = stripped.strip('《》"\'“”：: ')
        if stripped == text:
            break
        text = stripped
    for pat in CORRECTION_PREFIX_PATTERNS:
        text = pat.sub("", text).strip()
    return text


def is_pure_modifier(text: str) -> bool:
    """检查一段文本是否完全由修饰词组成（不包含实际人名/歌名实体）"""
    t = text.strip()
    cleaned = clean_song_title(t)
    return len(cleaned) == 0


def extract_music_entity(text: str) -> Optional[Tuple[str, str]]:
    """
    智能自然语言音乐实体抽取器：支持全场景口语化句式提取
    能够将各类修饰语（代表作、最火、经典、当年、唱的、主题曲等）及口语纠错/吐槽彻底剥离，
    精确输出干净的 (artist, song)。
    """
    clean = text.strip()

    # 循环清洗口语纠错、吐槽、否定前缀 (如“不是啊 你给错了啊 是廖俊涛的歌曲谁” -> “廖俊涛的歌曲谁”)
    while True:
        changed = False
        for pat in CORRECTION_PREFIX_PATTERNS:
            new_t = pat.sub("", clean).strip()
            if new_t != clean and new_t:
                clean = new_t
                changed = True
        if not changed:
            break

    # 循环清洗尾部指令与抱怨 (如“你要去搜索本地没有”)
    while True:
        changed = False
        for pat in DIRECTIVE_SUFFIX_PATTERNS:
            new_t = pat.sub("", clean).strip()
            if new_t != clean and new_t:
                clean = new_t
                changed = True
        if not changed:
            break

    # 1. 匹配标准指令前缀并去除
    cmd_prefix = re.compile(
        r"^(?:帮我|请帮我|给我|我想|我要|麻烦你?|请)?\s*"
        r"(?:播放|放|听|播|来|搜|找|点|整)\s*"
        r"(?:一下|一首|首|个|点|曲)?\s*"
        r"(?:这首歌曲|这首歌|这首|歌曲|单曲|音乐)?\s*",
        re.IGNORECASE
    )
    body = cmd_prefix.sub("", clean).strip()

    if body in NOT_SONG_NAMES or not body:
        return None

    art = ""
    song = ""

    # 句型 0: 检查是否直接命中已知含“的”经典歌名 (如“迷人的危险”)
    if body in KNOWN_TITLES_WITH_DE:
        return "", body

    # 检查是否为 [歌手] 的 [已知含“的”经典歌名] (如“周杰伦的最长的电影”, “紫薇的迷人的危险”)
    for known in KNOWN_TITLES_WITH_DE:
        if body.endswith(known) and len(body) > len(known):
            prefix = body[:-len(known)].rstrip("的 ")
            if prefix:
                prefix_art = clean_artist_name(prefix)
                if is_valid_artist_name(prefix_art):
                    return prefix_art, known
                return "", body

    # 句型 1: 包含“的”字
    if "的" in body:
        parts = body.split("的")
        cleaned_p0 = clean_artist_name(parts[0])
        # 如果第一段是纯修饰词、或者属于非法歌手名（如“迷人”、“动听”、“你猜我今天”）
        if is_pure_modifier(parts[0]) or not is_valid_artist_name(cleaned_p0):
            art = ""
            # 如果第一段不是合法歌手，整句保留为完整歌名 (如《迷人的危险》)
            song = clean_song_title(body)
        else:
            # 第一段是真实歌手（如 '周杰伦'）
            art = cleaned_p0
            rest = "的".join(parts[1:])
            song = clean_song_title(rest)

    # 句型 2: 中间包含明显的特征修饰词（如“王菲经典老歌红豆”, “周杰伦主打歌晴天”）
    else:
        found_mod = False
        for mod in MIDDLE_MODIFIERS:
            idx = body.find(mod)
            if idx > 0 and idx + len(mod) < len(body):
                left = body[:idx].strip()
                right = body[idx + len(mod):].strip()
                left_art = clean_artist_name(left)
                right_song = clean_song_title(right)
                if left_art and right_song and is_valid_artist_name(left_art) and not is_pure_modifier(left_art):
                    art = left_art
                    song = right_song
                    found_mod = True
                    break

        if not found_mod:
            # 句型 3: 书名号提取（例如：“周杰伦《晴天》”, “《晴天》”）
            if "《" in body and "》" in body:
                m = re.search(r"^(.*?)\s*《(.*?)》", body)
                if m:
                    raw_a = clean_artist_name(m.group(1))
                    art = raw_a if is_valid_artist_name(raw_a) else ""
                    song = clean_song_title(m.group(2).strip())
                else:
                    song = clean_song_title(body)
            # 句型 4: 短横线分隔（例如：“周杰伦 - 晴天”, “周杰伦-晴天”）
            elif " - " in body or ("-" in body and len(body.split("-")) == 2 and not any(ch in body for ch in "，,。！？!?")):
                sep = " - " if " - " in body else "-"
                parts = body.split(sep, 1)
                p0 = clean_artist_name(parts[0])
                p1 = clean_song_title(parts[1])
                if is_valid_artist_name(p0) and p1 and p1 not in NOT_SONG_NAMES and not is_pure_modifier(p0):
                    art = p0
                    song = p1
                else:
                    song = clean_song_title(body)
            # 句型 5: 空格分隔（例如：“周杰伦 晴天”）
            elif " " in body:
                parts = body.split(None, 1)
                p0 = clean_artist_name(parts[0])
                p1 = clean_song_title(parts[1])
                if is_valid_artist_name(p0) and p1 and p1 not in NOT_SONG_NAMES and not is_pure_modifier(p0):
                    art = p0
                    song = p1
                else:
                    song = clean_song_title(body)
            # 句型 6: 直接纯歌名输入
            else:
                song = clean_song_title(body)

    return art, song


class IntentRouter:
    """
    意图路由器 (基于 Step 4 架构要求)
    两阶段分发：
    - 正则与关键词确定性规则引擎 (极高频、低延迟、零幻觉)
    - LLM 结构化提取降级层 (复杂多变句式)
    """

    @classmethod
    def match_rule(cls, text: str) -> Optional[IntentResult]:
        clean = text.strip()
        lower = clean.lower()

        # 检查是否是指代当前已有/上一轮推荐的歌单（如：“播放你给我推荐的这份歌单的第10首歌曲”, "播放这份歌单的第十首"）
        is_referential_playlist = any(k in lower for k in [
            "你给我推荐的", "你刚才推荐的", "你推荐的", "刚才推荐的", "之前推荐的",
            "上面推荐的", "这份歌单", "这个歌单", "刚刚生成的歌单", "刚才生成的歌单",
            "生成的这份歌单", "生成的这歌单", "这歌单", "该歌单", "当前歌单", "当前列表",
            "歌单里的", "歌单中的", "歌单的第"
        ])

        # 检查是否包含生成/创建/定制新歌单语义 (例如：“给我生成一份轻松愉快歌曲的歌单”, "给我一份节奏轻快愉悦的歌单 并且播放其中第五首歌曲")
        has_playlist_kw = any(w in lower for w in ["歌单", "播放列表", "新列表"])
        has_create_act = any(w in lower for w in [
            "生成", "创建", "建", "做", "整", "推荐", "定制", "一份", "一个", "来", "给", "弄", "搞", "放点", "来点"
        ])
        is_create_playlist = (not is_referential_playlist) and (has_playlist_kw and has_create_act)

        # 匹配提取序号 (例如：“第十首”, "第10首", "第5首歌曲", "第2首歌", "最后一首")
        # 0.0 多源网络发现与下载 (例如：“全网搜索周杰伦的夜曲并下载”, "全网搜夜曲", "从网上下载反方向的钟", "下载歌曲夜曲", "网上搜晴天")
        is_net_kw = any(k in lower for k in ["全网", "网络", "网上"])
        # 严谨的下载关键词判断：绝不能因为包含“一下歌”或“下一首歌”等常规口语而误判为下载指令
        is_dl_kw = ("下载" in lower) or ("缓存" in lower) or any(k in lower for k in ["去下载", "帮我下载", "去下这首", "帮我下这首"])
        # 排除常规点歌指令（如“帮我播放一下歌曲冬眠”，应当流转至常规点歌与本地优先检索）
        is_regular_play = any(lower.startswith(p) for p in [
            "帮我播放", "请帮我播放", "给我播放", "我想播放", "我要播放",
            "帮我放", "请帮我放", "给我放", "我想听", "我要听",
            "播放", "放一下", "播一下", "听一下", "来一首", "放一首"
        ])
        if ((is_net_kw and any(w in lower for w in ["搜", "找", "检索", "查", "听", "播", "放", "下载"])) or (is_dl_kw and not is_referential_playlist)) and not is_regular_play:
            raw_target = clean
            for prefix in [
                "全网搜索", "全网检索", "全网找", "全网搜", "网络搜索", "网络检索",
                "网上搜索", "网上搜", "网上找", "从网上下载", "从网络下载", "从网上找",
                "从网络找", "从网上", "从网络", "下载歌曲", "去下载", "帮我下载", "下载", "缓存"
            ]:
                if raw_target.startswith(prefix):
                    raw_target = raw_target[len(prefix):].strip()
                    break
            for suffix in ["并下载", "且下载", "然后下载", "并播放", "且播放", "这首歌", "这首"]:
                if raw_target.endswith(suffix):
                    raw_target = raw_target[:-len(suffix)].strip()
                    break

            parsed_ent = extract_music_entity(raw_target)
            if parsed_ent and (parsed_ent[0] or parsed_ent[1]):
                art_q, song_q = parsed_ent
            else:
                art_q = ""
                song_q = clean_song_title(raw_target)

            return IntentResult(
                intent_type="NETWORK_DISCOVERY",
                action="network_discovery",
                params={
                    "query": song_q,
                    "artist": art_q,
                    "raw_text": clean,
                    "auto_download": True
                }
            )

        # 匹配提取序号 (例如：“第十首”, "第10首", "第5首歌曲", "第2首歌", "最后一首")
        ord_pattern = re.search(r"第\s*([0-9一二两三四五六七八九十]+)\s*(?:首|个|曲)(?:歌曲|歌|曲目)?", lower)
        has_last_track = any(k in lower for k in ["最后一首", "最后首", "最后那首", "最后的一首"])

        # 0. A: 生成歌单并且从指定序号起播 (例如：“给我生成一份歌单 并且播放其中的第十首歌曲”)
        if is_create_playlist:
            play_ord = None
            if ord_pattern:
                play_ord = parse_ordinal_num(ord_pattern.group(1))
            elif has_last_track:
                play_ord = -1
            params = {"raw_text": clean}
            if play_ord is not None:
                params["play_ordinal"] = play_ord
            return IntentResult(
                intent_type="SMART_PLAYLIST",
                action="smart_playlist",
                params=params
            )

        # 0. B: 歌单指定序号点播 (例如：“播放这份歌单的第十首歌曲”, "播放你给我推荐的这份歌单的第10首歌曲", "我要播放第五首", "播放第5首", "放第2首", "切到最后一首")
        if ord_pattern:
            ord_idx = parse_ordinal_num(ord_pattern.group(1))
            if ord_idx is not None:
                return IntentResult(
                    intent_type="SEARCH_AND_PLAY",
                    action="search_and_play",
                    params={"query": "", "ordinal_index": ord_idx, "is_context_referential": True}
                )
        if has_last_track:
            return IntentResult(
                intent_type="SEARCH_AND_PLAY",
                action="search_and_play",
                params={"query": "", "ordinal_index": -1, "is_context_referential": True}
            )

        # 0.1 歌词搜歌识别 (例如：“我想听有一首歌 歌词是还记得家是唯一的城堡”, "歌词是还记得你说家是唯一的城堡", "有首歌歌词有...")
        lyric_pattern = re.search(r"(?:我想听|放|搜|找|有)?(?:一首)?(?:歌)?(?:歌词(?:是|有|包含|带|叫)|歌词里有|有句歌词(?:是)?)\s*[:：]?\s*[\"“'《]?([^\s，,。！？\"'”’《》]{2,40})[\"”'》]?", clean)
        if lyric_pattern:
            lyrics_text = lyric_pattern.group(1).strip()
            if len(lyrics_text) >= 2:
                return IntentResult(
                    intent_type="SEARCH_AND_PLAY",
                    action="search_and_play",
                    params={"query": lyrics_text, "lyrics_query": lyrics_text}
                )

        # 0.2 跨轮指代消歧（最高优先级拦截，防止被误判为常规播放或 resume）
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

        # 9. 精准与全场景口语化点歌 (SEARCH_AND_PLAY)
        # 严格门禁：只有包含明确点歌/听歌动词、或者书名号、标准分隔符时，才触发规则点歌工作流；
        # 其余所有开放对话（如“你猜我今天的心情如何”、“你好”、“我今天好累”），坚决不通过规则劫持，100% 归还给大模型心智大脑！
        has_play_verb = any(v in lower for v in [
            "播放", "放一下", "播一下", "听一下", "来一首", "放一首", "播一首", "听一首",
            "我想听", "我要听", "帮我放", "请放", "给我放", "帮我播放", "请播放", "给我播放",
            "放首", "播首", "听首", "整首", "来首", "搜一下", "查一下", "找一下", "点一首", "点首",
            "唱一首", "唱首", "下载", "缓存"
        ])
        has_book_quotes = ("《" in clean and "》" in clean)
        has_song_noun = any(n in lower for n in ["歌曲", "这首歌", "那首歌", "这首", "那首", "单曲", "曲目", "伴奏", "原声"])
        has_delim = (" - " in clean) or ("-" in clean and len(clean.split("-")) == 2 and not any(ch in clean for ch in "，,。！？!?"))

        is_explicit_music_intent = has_play_verb or has_book_quotes or has_song_noun or has_delim

        if not is_explicit_music_intent:
            return None

        entity = extract_music_entity(clean)
        if entity:
            art, song = entity
            if art or song:
                return IntentResult(
                    intent_type="SEARCH_AND_PLAY",
                    action="search_and_play",
                    params={"artist": art, "query": song}
                )

        return None

    @classmethod
    async def route_intent(
        cls,
        text: str,
        llm_provider: Optional[BaseLlmProvider] = None,
        context_session = None,
        **kwargs
    ) -> IntentResult:
        """
        统一意图路由入口：
        1. 快速确定性规则
        2. 若未命中且带音乐相关词汇，由 LLM 做结构化意图槽位识别
        """
        effective_provider = llm_provider or kwargs.get("provider")
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

        suspicious_keywords = [
            "音量", "声音", "放", "停", "切", "唱", "歌", "大声", "小声",
            "静音", "循环", "收藏", "喜欢", "听", "播", "曲", "推荐", "心情", "首"
        ]
        if not any(k in text for k in suspicious_keywords) or not effective_provider:
            return IntentResult(intent_type="CHAT")

        # 若 LLM 提供者支持可用性探测且当前未启动，直接归为 CHAT，杜绝连接超时阻塞
        if hasattr(effective_provider, "check_availability"):
            if not await effective_provider.check_availability():
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
4. NETWORK_DISCOVERY (全网/网络搜索、下载曲目):
   - network_discovery: {{"query": "歌名", "artist": "歌手", "auto_download": true}}
5. CHAT (常规聊天、问答、与播放操作无关):
   - chat: {{}}

用户指令: "{text}"

请严格输出 JSON 对象，绝不要输出额外解释或 markdown 以外的文字：
{{"intent_type": "PLAYER_CONTROL|SEARCH_AND_PLAY|SMART_PLAYLIST|NETWORK_DISCOVERY|CHAT", "action": "...", "params": {{}}}}
"""
            raw = await effective_provider.chat_complete(
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
                if intent_type in ["PLAYER_CONTROL", "SEARCH_AND_PLAY", "SMART_PLAYLIST", "NETWORK_DISCOVERY"]:
                    return IntentResult(
                        intent_type=intent_type,
                        action=action,
                        params=params
                    )
        except Exception as e:
            logger.debug(f"[IntentRouter] LLM 意图降级提取异常: {e}")

        return IntentResult(intent_type="CHAT")
