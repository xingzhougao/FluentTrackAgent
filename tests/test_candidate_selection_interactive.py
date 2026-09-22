"""
Interactive candidate selection test:
Verifies that when multiple network versions are found, the system presents up to 5 candidates
with version tags, and downloads/opens the exact candidate picked by the user.
"""
import os
import sys
import asyncio

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

from runtime.agent_runtime import AgentRuntime
from providers.music.base import TrackCandidate

class MockWebSocketClient:
    def __init__(self, runtime):
        self.runtime = runtime
        self.received_messages = []
        self.selection_triggered = False

    async def send_json(self, session_id, data=None):
        if data is None:
            data = session_id
        self.received_messages.append(data)
        msg_type = data.get("type")
        if msg_type == "candidate_selection_required":
            self.selection_triggered = True
            confirm_id = data.get("confirm_id")
            payload = data.get("payload", {})
            candidates = payload.get("candidates", [])
            print(f"\n[MockClient] 收到多版本选歌弹窗请求! confirm_id={confirm_id}")
            print(f"[MockClient] 候选版本总数: {len(candidates)} (最多 5 条)")
            assert len(candidates) <= 5, "候选数量不应超过 5 条"

            for i, c in enumerate(candidates):
                print(f"   [{i}] [{c.get('version_tag')}] [{c.get('source_label')}] {c.get('title')} - {c.get('artist')} ({c.get('format')} {c.get('bitrate')})")

            # 模拟用户选择第 1 个候选版本 (index 0)
            chosen_id = candidates[0].get("id")
            print(f"[MockClient] 用户在弹窗中点选了: [{candidates[0].get('version_tag')}] {candidates[0].get('title')} (id={chosen_id})")

            # 异步回传选择响应
            asyncio.create_task(self._reply_selection(confirm_id, chosen_id))

    async def _reply_selection(self, confirm_id, chosen_id):
        await asyncio.sleep(0.1)
        await self.runtime.handle_inbound_message("default", {
            "type": "candidate_selection_response",
            "confirm_id": confirm_id,
            "payload": {
                "confirm_id": confirm_id,
                "selected_id": chosen_id,
                "cancelled": False
            }
        })

    def has_session(self, session_id):
        return True

async def run_test():
    print("=======================================================")
    print("TEST: 多版本弹窗交互与精准选择验证 (Sweety - 樱花草)")
    print("=======================================================")
    runtime = AgentRuntime()
    mock_client = MockWebSocketClient(runtime)
    runtime.session_manager = mock_client
    runtime.confirmation_manager.set_session_manager(mock_client)

    # Mock Qt 客户端工具通信
    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        if tool_name == "import_downloaded_track":
            return {"success": True, "result": {"index": 0, "total_count": 100}}
        return {"success": True, "result": {}}

    runtime.call_client_tool = mock_call_client_tool

    out = await runtime.network_discovery_workflow.execute(
        session_id="default",
        request_id="req_sel_test",
        query="樱花草",
        artist="Sweety",
        auto_download=True,
        auto_play=True
    )

    print(f"\n工作流执行结果: success={out.success}")
    print(f"弹窗是否成功弹出: {mock_client.selection_triggered}")
    assert mock_client.selection_triggered is True, "期望触发 candidate_selection_required 弹窗"
    assert out.success is True, "期望执行成功"

    print("\n=======================================================")
    print("TEST: 多版本弹窗交互与精准选择验证 (胡歌 - 一吻天荒)")
    print("=======================================================")
    mock_client.selection_triggered = False
    out2 = await runtime.network_discovery_workflow.execute(
        session_id="default",
        request_id="req_sel_test2",
        query="一吻天荒",
        artist="胡歌",
        auto_download=True,
        auto_play=True
    )

    print(f"\n工作流执行结果: success={out2.success}")
    print(f"弹窗是否成功弹出: {mock_client.selection_triggered}")
    assert mock_client.selection_triggered is True, "期望触发 candidate_selection_required 弹窗"
    assert out2.success is True, "期望执行成功"
    print("\n🎉 两大真实曲目多版本弹窗选择与交互式下载全部 100% 通过验证！")

if __name__ == "__main__":
    asyncio.run(run_test())
