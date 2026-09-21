"""
本地搜歌与点歌确定性工作流 (基于 Step 4 架构要求)
实现精准歌名点歌、歌手范围点歌、模糊检索，以及跨轮上下文指代歌曲开播（如“你给我播放呀”）。
"""
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from .base import BaseWorkflow, WorkflowOutput

if TYPE_CHECKING:
    from runtime.agent_runtime import AgentRuntime

logger = logging.getLogger("AgentLogger")


class SearchAndPlayWorkflow(BaseWorkflow):
    """本地精准/模糊搜歌与即时播放工作流"""

    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime

    async def execute(
        self,
        session_id: str,
        request_id: str,
        query: str = "",
        artist: str = "",
        raw_text: str = "",
        **kwargs
    ) -> WorkflowOutput:
        session_ctx = self.runtime.context_manager.get_session(session_id)

        # 1. 跨轮指代消歧：如果 query 为空或泛词，尝试从上下文解析提及的歌曲
        clean_query = query.strip()
        if not clean_query or clean_query in ["这首歌", "那首歌", "刚刚说的歌", "上一首推荐的"]:
            resolved = session_ctx.resolve_song_from_context(raw_text or clean_query)
            if resolved:
                logger.info(f"[SearchAndPlayWorkflow] 成功从上下文解析出目标歌曲: {resolved}")
                clean_query = resolved

        # 若仍无法解析出歌名，且没有指定歌手，则默认选曲或引导用户
        if not clean_query and not artist:
            # 检查是否有近期推荐实体
            if session_ctx.last_recommended_tracks:
                clean_query = session_ctx.last_recommended_tracks[0].get("title", "")

        search_keyword = clean_query or artist
        logger.info(f"[SearchAndPlayWorkflow] 检索本地曲库: query='{clean_query}', artist='{artist}'")

        # 2. 调用 Qt 端 search_local_music 原子工具
        search_reply = await self.runtime.call_client_tool(
            session_id=session_id,
            tool_name="search_local_music",
            arguments={"query": search_keyword, "limit": 10},
            timeout=4.0
        )

        success = search_reply.get("success", False)
        error_str = search_reply.get("error", "")
        res_data = search_reply.get("result", {})
        tracks = res_data.get("tracks", [])

        if not success or not tracks:
            logger.warning(f"[SearchAndPlayWorkflow] 本地未检索到曲目: {search_keyword}")
            tool_card = {
                "name": "曲库检索",
                "action": "search_local_music",
                "params": f"关键字: {search_keyword}",
                "status": "failed",
                "result": "本地曲库暂未收录该曲目"
            }
            ans = (
                f"在本地音乐库中暂未找到「{search_keyword}」相关的歌曲 😥\n\n"
                f"💡 提示：多源网络音乐检索与自动下载入库将在 Step 5 接入！\n"
                f"目前您可以对我说「播放晴天」或「放一首周杰伦的歌」来聆听本地曲库已有的经典歌曲哦 🎵"
            )
            return WorkflowOutput(answer_text=ans, tools=[tool_card], success=False)

        # 3. 选定目标歌曲
        target_track = tracks[0]
        # 如果指定了歌手，优先在结果中过滤出该歌手的作品
        if artist:
            for t in tracks:
                if artist.lower() in t.get("artist", "").lower():
                    target_track = t
                    break

        target_idx = target_track.get("index", -1)
        target_title = target_track.get("title", clean_query)
        target_artist = target_track.get("artist", "")

        # 4. 调用 Qt 端 play_local_track 开播
        play_reply = await self.runtime.call_client_tool(
            session_id=session_id,
            tool_name="play_local_track",
            arguments={"index": target_idx},
            timeout=4.0
        )

        play_success = play_reply.get("success", False)
        if not play_success:
            play_err = play_reply.get("error", "播放器载入失败")
            tool_card = {
                "name": "本地点歌",
                "action": "play_local_track",
                "params": f"《{target_title}》- {target_artist}",
                "status": "failed",
                "result": f"开播失败: {play_err}"
            }
            return WorkflowOutput(
                answer_text=f"找到了《{target_title}》，但播放器启动失败：{play_err} 🥺",
                tools=[tool_card],
                success=False
            )

        # 5. 更新上下文实体槽位
        session_ctx.record_played_track(target_track)
        session_ctx.record_recommended_tracks([target_track])

        # 6. 构造规范 ToolCard 与应答
        artist_display = f" - {target_artist}" if target_artist else ""
        tool_card = {
            "name": "本地点歌",
            "action": "play_local_track",
            "params": f"《{target_title}》{artist_display}",
            "status": "success",
            "result": f"已为你载入并开播《{target_title}》"
        }
        ans = f"好的，已为你播放《{target_title}》{artist_display} 🎵 快戴上耳机享受美妙音乐吧！"
        return WorkflowOutput(answer_text=ans, tools=[tool_card], success=True)
