"""
SmartPlaylistWorkflow 场景与情绪智能歌单工作流 (基于 Step 4 架构要求)
实现：意图解析 -> 本地初筛 -> 标签加权 -> 候选排序 -> 歌单生成/开播全确定性闭环。
支持：
- 情绪治愈单曲即时推荐开播（如“我今天有点不开心 给我播放一首能让我心情愉悦的歌曲”）
- 多维场景智能歌单生成与连续播放（如“我要写代码了，来几首轻快的中文歌”）
"""
import re
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from .base import BaseWorkflow, WorkflowOutput
from services.music_tagging_service import MusicTaggingService
from cache.tag_cache import AgentTagCache

if TYPE_CHECKING:
    from runtime.agent_runtime import AgentRuntime

logger = logging.getLogger("AgentLogger")


class SmartPlaylistWorkflow(BaseWorkflow):
    """智能场景与情绪推荐工作流"""

    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime
        self.tagging_service = MusicTaggingService()

    async def execute(
        self,
        session_id: str,
        request_id: str,
        mood: str = "",
        scene: str = "",
        language: str = "",
        artist: str = "",
        count: int = 1,
        raw_text: str = "",
        **kwargs
    ) -> WorkflowOutput:
        session_ctx = self.runtime.context_manager.get_session(session_id)
        clean_text = raw_text.strip()

        # 1. 语义特征提取补全
        resolved_mood = mood
        resolved_scene = scene
        resolved_lang = language
        resolved_count = count

        # 情绪特征推导
        if any(w in clean_text for w in ["不开心", "难过", "伤心", "郁闷", "烦躁", "丧", "压抑"]):
            resolved_mood = "治愈/愉悦/轻松"
            resolved_scene = "治愈/日常"
        elif any(w in clean_text for w in ["心情愉悦", "高兴", "开心", "欢快", "快乐", "愉悦"]):
            resolved_mood = "开心/欢快/轻快"
            resolved_scene = "日常/放松"
        elif any(w in clean_text for w in ["助眠", "睡觉", "失眠", "催眠", "安静点", "静一静"]):
            resolved_mood = "平静/安详/温柔"
            resolved_scene = "助眠"
            if "一首" not in clean_text:
                resolved_count = 5

        # 场景特征推导
        if any(w in clean_text for w in ["写代码", "编程", "敲代码", "工作", "专注", "办公", "学习"]):
            resolved_scene = "写代码/专注"
            if not resolved_mood:
                resolved_mood = "轻快/平静"
            if "一首" not in clean_text:
                resolved_count = 5
        elif any(w in clean_text for w in ["运动", "跑步", "健身", "锻炼", "打球"]):
            resolved_scene = "运动/健身"
            if not resolved_mood:
                resolved_mood = "活力/高能"
            if "一首" not in clean_text:
                resolved_count = 5

        # 语言特征
        if any(w in clean_text for w in ["中文歌", "国语", "华语"]):
            resolved_lang = "zh"
        elif any(w in clean_text for w in ["英文歌", "英语"]):
            resolved_lang = "en"

        # 数量特征
        if "一首" in clean_text or "1首" in clean_text:
            resolved_count = 1
        elif any(w in clean_text for w in ["几首", "歌单", "列表", "放些", "来点"]):
            resolved_count = max(3, resolved_count)

        logger.info(f"[SmartPlaylistWorkflow] 解析意图槽位: mood='{resolved_mood}', scene='{resolved_scene}', lang='{resolved_lang}', count={resolved_count}")

        # 2. 从 Qt 客户端拉取本地曲库候选曲目
        search_reply = await self.runtime.call_client_tool(
            session_id=session_id,
            tool_name="search_local_music",
            arguments={"query": "", "limit": 100},
            timeout=5.0
        )

        success = search_reply.get("success", False)
        res_data = search_reply.get("result", {})
        tracks = res_data.get("tracks", [])

        if not success or not tracks:
            logger.error("[SmartPlaylistWorkflow] 未能获取到本地曲库曲目")
            tool_card = {
                "name": "智能歌单",
                "action": "smart_playlist",
                "params": f"场景: {resolved_scene}, 心情: {resolved_mood}",
                "status": "failed",
                "result": "本地曲库暂无可推荐的曲目"
            }
            return WorkflowOutput(
                answer_text="未能检索到本地曲库，请确认本地音乐文件夹已正确配置并包含歌曲文件哦 📂",
                tools=[tool_card],
                success=False
            )

        # 3. 标签分析与加权匹配打分
        scored_tracks: List[Tuple[float, Dict[str, Any], Any]] = []
        for t in tracks:
            path = t.get("file_path", "")
            title = t.get("title", "")
            art = t.get("artist", "")
            tag_record = self.tagging_service.tag_track(path, title, art)
            score = self.tagging_service.calculate_match_score(
                tag_record,
                target_mood=resolved_mood,
                target_scene=resolved_scene,
                target_language=resolved_lang,
                target_artist=artist
            )
            scored_tracks.append((score, t, tag_record))

        # 按综合匹配分降序排列
        scored_tracks.sort(key=lambda x: x[0], reverse=True)

        # 4. 执行开播
        if resolved_count <= 1:
            # 单曲开播模式
            top_score, best_track, top_record = scored_tracks[0]
            target_idx = best_track.get("index", 0)
            target_title = best_track.get("title", "")
            target_artist = best_track.get("artist", "")

            play_reply = await self.runtime.call_client_tool(
                session_id=session_id,
                tool_name="play_local_track",
                arguments={"index": target_idx},
                timeout=4.0
            )

            play_success = play_reply.get("success", False)
            if not play_success:
                play_err = play_reply.get("error", "开播失败")
                tool_card = {
                    "name": "智能推荐开播",
                    "action": "play_local_track",
                    "params": f"《{target_title}》- {target_artist}",
                    "status": "failed",
                    "result": f"开播失败: {play_err}"
                }
                return WorkflowOutput(answer_text=f"为你挑选了《{target_title}》，但在开播时遇到了问题：{play_err}", tools=[tool_card], success=False)

            # 更新实体上下文
            session_ctx.record_played_track(best_track)
            session_ctx.record_recommended_tracks([best_track])

            tool_card = {
                "name": "智能推荐开播",
                "action": "play_local_track",
                "params": f"《{target_title}》 - {target_artist} [{top_record.mood}]",
                "status": "success",
                "result": f"已为你载入并播放《{target_title}》"
            }

            # 针对情绪共情生成回答
            if "不开心" in clean_text or "治愈" in resolved_mood or "难过" in clean_text:
                ans = (
                    f"生活偶尔会有阴霾，但好音乐总能带来温暖与慰藉 🌤️\n\n"
                    f"为你推荐并开播了 {target_artist} 的《{target_title}》🎵。\n"
                    f"希望这首旋律轻快治愈的歌曲能赶走你的烦恼，让嘴角重新上扬，笑一个吧！☀️"
                )
            else:
                ans = f"为你挑选了最契合当前氛围的《{target_title}》- {target_artist} 🎵，已为你启动播放，祝您听歌愉快！"

            return WorkflowOutput(answer_text=ans, tools=[tool_card], success=True)

        else:
            # 多曲临时歌单生成模式
            take_n = min(len(scored_tracks), resolved_count)
            selected_items = scored_tracks[:take_n]
            selected_indices = [item[1].get("index", 0) for item in selected_items]
            selected_tracks = [item[1] for item in selected_items]

            scene_tag = resolved_scene.split("/")[0] if resolved_scene else "精选"
            mood_tag = resolved_mood.split("/")[0] if resolved_mood else "随心听"
            playlist_name = f"AI推荐: {scene_tag}{mood_tag}"

            create_reply = await self.runtime.call_client_tool(
                session_id=session_id,
                tool_name="create_temp_playlist",
                arguments={
                    "name": playlist_name,
                    "track_indices": selected_indices,
                    "auto_play": True
                },
                timeout=5.0
            )

            create_success = create_reply.get("success", False)
            if not create_success:
                err = create_reply.get("error", "歌单创建失败")
                tool_card = {
                    "name": "智能歌单生成",
                    "action": "create_temp_playlist",
                    "params": playlist_name,
                    "status": "failed",
                    "result": f"生成失败: {err}"
                }
                return WorkflowOutput(answer_text=f"生成歌单时遇到错误：{err} 🥺", tools=[tool_card], success=False)

            # 更新实体上下文（记录全部选取的曲目列表）
            session_ctx.record_recommended_tracks(selected_tracks)
            if selected_tracks:
                session_ctx.record_played_track(selected_tracks[0])

            first_track_title = selected_tracks[0].get("title", "") if selected_tracks else ""
            tool_card = {
                "name": "智能歌单生成",
                "action": "create_temp_playlist",
                "params": f"「{playlist_name}」 (收录 {len(selected_indices)} 首)",
                "status": "success",
                "result": f"已创建歌单并自动开播第一首《{first_track_title}》"
            }

            song_list_text = "\n".join([
                f"{i+1}. 《{item[1].get('title', '')}》 - {item[1].get('artist', '')}"
                for i, item in enumerate(selected_items)
            ])

            ans = (
                f"已为你精心定制了专属智能歌单「{playlist_name}」，并已从第一首启动播放 🎧\n\n"
                f"**歌单曲目清单：**\n{song_list_text}\n\n"
                f"祝你享受这段愉快的音乐时光！如需切歌或调整，随时吩咐我哦 ✨"
            )

            return WorkflowOutput(answer_text=ans, tools=[tool_card], success=True)
