"""
MusicTaggingService 歌曲标签分析与场景情绪打标服务 (基于 Step 4 架构要求)
结合本地曲库高频曲目先验库、启发式关键词挖掘与缓存机制，
为曲目赋予 mood（情绪）、scene（场景）、energy（能量感）、language（语言）多维标签。
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

from cache.tag_cache import AgentTagCache, TagRecord

logger = logging.getLogger("AgentLogger")

# 经典曲目先验特征知识库（针对内置高品质曲目库的高置信度标定）
PRIOR_TRACK_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "稻香": {
        "mood": "治愈/欢快/温暖/励志",
        "scene": "放松/治愈/写代码/日常",
        "energy": 0.65,
        "language": "zh",
        "tags": ["周杰伦", "乡村民谣", "童年回忆", "心情愉悦", "温暖治愈"]
    },
    "晴天": {
        "mood": "怀旧/青春/治愈/轻快",
        "scene": "写代码/通勤/午后/日常",
        "energy": 0.58,
        "language": "zh",
        "tags": ["周杰伦", "校园", "青春回忆", "经典流行"]
    },
    "简单爱": {
        "mood": "欢快/甜蜜/轻松/愉悦",
        "scene": "放松/日常/约会/写代码",
        "energy": 0.62,
        "language": "zh",
        "tags": ["周杰伦", "小甜歌", "轻松浪漫", "心情愉悦"]
    },
    "告白气球": {
        "mood": "甜蜜/浪漫/轻快/愉悦",
        "scene": "约会/放松/日常",
        "energy": 0.65,
        "language": "zh",
        "tags": ["周杰伦", "甜歌", "浪漫氛围", "巴黎街头"]
    },
    "改变自己": {
        "mood": "欢快/积极/励志/活力",
        "scene": "运动/晨起/提神/写代码",
        "energy": 0.82,
        "language": "zh",
        "tags": ["王力宏", "动感流行", "环保", "充满能量"]
    },
    "离开地球表面": {
        "mood": "兴奋/高能/释放/嗨",
        "scene": "运动/健身/派对/提神",
        "energy": 0.95,
        "language": "zh",
        "tags": ["五月天", "摇滚", "燃爆", "释放压力"]
    },
    "倔强": {
        "mood": "励志/感动/热血/振奋",
        "scene": "工作/写代码/奔跑/深夜",
        "energy": 0.78,
        "language": "zh",
        "tags": ["五月天", "励志金曲", "坚持到底", "充满力量"]
    },
    "恋爱ing": {
        "mood": "欢快/热烈/甜蜜/兴奋",
        "scene": "运动/派对/聚会",
        "energy": 0.88,
        "language": "zh",
        "tags": ["五月天", "热烈", "甜歌摇滚"]
    },
    "日不落": {
        "mood": "欢快/轻快/舞曲/活力",
        "scene": "运动/跳舞/通勤/写代码",
        "energy": 0.85,
        "language": "zh",
        "tags": ["蔡依林", "复古迪斯科", "轻快节奏", "心情愉悦"]
    },
    "绿光": {
        "mood": "欢快/跳跃/希望/活力",
        "scene": "运动/日常/提神",
        "energy": 0.85,
        "language": "zh",
        "tags": ["孙燕姿", "踢踏舞风", "轻快", "希望"]
    },
    "第一天": {
        "mood": "欢快/清新/活力/明媚",
        "scene": "清晨/运动/写代码/放松",
        "energy": 0.82,
        "language": "zh",
        "tags": ["孙燕姿", "五月天合写", "明媚阳光", "新的一天"]
    },
    "知足": {
        "mood": "温暖/感动/治愈/平静",
        "scene": "助眠/散步/写代码/静心",
        "energy": 0.40,
        "language": "zh",
        "tags": ["五月天", "温暖", "慢歌", "星空治愈"]
    },
    "平凡的一天": {
        "mood": "平静/安详/治愈/温柔",
        "scene": "助眠/写代码/清晨/独处",
        "energy": 0.35,
        "language": "zh",
        "tags": ["毛不易", "人间烟火", "温柔平静", "慢生活"]
    },
    "豆浆油条": {
        "mood": "欢快/清新/温暖/轻快",
        "scene": "写代码/早餐/通勤/放松",
        "energy": 0.60,
        "language": "zh",
        "tags": ["林俊杰", "轻快中文歌", "市井温暖", "轻松惬意"]
    },
    "小酒窝": {
        "mood": "甜美/温暖/愉悦/轻快",
        "scene": "放松/写代码/约会",
        "energy": 0.52,
        "language": "zh",
        "tags": ["林俊杰", "对唱经典", "甜美微笑", "温馨"]
    },
    "江南": {
        "mood": "中国风/抒情/唯美/浪漫",
        "scene": "写代码/独处/静心",
        "energy": 0.55,
        "language": "zh",
        "tags": ["林俊杰", "中国风", "R&B", "经典"]
    },
    "夏日漱石": {
        "mood": "轻快/浪漫/惬意/清爽",
        "scene": "写代码/专注/下午茶/放松",
        "energy": 0.58,
        "language": "en",
        "tags": ["橘子海", "英伦摇滚", "夏日海风", "海边日落"]
    },
    "你要跳舞吗": {
        "mood": "欢快/释放/摇滚/嗨",
        "scene": "派对/运动/跑步/提神",
        "energy": 0.90,
        "language": "zh",
        "tags": ["新裤子", "迪斯科摇滚", "释放压力", "尽情摇摆"]
    },
    "起风了": {
        "mood": "感动/振奋/治愈/青春",
        "scene": "通勤/跑步/写代码/回忆",
        "energy": 0.72,
        "language": "zh",
        "tags": ["买辣椒也用券", "高亢激昂", "青春逆旅", "感动"]
    },
    "蓝莲花": {
        "mood": "开阔/宁静/坚定/治愈",
        "scene": "驾车/旅行/写代码/冥想",
        "energy": 0.65,
        "language": "zh",
        "tags": ["许巍", "人文摇滚", "心灵旷野", "自由清澈"]
    },
    "曾经的你": {
        "mood": "豪迈/怀旧/青春/释放",
        "scene": "驾驶/聚会/旅行",
        "energy": 0.75,
        "language": "zh",
        "tags": ["许巍", "仗剑走天涯", "赤子之心", "经典流行"]
    },
    "夜曲": {
        "mood": "华丽/感伤/古典/神秘",
        "scene": "夜晚/写代码/独处",
        "energy": 0.65,
        "language": "zh",
        "tags": ["周杰伦", "肖邦夜曲", "暗黑哥特", "封神之作"]
    },
    "青花瓷": {
        "mood": "唯美/宁静/典雅/悠远",
        "scene": "写代码/阅读/品茗/静心",
        "energy": 0.48,
        "language": "zh",
        "tags": ["周杰伦", "天青色等烟雨", "中国风代表作", "典雅"]
    },
    "大眠": {
        "mood": "深情/释怀/伤感/治愈",
        "scene": "夜晚/独处/深夜治愈",
        "energy": 0.50,
        "language": "zh",
        "tags": ["王心凌", "走心抒情", "深情释怀"]
    }
}


class MusicTaggingService:
    """本地音乐标签智能推理与打标服务"""

    def __init__(self, tag_cache: Optional[AgentTagCache] = None):
        self.tag_cache = tag_cache or AgentTagCache()

    def tag_track(self, track_path: str, title: str, artist: str = "") -> TagRecord:
        """
        获取或生成单首曲目的结构化标签：
        1. 优先查 SQLite 缓存
        2. 查内置先验知识库 (根据歌名精准命中)
        3. 启发式规则智能推导 (根据歌名、歌手语义关键词推断)
        """
        # 1. 缓存优先
        cached = self.tag_cache.get(track_path)
        if cached:
            return cached

        clean_title = title.strip()
        clean_artist = artist.strip()

        # 2. 检查先验库
        if clean_title in PRIOR_TRACK_KNOWLEDGE:
            info = PRIOR_TRACK_KNOWLEDGE[clean_title]
            record = TagRecord(
                track_path=track_path,
                title=clean_title,
                artist=clean_artist,
                mood=info["mood"],
                scene=info["scene"],
                energy=info["energy"],
                language=info["language"],
                tags=info["tags"],
                confidence=0.95,
                source="prior_knowledge"
            )
            self.tag_cache.upsert(record)
            return record

        # 3. 启发式规则推导
        record = self._heuristic_tagging(track_path, clean_title, clean_artist)
        self.tag_cache.upsert(record)
        return record

    def batch_tag_tracks(self, tracks: List[Dict[str, Any]]) -> List[TagRecord]:
        """批量对曲目打标并入库"""
        results = []
        to_upsert = []
        for t in tracks:
            path = t.get("file_path", "")
            title = t.get("title", "")
            artist = t.get("artist", "")
            cached = self.tag_cache.get(path)
            if cached:
                results.append(cached)
            else:
                rec = self.tag_track(path, title, artist)
                results.append(rec)
        return results

    def _heuristic_tagging(self, track_path: str, title: str, artist: str) -> TagRecord:
        """根据歌名、歌手名称的语义特征进行多维标签启发式提取"""
        mood_tags = []
        scene_tags = []
        extra_tags = []
        energy = 0.5
        language = "zh"

        # 语言推断
        if bool(re.search(r"^[A-Za-z0-9\s\',.\-\?!]+$", title)):
            language = "en"
        elif bool(re.search(r"[\u3040-\u30ff]", title)):
            language = "ja"
        elif bool(re.search(r"[\uac00-\ud7af]", title)):
            language = "ko"
        else:
            language = "zh"

        lower_title = title.lower()

        # 欢快/开心/愉悦/轻快 词库
        upbeat_words = ["晴", "笑", "爱", "甜", "快乐", "乐", "欢", "光", "阳", "稻香", "气球", "日不落", "夏天", "第一天", "彩虹", "自由", "简单"]
        if any(w in title for w in upbeat_words):
            mood_tags.extend(["开心", "欢快", "轻快", "心情愉悦"])
            scene_tags.extend(["日常", "放松", "写代码"])
            energy = 0.65

        # 高能/摇滚/运动 词库
        rock_words = ["跳舞", "迪斯科", "摇滚", "狂欢", "热血", "怒放", "派对", "地球表面", "盛夏", "离开", "火", "魔鬼", "变"]
        if any(w in title for w in rock_words):
            mood_tags.extend(["兴奋", "嗨", "释放", "活力"])
            scene_tags.extend(["运动", "健身", "跑步", "派对", "提神"])
            energy = 0.88

        # 舒缓/安详/助眠/平静 词库
        calm_words = ["安静", "睡", "静", "平凡", "夜", "雨", "海", "梦", "慢", "云", "知足", "漫长", "雪", "青花瓷"]
        if any(w in title for w in calm_words):
            mood_tags.extend(["平静", "安详", "温柔", "治愈"])
            scene_tags.extend(["助眠", "写代码", "专注", "静心", "独处"])
            energy = 0.35

        # 感伤/伤感/失恋 词库
        sad_words = ["哭", "痛", "伤心", "可惜", "阴天", "搁浅", "黑夜", "消愁", "遗憾", "冷", "泡沫", "退后", "淘汰", "说好不哭", "结束"]
        if any(w in title for w in sad_words):
            mood_tags.extend(["感伤", "悲伤", "释怀", "深沉"])
            scene_tags.extend(["独处", "深夜", "散步"])
            energy = 0.45

        # 浪漫/甜蜜 词库
        romantic_words = ["嫁", "唯一", "喜欢", "依然爱", "我们的歌", "遇见", "暖暖", "拥抱", "甜"]
        if any(w in title for w in romantic_words):
            mood_tags.extend(["浪漫", "甜蜜", "温馨"])
            scene_tags.extend(["约会", "放松", "日常"])
            energy = 0.55

        # 默认回退
        if not mood_tags:
            mood_tags = ["流行", "轻松", "动听"]
        if not scene_tags:
            scene_tags = ["写代码", "日常", "放松"]

        if artist:
            extra_tags.append(artist)
        extra_tags.extend(mood_tags)

        return TagRecord(
            track_path=track_path,
            title=title,
            artist=artist,
            mood="/".join(list(dict.fromkeys(mood_tags))),
            scene="/".join(list(dict.fromkeys(scene_tags))),
            energy=energy,
            language=language,
            tags=list(dict.fromkeys(extra_tags)),
            confidence=0.82,
            source="heuristic"
        )

    def calculate_match_score(
        self,
        record: TagRecord,
        target_mood: str = "",
        target_scene: str = "",
        target_language: str = "",
        target_artist: str = ""
    ) -> float:
        """
        计算单首曲目与用户期望的场景、心情和语言标签之间的匹配契合度得分 (0.0 - 100.0)
        """
        score = 20.0  # 基础分

        # 1. 情绪契合度 (按多关键词命中累加，最高 40 分)
        if target_mood:
            keywords = [k for k in re.split(r"[/,，\s]+", target_mood) if k]
            matched_mood_weight = 0.0
            for kw in keywords:
                if kw in record.mood:
                    matched_mood_weight += 1.0
                elif any(kw in t for t in record.tags):
                    matched_mood_weight += 1.0
                elif any(syn in record.mood for syn in ["欢快", "轻快", "开心", "治愈"] if kw in ["愉悦", "高兴", "开心", "心情好", "治愈", "轻松"]):
                    matched_mood_weight += 0.8
                elif any(syn in record.mood for syn in ["平静", "温柔", "安详"] if kw in ["助眠", "放松", "安静", "舒缓"]):
                    matched_mood_weight += 0.8
            score += min(40.0, matched_mood_weight * 16.0)

        # 2. 场景契合度 (最高 30 分)
        if target_scene:
            scene_keys = [k for k in re.split(r"[/,，\s]+", target_scene) if k]
            matched_scene_weight = 0.0
            for sk in scene_keys:
                if sk in record.scene:
                    matched_scene_weight += 1.0
                elif any(sk in t for t in record.tags):
                    matched_scene_weight += 1.0
                elif (sk in ["编程", "写代码", "工作", "专注", "学习"]) and ("写代码" in record.scene or "专注" in record.scene):
                    matched_scene_weight += 0.9
                elif (sk in ["运动", "跑步", "健身"]) and ("运动" in record.scene or "健身" in record.scene or record.energy > 0.75):
                    matched_scene_weight += 0.9
                elif (sk in ["助眠", "睡觉", "催眠"]) and ("助眠" in record.scene or record.energy < 0.45):
                    matched_scene_weight += 0.9
            score += min(30.0, matched_scene_weight * 15.0)

        # 3. 语言契合度 (最高 15 分)
        if target_language:
            if target_language.lower() in ["zh", "中文", "国语", "华语"] and record.language == "zh":
                score += 15.0
            elif target_language.lower() in ["en", "英文", "英语"] and record.language == "en":
                score += 15.0
            elif target_language.lower() in ["ja", "日文", "日语"] and record.language == "ja":
                score += 15.0

        # 4. 指定歌手加分 (最高 20 分)
        if target_artist and target_artist.lower() in record.artist.lower():
            score += 20.0

        return min(100.0, score)
