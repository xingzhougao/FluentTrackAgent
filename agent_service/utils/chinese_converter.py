"""
Chinese Converter 简繁体转换工具
用于 Soulseek P2P 海外/港台无损曲库检索与元数据匹配
"""

import json
from pathlib import Path

# 加载完整 OpenCC 简繁转换字符库 (涵盖 2400+ 规范汉字)
_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "st_characters.json"
_SIMP_TO_TRAD = {}
if _DATA_FILE.exists():
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as _f:
            _SIMP_TO_TRAD = json.load(_f)
    except Exception:
        pass

# 常用简繁对照与音乐专有名词微调表（确保生僻或多音字精准映射）
_EXTRA_OVERRIDE = {
    # 音乐常用字与虚词
    '爱': '愛', '荡': '蕩', '萧': '蕭', '潇': '瀟', '伦': '倫', '没': '沒', '国': '國',
    '风': '風', '乐': '樂', '华': '華', '杰': '傑', '听': '聽', '欢': '歡', '语': '語',
    '恋': '戀', '梦': '夢', '离': '離', '开': '開', '关': '關', '点': '點', '会': '會',
    '边': '邊', '头': '頭', '间': '間', '门': '門', '见': '見', '经': '經', '动': '動',
    '现': '現', '单': '單', '选': '選', '变': '變', '阳': '陽', '怀': '懷', '伤': '傷',
    '忆': '憶', '独': '獨', '寻': '尋', '尽': '盡', '泪': '淚', '觉': '覺', '编': '編',
    '飞': '飛', '归': '歸', '传': '傳', '声': '聲', '尘': '塵', '盏': '盞', '栈': '棧',
    '难': '難', '岁': '歲', '浅': '淺', '乱': '亂', '绝': '絕', '续': '續', '终': '終',
    '绿': '綠', '蓝': '藍', '红': '紅', '银': '銀', '钱': '錢', '铁': '鐵', '钟': '鐘',
    '废': '廢', '柴': '柴', '说': '說', '么': '麼', '后': '後', '里': '裡', '发': '發'
}
_SIMP_TO_TRAD.update(_EXTRA_OVERRIDE)

_TRAD_TO_SIMP = {v: k for k, v in _SIMP_TO_TRAD.items()}


# 歌手常见同音/异体/简繁别名对照映射
ARTIST_ALIASES = {
    "萧萧": ["萧潇", "蕭瀟", "蕭蕭", "萧萧", "Xiao Xiao"],
    "萧潇": ["萧萧", "蕭瀟", "蕭蕭", "萧萧", "Xiao Xiao"],
    "蕭瀟": ["萧萧", "萧潇", "蕭蕭", "Xiao Xiao"],
    "胡歌": ["胡歌", "Hu Ge", "Hugh Hu"],
    "周杰伦": ["周杰倫", "Jay Chou", "Jay"],
    "林俊杰": ["林俊傑", "JJ Lin", "JJ"],
    "陈奕迅": ["陳奕迅", "Eason Chan", "Eason"],
    "王菲": ["王菲", "Faye Wong"],
    "张学友": ["張學友", "Jacky Cheung"],
    "刘德华": ["劉德華", "Andy Lau"],
    "张惠妹": ["張惠妹", "A-Mei", "aMEI"],
    "孙燕姿": ["孫燕姿", "Stefanie Sun"],
    "梁静茹": ["梁靜茹", "Fish Leong"],
    "蔡依林": ["蔡依林", "Jolin Tsai", "Jolin"],
    "王力宏": ["王力宏", "Leehom Wang"],
    "陶喆": ["陶喆", "David Tao"],
    "五月天": ["五月天", "Mayday"],
    "苏打绿": ["蘇打綠", "Sodagreen", "鱼丁糸", "魚丁糸"],
    "邓紫棋": ["鄧紫棋", "G.E.M.", "GEM"],
    "华晨宇": ["華晨宇", "Hua Chenyu"],
    "薛之谦": ["薛之謙", "Joker Xue"],
    "李荣浩": ["李榮浩", "Ronghao Li"],
    "毛不易": ["毛不易", "Mao Buyi"],
    "周深": ["周深", "Charlie Zhou"],
    "许嵩": ["許嵩", "Vae"],
    "汪苏泷": ["汪蘇瀧", "Silence Wang"]
}


def to_traditional(text: str) -> str:
    """转换为标准繁体"""
    if not text:
        return ""
    return "".join(_SIMP_TO_TRAD.get(ch, ch) for ch in text)


def to_simplified(text: str) -> str:
    """转换为标准简体"""
    if not text:
        return ""
    return "".join(_TRAD_TO_SIMP.get(ch, ch) for ch in text)


def get_artist_variations(artist: str) -> list[str]:
    """获取歌手的所有别名及简繁体变形"""
    if not artist:
        return []
    art = artist.strip()
    variations = {art, to_traditional(art), to_simplified(art)}
    for k, aliases in ARTIST_ALIASES.items():
        if art.lower() == k.lower() or art.lower() in [a.lower() for a in aliases]:
            for a in aliases:
                variations.add(a)
                variations.add(to_traditional(a))
                variations.add(to_simplified(a))
    return [v for v in variations if v]
