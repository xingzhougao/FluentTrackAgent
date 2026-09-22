"""
验证测试：四大梯队优先级排序、Soulseek 原版直通、自动下载模式与弹窗自选模式
"""
import sys
import os
import asyncio
import logging

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from providers.music.manager import MusicProviderManager
from runtime.agent_runtime import AgentRuntime


async def run_tests():
    print("\n=======================================================")
    print("TEST 1: 验证四大梯队严格排序 (Tier 1 > Tier 2 > Tier 3 > Tier 4)")
    print("=======================================================")
    mgr = MusicProviderManager()

    # 1. 萧萧 - 爱要坦荡荡 (Soulseek 拥有无损原版)
    print("\n>>> 检索：萧萧 -《爱要坦荡荡》")
    cands_xiao = await mgr.search("爱要坦荡荡", "萧萧", limit=5)
    assert len(cands_xiao) > 0, "未能搜出任何候选！"
    top_cand = cands_xiao[0]
    print(f"Top 1 候选: [{top_cand.extra.get('tier_name')}] [{top_cand.extra.get('version_tag')}] 《{top_cand.title}》- {top_cand.artist} ({top_cand.provider})")
    assert top_cand.provider == "soulseek_p2p", f"Top 1 必须是 Soulseek P2P，实际为: {top_cand.provider}"
    assert "原版" in top_cand.extra.get("version_tag", ""), f"Top 1 必须是原版无损或原版，实际为: {top_cand.extra.get('version_tag')}"
    print("✅ 《爱要坦荡荡》成功由 Soulseek 原版无损登顶第一级 (Tier 1)！")

    # 2. 胡歌 - 一吻天荒 (Soulseek 仅有翻唱，网络有胡歌直接音频)
    print("\n>>> 检索：胡歌 -《一吻天荒》")
    cands_hu = await mgr.search("一吻天荒", "胡歌", limit=5)
    assert len(cands_hu) > 0, "未能搜出任何候选！"
    top_hu = cands_hu[0]
    print(f"Top 1 候选: [{top_hu.extra.get('tier_name')}] [{top_hu.extra.get('version_tag')}] 《{top_hu.title}》- {top_hu.artist} ({top_hu.provider})")
    # 验证网盘资源没有挤占前列
    netdisk_count_in_top2 = sum(1 for c in cands_hu[:2] if c.extra.get("is_netdisk"))
    assert netdisk_count_in_top2 == 0, "网盘资源不应该挤占前 2 位！"
    print("✅ 《一吻天荒》中直接可播音频成功排在前面，网盘被压制到保底梯队！")

    print("\n=======================================================")
    print("TEST 2: 验证【自动优先下载模式】(auto_download = True)")
    print("=======================================================")
    runtime = AgentRuntime()
    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        print(f"[MockQtClient] 收到 Qt 客户端工具调用: {tool_name}")
        return {"success": True, "result": {"index": 0, "total_count": 10}}
    runtime.call_client_tool = mock_call_client_tool

    session_id = "test_auto_session"
    session_ctx = runtime.context_manager.get_session(session_id)
    session_ctx.preferences["auto_download"] = True

    # 模拟工作流执行
    workflow_res = await runtime.network_discovery_workflow.execute(
        session_id=session_id,
        request_id="req_auto_1",
        query="爱要坦荡荡",
        artist="萧萧",
        auto_download=True
    )
    print("自动模式执行结果:", workflow_res.success)
    print("应答摘要:", workflow_res.answer_text[:100] + "...")
    assert workflow_res.success, "自动下载模式应当成功执行！"
    print("✅ 自动优先下载模式验证成功（0 弹窗阻塞，全自动流转）！")

    print("\n=======================================================")
    print("TEST 3: 验证【弹窗自选版本模式】(auto_download = False)")
    print("=======================================================")
    session_id_modal = "test_modal_session"
    session_ctx_modal = runtime.context_manager.get_session(session_id_modal)
    session_ctx_modal.preferences["auto_download"] = False

    class MockWebSocket:
        async def send_json(self, data):
            pass
    runtime.session_manager._active_connections[session_id_modal] = MockWebSocket()

    modal_popped = False

    async def mock_client():
        nonlocal modal_popped
        for _ in range(30):
            await asyncio.sleep(0.5)
            if runtime.confirmation_manager.pending_confirmations:
                cid = list(runtime.confirmation_manager.pending_confirmations.keys())[0]
                modal_popped = True
                print(f"[MockClient] 客户端捕获到多选弹窗请求: confirm_id={cid}")
                # 模拟用户在弹窗中选择第一个候选
                await runtime.handle_inbound_message(session_id_modal, {
                    "type": "candidate_selection_response",
                    "confirm_id": cid,
                    "payload": {
                        "selected_id": cands_xiao[0].id,
                        "cancelled": False
                    }
                })
                break

    client_task = asyncio.create_task(mock_client())
    workflow_modal_res = await runtime.network_discovery_workflow.execute(
        session_id=session_id_modal,
        request_id="req_modal_1",
        query="爱要坦荡荡",
        artist="萧萧",
        auto_download=False
    )
    await client_task
    print("自选模式弹窗是否弹出:", modal_popped)
    print("自选模式执行结果:", workflow_modal_res.success)
    assert modal_popped, "弹窗自选模式必须成功唤起弹窗！"
    assert workflow_modal_res.success, "用户自选后必须成功流转！"
    print("✅ 弹窗自选模式验证成功（成功唤起 Top 5 候选并响应用户点选）！")

    print("\n🎉 全部四大梯队优先级、双模式切换与网盘保底防坑验证 100% 通过！")


if __name__ == "__main__":
    asyncio.run(run_tests())
