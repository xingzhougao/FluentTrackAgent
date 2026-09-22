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

        # 1. 歌单指定序号快速点播 (例如：“播放这份歌单的第十首歌曲”, "我要播放第五首", "播放第5首", "切到最后一首")
        ordinal_idx = kwargs.get("ordinal_index", None)
        if ordinal_idx is not None:
            target_track = None
            disp_num = ordinal_idx + 1 if ordinal_idx >= 0 else 1
            rec_len = len(session_ctx.last_recommended_tracks) if session_ctx.last_recommended_tracks else 0

            if rec_len > 0:
                if ordinal_idx == -1 or ordinal_idx >= rec_len:
                    target_track = session_ctx.last_recommended_tracks[-1]
                    disp_num = rec_len
                else:
                    target_track = session_ctx.last_recommended_tracks[ordinal_idx]
                    disp_num = ordinal_idx + 1

            target_idx = target_track.get("index", -1) if target_track else -1
            target_path = target_track.get("file_path", "") if target_track else ""
            target_title = target_track.get("title", "") if target_track else ""
            target_artist = target_track.get("artist", "") if target_track else ""

            logger.info(f"[SearchAndPlayWorkflow] 按歌单序号第 {disp_num} 首点播: 《{target_title}》 (index={target_idx})")

            call_args = {"playlist_index": disp_num - 1}
            if target_idx >= 0:
                call_args["index"] = target_idx
            if target_path:
                call_args["file_path"] = target_path

            play_reply = await self.runtime.call_client_tool(
                session_id=session_id,
                tool_name="play_local_track",
                arguments=call_args,
                timeout=4.0
            )

            if play_reply.get("success"):
                res_info = play_reply.get("result", {})
                if not target_title:
                    target_title = res_info.get("title", f"第 {disp_num} 首")
                if not target_artist:
                    target_artist = res_info.get("artist", "")
                if target_track:
                    session_ctx.record_played_track(target_track)
                art_disp = f" - {target_artist}" if target_artist else ""
                tool_card = {
                    "name": "歌单选曲",
                    "action": "play_local_track",
                    "params": f"第 {disp_num} 首: 《{target_title}》{art_disp}",
                    "status": "success",
                    "result": f"已为你播放歌单中的第 {disp_num} 首《{target_title}》"
                }
                ans = f"好的，已为你切换并播放歌单中的第 {disp_num} 首：《{target_title}》{art_disp} 🎵"
                return WorkflowOutput(answer_text=ans, tools=[tool_card], success=True)

        # 2. 歌词搜歌与识别处理 (例如："我想听有一首歌 歌词是还记得家是唯一的城堡")
        lyrics_query = kwargs.get("lyrics_query", "")
        if lyrics_query:
            logger.info(f"[SearchAndPlayWorkflow] 正在执行歌词搜歌: '{lyrics_query}'")
            search_reply = await self.runtime.call_client_tool(
                session_id=session_id,
                tool_name="search_local_music",
                arguments={"query": lyrics_query, "limit": 5},
                timeout=4.0
            )
            tracks = search_reply.get("result", {}).get("tracks", []) if search_reply.get("success") else []

            matched_track = None
            for t in tracks:
                if t.get("matched_lyric"):
                    matched_track = t
                    break
            if not matched_track and tracks:
                matched_track = tracks[0]

            # 若本地 .lrc 未直接匹配，调用 LLM 进行歌词常识联想
            if not matched_track:
                try:
                    provider = self.runtime.llm_manager.get_provider()
                    prompt = f"""用户在寻找一首歌，只记得歌词片段: "{lyrics_query}"。
请分析这句歌词出自哪首歌曲及歌手。
请严格以 JSON 格式输出，不要有任何多余文字：
{{"title": "歌名", "artist": "歌手"}}
"""
                    from llm.base import ChatMessage
                    import json
                    llm_ans = await provider.chat_complete([ChatMessage(role="user", content=prompt)], temperature=0.1)
                    if "{" in llm_ans and "}" in llm_ans:
                        data = json.loads(llm_ans[llm_ans.index("{"):llm_ans.rindex("}")+1])
                        inferred_title = data.get("title", "").strip()
                        inferred_artist = data.get("artist", "").strip()
                        if inferred_title:
                            logger.info(f"[SearchAndPlayWorkflow] LLM 歌词联想成功: 《{inferred_title}》- {inferred_artist}")
                            sub_search = await self.runtime.call_client_tool(
                                session_id=session_id,
                                tool_name="search_local_music",
                                arguments={"query": inferred_title, "limit": 5},
                                timeout=4.0
                            )
                            sub_tracks = sub_search.get("result", {}).get("tracks", []) if sub_search.get("success") else []
                            if sub_tracks:
                                matched_track = sub_tracks[0]
                except Exception as e:
                    logger.debug(f"LLM 歌词联想失败: {e}")

            if matched_track:
                target_idx = matched_track.get("index", -1)
                target_title = matched_track.get("title", "")
                target_artist = matched_track.get("artist", "")
                matched_line = matched_track.get("matched_lyric", "")

                play_reply = await self.runtime.call_client_tool(
                    session_id=session_id,
                    tool_name="play_local_track",
                    arguments={"index": target_idx},
                    timeout=4.0
                )
                if play_reply.get("success"):
                    session_ctx.record_played_track(matched_track)
                    session_ctx.record_recommended_tracks([matched_track])

                    lyric_tip = f" (对应歌词: 「{matched_line}」)" if matched_line else ""
                    tool_card = {
                        "name": "歌词识曲",
                        "action": "play_local_track",
                        "params": f"《{target_title}》- {target_artist}{lyric_tip}",
                        "status": "success",
                        "result": f"已识别歌词并开播《{target_title}》"
                    }
                    ans = (
                        f"通过歌词「{lyrics_query}」为你识别并开播了 {target_artist} 的《{target_title}》🎵\n"
                        f"{'（匹配原句：' + matched_line + '）\n' if matched_line else ''}"
                        f"经典旋律已经响起，快戴上耳机尽情享受吧！✨"
                    )
                    return WorkflowOutput(answer_text=ans, tools=[tool_card], success=True)

        # 3. 跨轮指代消歧：如果 query 为空或泛词，尝试从上下文解析提及的歌曲
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
            logger.info(f"[SearchAndPlayWorkflow] 本地未检索到曲目: '{search_keyword}'，自动流转至网络多源发现工作流")
            if hasattr(self.runtime, "network_discovery_workflow") and self.runtime.network_discovery_workflow:
                return await self.runtime.network_discovery_workflow.execute(
                    session_id=session_id,
                    request_id=request_id,
                    query=clean_query,
                    artist=artist,
                    auto_download=True,
                    raw_text=raw_text,
                    **kwargs
                )

            tool_card = {
                "name": "曲库检索",
                "action": "search_local_music",
                "params": f"关键字: {search_keyword}",
                "status": "failed",
                "result": "本地曲库暂未收录该曲目"
            }
            ans = f"在本地音乐库中暂未找到「{search_keyword}」相关的歌曲 😥"
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
        if not session_ctx.last_recommended_tracks or len(session_ctx.last_recommended_tracks) <= 1:
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
