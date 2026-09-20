"""
播放器控制原子工具集声明 (与 Qt ToolDispatcher 完全对应)
"""
from typing import Dict
from .base import ToolDefinition

PLAYER_TOOLS: Dict[str, ToolDefinition] = {
    "get_player_state": ToolDefinition(
        name="get_player_state",
        description="获取当前播放器的完整状态快照（包括当前歌名、歌手、专辑、是否正在播放、音量、进度等）",
        parameters={},
        is_read_only=True
    ),
    "set_volume": ToolDefinition(
        name="set_volume",
        description="调整播放器音量大小，取值范围 0 到 100",
        parameters={
            "type": "object",
            "properties": {
                "volume": {"type": "integer", "description": "目标音量值 (0-100)"},
                "delta": {"type": "integer", "description": "相对音量增减量 (如 +10, -10)"}
            }
        },
        is_read_only=False
    ),
    "pause": ToolDefinition(
        name="pause",
        description="暂停正在播放的音乐",
        parameters={},
        is_read_only=False
    ),
    "resume": ToolDefinition(
        name="resume",
        description="继续/恢复播放已暂停的音乐",
        parameters={},
        is_read_only=False
    ),
    "toggle_play": ToolDefinition(
        name="toggle_play",
        description="切换音乐播放与暂停状态",
        parameters={},
        is_read_only=False
    ),
    "next_track": ToolDefinition(
        name="next_track",
        description="切换并播放下一首歌曲",
        parameters={},
        is_read_only=False
    ),
    "previous_track": ToolDefinition(
        name="previous_track",
        description="切换并播放上一首歌曲",
        parameters={},
        is_read_only=False
    ),
    "toggle_favorite": ToolDefinition(
        name="toggle_favorite",
        description="收藏或取消收藏当前正在播放的歌曲",
        parameters={},
        is_read_only=False
    ),
    "set_play_mode": ToolDefinition(
        name="set_play_mode",
        description="设置播放模式：0=顺序播放, 1=随机播放, 2=单曲循环",
        parameters={
            "type": "object",
            "properties": {
                "mode": {"type": "integer", "enum": [0, 1, 2], "description": "播放模式编号"}
            },
            "required": ["mode"]
        },
        is_read_only=False
    ),
    "seek": ToolDefinition(
        name="seek",
        description="快进或快退至指定时间位置",
        parameters={
            "type": "object",
            "properties": {
                "position_seconds": {"type": "number", "description": "目标时间位置（秒）"},
                "position_ms": {"type": "integer", "description": "目标时间位置（毫秒）"}
            }
        },
        is_read_only=False
    )
}
