"""
播放控制确定性工作流 (基于架构审查第 3 项：PlayerCommandWorkflow)
"""
import logging
from typing import Dict, Any, TYPE_CHECKING
from .base import BaseWorkflow, WorkflowOutput

if TYPE_CHECKING:
    from runtime.agent_runtime import AgentRuntime

logger = logging.getLogger("AgentLogger")


class PlayerCommandWorkflow(BaseWorkflow):
    """
    负责执行所有确定性的播放器硬件级控制指令，
    通过 WebSocket 派发 tool_request，同步等待 C++ 执行回执 tool_result，
    并组装 AgentToolCard 与自然语言应答。
    """

    def __init__(self, runtime: "AgentRuntime"):
        self.runtime = runtime

    async def execute(
        self,
        session_id: str,
        request_id: str,
        action: str = "",
        params: Dict[str, Any] = None,
        **kwargs
    ) -> WorkflowOutput:
        params = params or {}
        logger.info(f"[PlayerCommandWorkflow] 开始执行动作: {action}, 参数: {params}")

        # 向 Qt 客户端下发原子工具调用并等待回执
        tool_reply = await self.runtime.call_client_tool(
            session_id=session_id,
            tool_name=action,
            arguments=params,
            timeout=4.0
        )

        success = tool_reply.get("success", False)
        error_str = tool_reply.get("error", "")
        res_data = tool_reply.get("result", {})

        if not success:
            logger.error(f"[PlayerCommandWorkflow] 工具执行失败: {error_str}")
            tool_card = {
                "name": "播放控制",
                "action": action,
                "params": str(params) if params else "",
                "status": "failed",
                "result": f"执行失败: {error_str}"
            }
            return WorkflowOutput(
                answer_text=f"抱歉，操作未能成功完成：{error_str} 😥",
                tools=[tool_card],
                success=False,
                error=error_str
            )

        # 执行成功：根据具体 action 生成规范卡片与友好自然语言
        if action == "set_volume":
            curr_vol = res_data.get("current_volume", 50)
            prev_vol = res_data.get("previous_volume", curr_vol)
            tool_card = {
                "name": "音量调节",
                "action": "set_volume",
                "params": f"设置音量: {curr_vol}%",
                "status": "success",
                "result": f"音量已由 {prev_vol}% 调整为 {curr_vol}%"
            }
            ans = f"好的，已将播放器音量调整为 {curr_vol}% 啦 🔊"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "pause":
            tool_card = {
                "name": "播放控制",
                "action": "pause",
                "params": "暂停播放",
                "status": "success",
                "result": "已暂停当前播放"
            }
            ans = "音乐已为你暂停，随时对我说「继续播放」恢复哦 ⏸️"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "resume":
            tool_card = {
                "name": "播放控制",
                "action": "resume",
                "params": "继续播放",
                "status": "success",
                "result": "已恢复音乐播放"
            }
            ans = "音乐已恢复播放，继续享受美妙时光吧 ▶️"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "next_track":
            title = res_data.get("title", "下一首")
            artist = res_data.get("artist", "")
            title_display = f"《{title}》" if title else "下一首歌曲"
            by_artist = f" - {artist}" if artist else ""
            tool_card = {
                "name": "切歌控制",
                "action": "next_track",
                "params": "下一首",
                "status": "success",
                "result": f"已切至: {title_display}{by_artist}"
            }
            ans = f"已为你切换到下一首：{title_display}{by_artist} ⏭️"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "previous_track":
            title = res_data.get("title", "上一首")
            artist = res_data.get("artist", "")
            title_display = f"《{title}》" if title else "上一首歌曲"
            by_artist = f" - {artist}" if artist else ""
            tool_card = {
                "name": "切歌控制",
                "action": "previous_track",
                "params": "上一首",
                "status": "success",
                "result": f"已切回: {title_display}{by_artist}"
            }
            ans = f"已为你切回上一首：{title_display}{by_artist} ⏮️"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "toggle_favorite":
            is_fav = res_data.get("is_favorite", False)
            title = res_data.get("title", "当前歌曲")
            if is_fav:
                tool_card = {
                    "name": "歌曲收藏",
                    "action": "toggle_favorite",
                    "params": f"《{title}》",
                    "status": "success",
                    "result": "已添加到「我喜欢」"
                }
                ans = f"已将《{title}》添加到您的「我喜欢」歌单中 ❤️"
            else:
                tool_card = {
                    "name": "歌曲收藏",
                    "action": "toggle_favorite",
                    "params": f"《{title}》",
                    "status": "success",
                    "result": "已从「我喜欢」中移除"
                }
                ans = f"已从「我喜欢」歌单中取消了对《{title}》的收藏 🤍"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "get_player_state":
            title = res_data.get("title", "")
            artist = res_data.get("artist", "")
            album = res_data.get("album", "")
            playing = res_data.get("playing", False)
            vol = res_data.get("volume", 50)
            is_fav = res_data.get("is_favorite", False)

            if not title:
                tool_card = {
                    "name": "状态查询",
                    "action": "get_player_state",
                    "params": "播放器状态",
                    "status": "success",
                    "result": "当前播放器未载入曲目"
                }
                ans = "当前播放器暂未载入任何歌曲，你可以点一首歌或在本地曲库挑一首开播哦 🎶"
            else:
                fav_tag = " (已收藏 ❤️)" if is_fav else ""
                status_tag = "正在播放" if playing else "已暂停"
                tool_card = {
                    "name": "曲目信息",
                    "action": "get_player_state",
                    "params": f"《{title}》 - {artist}",
                    "status": "success",
                    "result": f"状态: {status_tag}, 音量: {vol}%{fav_tag}"
                }
                album_info = f"，收录于专辑《{album}》" if album else ""
                ans = f"当前{status_tag}的是 {artist} 的《{title}》{album_info}，当前音量为 {vol}%{fav_tag} 🎵"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        elif action == "set_play_mode":
            mode = res_data.get("play_mode", 0)
            mode_names = {0: "顺序播放", 1: "随机播放", 2: "单曲循环"}
            mode_name = mode_names.get(mode, "顺序播放")
            tool_card = {
                "name": "播放模式",
                "action": "set_play_mode",
                "params": f"模式: {mode_name}",
                "status": "success",
                "result": f"已设置为【{mode_name}】"
            }
            ans = f"已为你切换播放模式为【{mode_name}】 🔁"
            return WorkflowOutput(answer_text=ans, tools=[tool_card])

        # 兜底
        tool_card = {
            "name": "控制执行",
            "action": action,
            "params": str(params),
            "status": "success",
            "result": "操作已完成"
        }
        return WorkflowOutput(answer_text="指令已成功执行完成！✨", tools=[tool_card])
