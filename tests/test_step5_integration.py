"""
Step 5 全链路集成测试：网络音乐发现、Human Confirmation 与下载自动入库
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
AGENT_SERVICE_DIR = os.path.join(PROJECT_ROOT, "agent_service")

if AGENT_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AGENT_SERVICE_DIR)

from runtime.context_manager import ContextManager
from runtime.confirmation_manager import ConfirmationManager
from providers.music.manager import MusicProviderManager
from services.download_service import DownloadService
from workflows.network_discovery_workflow import NetworkDiscoveryWorkflow
from workflows.search_and_play_workflow import SearchAndPlayWorkflow


async def run_step5_integration():
    print("=" * 70)
    print("🚀 开始运行 Step 5 多源网络音乐发现、人工确认与自动入库全链路集成测试")
    print("=" * 70)

    # 1. 初始化 Mock Runtime
    runtime = MagicMock()
    runtime.context_manager = ContextManager()
    session = runtime.context_manager.get_session("s_step5")

    # 模拟客户端 WebSocket 发送器
    mock_sent_messages = []
    async def mock_send_json(session_id, data):
        mock_sent_messages.append(data)
        # 模拟 Qt 前端自动处理 confirmation_required 弹窗响应
        if data.get("type") == "confirmation_required":
            cid = data.get("confirm_id")
            # 默认如果是 test_confirm 场景则回复 True，test_reject 则回复 False
            confirmed = not getattr(runtime, "simulate_user_reject", False)
            print(f"   [Mock QML Dialog] 弹出《{data.get('payload', {}).get('title')}》弹窗，模拟用户点击: {'【确认】' if confirmed else '【取消】'}")
            # 异步模拟用户交互响应
            asyncio.create_task(async_respond_confirm(cid, confirmed))
        return True

    async def async_respond_confirm(cid, confirmed):
        await asyncio.sleep(0.05)
        runtime.confirmation_manager.handle_response(cid, confirmed)

    session_mgr = MagicMock()
    session_mgr.send_json = mock_send_json

    runtime.session_manager = session_mgr
    runtime.confirmation_manager = ConfirmationManager(session_mgr)
    runtime.provider_manager = MusicProviderManager()
    runtime.download_service = DownloadService()

    # 模拟本地曲库：仅收录了《晴天》
    mock_local_library = [
        {"index": 0, "title": "晴天", "artist": "周杰伦", "file_path": "d:/music/晴天.mp3"}
    ]

    last_called_tools = []
    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        last_called_tools.append({"name": tool_name, "args": arguments})
        print(f"   [Mock Qt Client] 收到工具调用: {tool_name}, 入参: {arguments}")
        if tool_name == "search_local_music":
            q = arguments.get("query", "").lower()
            matched = [t for t in mock_local_library if q in t["title"].lower() or q in t["artist"].lower()]
            return {"success": True, "result": {"tracks": matched}}
        elif tool_name == "play_local_track":
            return {"success": True, "result": {"index": arguments.get("index", 0)}}
        elif tool_name == "import_downloaded_track":
            new_idx = len(mock_local_library)
            new_t = {
                "index": new_idx,
                "title": arguments.get("title"),
                "artist": arguments.get("artist"),
                "file_path": arguments.get("file_path")
            }
            mock_local_library.append(new_t)
            return {"success": True, "result": {"index": new_idx, "total_count": len(mock_local_library)}}
        return {"success": False, "error": "unknown tool"}

    runtime.call_client_tool = mock_call_client_tool
    net_wf = NetworkDiscoveryWorkflow(runtime)
    runtime.network_discovery_workflow = net_wf
    search_wf = SearchAndPlayWorkflow(runtime)
    runtime.search_play_workflow = search_wf

    # -------------------------------------------------------------
    # Test 1: 本地优先原则查验 (Local-First Guardrail)
    # 输入已有本地歌曲《晴天》，坚决本地开播，严禁网络搜索与下载
    # -------------------------------------------------------------
    print("\n--- [Test 1] 本地优先原则：网络指令命中本地曲库时不触发网络下载 ---")
    last_called_tools.clear()
    out1 = await net_wf.execute(
        session_id="s_step5",
        request_id="r1",
        query="晴天",
        artist="周杰伦"
    )
    assert out1.success is True
    assert any(c["name"] == "play_local_track" for c in last_called_tools)
    assert not any(c["name"] == "import_downloaded_track" for c in last_called_tools)
    print("✅ Test 1 通过！检测到本地已有《晴天》，直接本地原生开播，零网络消耗！")

    # -------------------------------------------------------------
    # Test 2: 网络音乐发现 + Human Confirmation 用户确认通过 + 下载自动入库
    # 输入本地未收录的歌曲《夜曲》，弹出确认，模拟用户点击确认
    # -------------------------------------------------------------
    print("\n--- [Test 2] 网络多源发现 + 人工确认通过 + 自动入库开播 ---")
    runtime.simulate_user_reject = False
    last_called_tools.clear()
    out2 = await net_wf.execute(
        session_id="s_step5",
        request_id="r2",
        query="夜曲",
        artist="周杰伦",
        auto_download=True,
        auto_play=True
    )
    assert out2.success is True
    # 验证是否触发了 import_downloaded_track
    import_calls = [c for c in last_called_tools if c["name"] == "import_downloaded_track"]
    assert len(import_calls) == 1
    imported_args = import_calls[0]["args"]
    assert imported_args["title"] == "夜曲"
    assert imported_args["artist"] == "周杰伦"
    assert imported_args["auto_play"] is True
    assert os.path.exists(imported_args["file_path"])
    print(f"✅ Test 2 通过！用户确认后成功下载并自动入库: {imported_args['file_path']}")
    print(f"   当前曲库总数自动扩充为: {len(mock_local_library)} 首")

    # -------------------------------------------------------------
    # Test 3: 网络音乐发现 + Human Confirmation 用户取消
    # 模拟用户在模态弹窗点击“取消”
    # -------------------------------------------------------------
    print("\n--- [Test 3] 网络音乐发现 + 人工确认取消：安全拦截未授权下载 ---")
    runtime.simulate_user_reject = True
    last_called_tools.clear()
    out3 = await net_wf.execute(
        session_id="s_step5",
        request_id="r3",
        query="枫",
        artist="周杰伦",
        auto_download=True
    )
    assert out3.success is True
    assert "取消" in out3.answer_text
    assert not any(c["name"] == "import_downloaded_track" for c in last_called_tools)
    print("✅ Test 3 通过！用户点击取消后，任务平滑终止，坚决不向本地写入未确认文件！")

    # -------------------------------------------------------------
    # Test 4: SearchAndPlayWorkflow 本地查无此曲时无缝流转至网络发现
    # -------------------------------------------------------------
    print("\n--- [Test 4] 点歌工作流本地查无此曲，自动平滑流转网络发现 ---")
    runtime.simulate_user_reject = False
    last_called_tools.clear()
    out4 = await search_wf.execute(
        session_id="s_step5",
        request_id="r4",
        query="反方向的钟",
        artist="周杰伦"
    )
    assert out4.success is True
    import_calls4 = [c for c in last_called_tools if c["name"] == "import_downloaded_track"]
    assert len(import_calls4) == 1
    assert import_calls4[0]["args"]["title"] == "反方向的钟"
    print("✅ Test 4 通过！常规点歌本地查不到时，自动顺畅过渡到网络多源发现与下载入库！")

    print("\n" + "=" * 70)
    print("🎉 Step 5 全部 4 大核心全链路集成测试 100% 验证通过！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_step5_integration())
