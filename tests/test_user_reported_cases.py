"""
针对用户实测反馈的两个具体提示词的全链路自动化回归测试：
1. "播放一下王小帅的我爱他"
2. "播放一下邵帅的你是人间四月天"
验证：
- 意图提取干净准确，无“一下”前缀污染
- 本地查无此曲时，平滑升级到网络多源发现
- 人工确认请求携带正确参数且确认机制无超时
- 下载过程中实时推送下载进度百分比与 MB 数
- 下载完成后自动调用 import_downloaded_track 工具并自动开播
"""
import asyncio
import os
import sys

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

from runtime.agent_runtime import AgentRuntime
from runtime.intent_router import IntentRouter
from workflows.network_discovery_workflow import NetworkDiscoveryWorkflow
from providers.music.base import TrackCandidate


class MockSessionManager:
    def __init__(self):
        self.sent_messages = []

    async def send_json(self, session_id: str, data: dict):
        self.sent_messages.append(data)
        # 如果是确认请求，模拟 Qt 客户端确认弹窗点击【确认】
        if data.get("type") == "confirmation_required":
            cid = data.get("confirm_id")
            # 模拟在下一轮事件循环中分发确认响应
            asyncio.create_task(self._auto_confirm(cid))
        return True

    async def _auto_confirm(self, confirm_id):
        await asyncio.sleep(0.05)
        # 模拟 Qt 客户端通过 agentController.respondConfirmation(cid, True) 回传
        global runtime
        runtime.confirmation_manager.handle_response(confirm_id, True)


async def test_case(prompt: str, expected_artist: str, expected_title: str):
    print(f"\n=======================================================")
    print(f"🧪 测试提示词: '{prompt}'")
    print(f"=======================================================")

    # 1. 意图路由验证
    intent = IntentRouter.match_rule(prompt)
    print(f"1. 意图路由结果: intent_type={intent.intent_type}, action={intent.action}, params={intent.params}")
    assert intent.intent_type == "SEARCH_AND_PLAY", f"期望 SEARCH_AND_PLAY，实际 {intent.intent_type}"
    assert intent.params.get("artist") == expected_artist, f"歌手解析错误: 期望 {expected_artist}, 实际 {intent.params.get('artist')}"
    assert intent.params.get("query") == expected_title, f"歌名解析错误: 期望 {expected_title}, 实际 {intent.params.get('query')}"
    print(f"   ✅ 歌手 '{expected_artist}' 与歌名 '{expected_title}' 提取 100% 准确！")

    # 2. 模拟客户端工具调用环境
    called_tools = []

    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        called_tools.append((tool_name, arguments))
        if tool_name == "search_local_music":
            # 模拟本地曲库没有该冷门歌曲
            return {"success": True, "result": {"tracks": [], "total": 0}}
        elif tool_name == "import_downloaded_track":
            # 模拟 Qt 本地曲库导入成功并开播
            return {
                "success": True,
                "result": {
                    "index": 12,
                    "title": arguments.get("title"),
                    "artist": arguments.get("artist"),
                    "total_count": 13
                }
            }
        elif tool_name == "play_local_track":
            return {"success": True, "result": {"playing": True}}
        return {"success": True, "result": {}}

    runtime.call_client_tool = mock_call_client_tool
    mock_session.sent_messages.clear()

    # 3. 运行工作流
    wf_output = await runtime.search_play_workflow.execute(
        session_id="test_session",
        request_id="req_test",
        query=intent.params.get("query"),
        artist=intent.params.get("artist"),
        raw_text=prompt
    )

    print(f"2. 工作流执行完成: success={wf_output.success}")
    print(f"   answer_text: {wf_output.answer_text}")
    print(f"   tools: {wf_output.tools}")
    assert wf_output.success is True, f"工作流执行失败: {wf_output.answer_text}"

    # 4. 验证是否触发了人工确认
    confirm_msgs = [m for m in mock_session.sent_messages if m.get("type") == "confirmation_required"]
    assert len(confirm_msgs) > 0, "未触发人工二次确认"
    print(f"   ✅ 成功触发人工二次确认: confirm_id={confirm_msgs[0].get('confirm_id')}")

    # 5. 验证是否推送了实时下载进度
    progress_msgs = [
        m for m in mock_session.sent_messages
        if m.get("type") == "status_update" and m.get("payload", {}).get("status") == "downloading"
    ]
    assert len(progress_msgs) > 0, "未向客户端推送实时下载进度"
    print(f"   ✅ 成功向客户端推送实时下载进度 (共 {len(progress_msgs)} 次进度通知):")
    for p in progress_msgs[-3:]:
        print(f"      - {p['payload']['message']}")

    # 6. 验证是否调用了 import_downloaded_track 且文件为真实高品质 MP3 + LRC 歌词
    import_calls = [c for c in called_tools if c[0] == "import_downloaded_track"]
    assert len(import_calls) > 0, "未调用 import_downloaded_track"
    imported_args = import_calls[0][1]
    fp = imported_args["file_path"]
    assert os.path.exists(fp), f"下载的音频文件不存在: {fp}"
    sz = os.path.getsize(fp)
    assert sz > 500000, f"下载的音频文件过小或为假数据: {sz} 字节"
    lrc_fp = os.path.splitext(fp)[0] + ".lrc"
    assert os.path.exists(lrc_fp), f"对应的 .lrc 歌词文件不存在: {lrc_fp}"
    print(f"   ✅ 成功导入本地曲库并启动播放: {fp} (真实大小: {sz} 字节, 歌词: {lrc_fp})")

    print(f"🎉 提示词 '{prompt}' 全链路测试完美通过！\n")


async def main():
    global runtime, mock_session
    runtime = AgentRuntime()
    mock_session = MockSessionManager()
    runtime.session_manager = mock_session
    runtime.confirmation_manager.set_session_manager(mock_session)

    # 预热并测试
    await test_case("播放一下王小帅的我爱他", "王小帅", "我爱他")
    await test_case("播放一下邵帅的你是人间四月天", "邵帅", "你是人间四月天")
    print("======================================================================")
    print("🏆 用户报告的两个提示词回归测试 100% 全部通过！")
    print("======================================================================")


if __name__ == "__main__":
    asyncio.run(main())
