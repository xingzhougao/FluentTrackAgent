"""
针对用户指令的完整端到端测试：
1. "帮我播放一下 周杰伦的爱你没差" (Soulseek P2P 无损下载 -> 自动入库 -> 自动播放)
2. "帮我播放一下邵帅的你是人间四月天" (Xiageba 网盘资源 -> 自动打开系统浏览器转存 -> 优雅卡片响应)
"""
import asyncio
import os
import sys
import webbrowser

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

from runtime.agent_runtime import AgentRuntime
from runtime.intent_router import IntentRouter


class MockSessionManager:
    def __init__(self):
        self.sent_messages = []

    async def send_json(self, session_id: str, data: dict):
        self.sent_messages.append(data)
        if data.get("type") == "confirmation_required":
            cid = data.get("confirm_id")
            asyncio.create_task(self._auto_confirm(cid))
        return True

    async def _auto_confirm(self, confirm_id):
        await asyncio.sleep(0.05)
        global runtime
        runtime.confirmation_manager.handle_response(confirm_id, True)


async def run_test():
    global runtime, mock_session
    runtime = AgentRuntime()
    mock_session = MockSessionManager()
    runtime.session_manager = mock_session
    runtime.confirmation_manager.set_session_manager(mock_session)

    called_tools = []
    opened_browsers = []

    # Mock Qt 客户端工具通信
    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        called_tools.append((tool_name, arguments))
        if tool_name == "search_local_music":
            # 模拟本地曲库查无此曲，进入网络发现流程
            return {"success": True, "result": {"tracks": [], "total": 0}}
        elif tool_name == "import_downloaded_track":
            # 模拟 Qt 本地曲库导入成功并即刻开播
            return {
                "success": True,
                "result": {
                    "index": 99,
                    "title": arguments.get("title"),
                    "artist": arguments.get("artist"),
                    "total_count": 100
                }
            }
        elif tool_name == "play_local_track":
            return {"success": True, "result": {"playing": True}}
        return {"success": True, "result": {}}

    runtime.call_client_tool = mock_call_client_tool

    # Mock 浏览器启动记录
    orig_open = webbrowser.open
    def mock_webbrowser_open(url, *args, **kwargs):
        opened_browsers.append(url)
        return True
    webbrowser.open = mock_webbrowser_open

    print("\n=======================================================")
    print("TEST CASE 1: 帮我播放一下邵帅的你是人间四月天")
    print("=======================================================")
    prompt1 = "帮我播放一下邵帅的你是人间四月天"
    intent1 = IntentRouter.match_rule(prompt1)
    print(f"1. 意图解析: artist={intent1.params.get('artist')}, query={intent1.params.get('query')}")
    assert intent1.params.get("artist") == "邵帅"
    assert intent1.params.get("query") == "你是人间四月天"

    called_tools.clear()
    opened_browsers.clear()
    mock_session.sent_messages.clear()

    out1 = await runtime.search_play_workflow.execute(
        session_id="session_1",
        request_id="req_1",
        query=intent1.params.get("query"),
        artist=intent1.params.get("artist"),
        raw_text=prompt1
    )
    print(f"2. 执行结果: success={out1.success}")
    print(f"   回答内容: {out1.answer_text[:120]}...")
    print(f"   工具卡片: {out1.tools}")
    print(f"   浏览器打开地址: {opened_browsers}")

    assert out1.success is True, "Case 1 期望执行成功"
    if len(opened_browsers) > 0:
        assert "pan.quark.cn" in opened_browsers[0] or "pan.baidu.com" in opened_browsers[0]
        print("✅ Case 1 成功匹配下歌吧网盘资源并自动唤起浏览器转存！\n")
    else:
        # 直接音频流下载并入库成功
        import_calls1 = [c for c in called_tools if c[0] == "import_downloaded_track"]
        assert len(import_calls1) > 0, "期望调用 import_downloaded_track"
        fp1 = import_calls1[0][1]["file_path"]
        assert os.path.exists(fp1) and os.path.getsize(fp1) > 500000
        print(f"✅ Case 1 成功直接获取真实高品质音频 ({os.path.getsize(fp1)} 字节) 并入库开播！\n")

    print("=======================================================")
    print("TEST CASE 2: 帮我播放一下 周杰伦的爱你没差")
    print("=======================================================")
    prompt2 = "帮我播放一下 周杰伦的爱你没差"
    intent2 = IntentRouter.match_rule(prompt2)
    print(f"1. 意图解析: artist={intent2.params.get('artist')}, query={intent2.params.get('query')}")
    assert intent2.params.get("artist") == "周杰伦"
    assert intent2.params.get("query") == "爱你没差"

    called_tools.clear()
    opened_browsers.clear()
    mock_session.sent_messages.clear()

    out2 = await runtime.search_play_workflow.execute(
        session_id="session_2",
        request_id="req_2",
        query=intent2.params.get("query"),
        artist=intent2.params.get("artist"),
        raw_text=prompt2
    )
    print(f"2. 执行结果: success={out2.success}")
    print(f"   回答内容: {out2.answer_text[:120]}...")
    print(f"   工具卡片: {out2.tools}")
    print(f"   客户端工具调用: {called_tools}")

    assert out2.success is True, "Case 2 期望执行成功"
    import_calls = [c for c in called_tools if c[0] == "import_downloaded_track"]
    assert len(import_calls) > 0, "Case 2 期望调用 import_downloaded_track"
    downloaded_fp = import_calls[0][1]["file_path"]
    print(f"   入库文件路径: {downloaded_fp}")
    assert os.path.exists(downloaded_fp), f"下载的文件不存在: {downloaded_fp}"
    file_sz = os.path.getsize(downloaded_fp)
    print(f"   真实文件大小: {file_sz} 字节 ({file_sz // (1024*1024)} MB)")
    assert file_sz > 500000, "文件过小"

    print("✅ Case 2 成功完成 Soulseek P2P 下载、无缝入库并启动开播！\n")

    webbrowser.open = orig_open
    print("🎉 用户实测两大场景端到端全部通过验证！")


if __name__ == "__main__":
    asyncio.run(run_test())
