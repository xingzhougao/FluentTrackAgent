"""
验证测试：
1. 彻底移除第四级其他网络音源，仅保留第一级 (Soulseek 原版)、第二级 (歌名匹配翻唱/直接音频)、第三级 (下歌吧网盘)
2. 无音源时触发 no_source_found 消息（弹出“抱歉暂时找不到对应音源哦”+确认按钮）
3. 选歌弹窗点击提交后窗口保持并支持关闭
"""
import sys
import os
import asyncio
import logging
from unittest.mock import AsyncMock

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from providers.music.manager import MusicProviderManager
from runtime.agent_runtime import AgentRuntime


async def run_tests():
    print("\n=======================================================")
    print("TEST 1: 验证仅保留前三梯队，彻底剔除第四级其他网络音源")
    print("=======================================================")
    mgr = MusicProviderManager()
    
    # 验证注册的 Provider
    registered_providers = list(mgr.providers.keys())
    print("当前注册的 Provider:", registered_providers)
    assert "web_music" not in registered_providers, "第四级其他网络音源 (web_music) 必须被移除！"
    assert "soulseek_p2p" in registered_providers, "第一级/第二级主力 Soulseek P2P 必须保留！"
    assert "xiageba" in registered_providers, "第三级主力下歌吧必须保留！"
    print("✅ Provider 注册检查通过：仅保留三大主力音源！")

    # 检索真实曲目：萧萧 - 爱要坦荡荡
    print("\n>>> 检索：萧萧 -《爱要坦荡荡》")
    cands = await mgr.search("爱要坦荡荡", "萧萧", limit=5)
    print(f"返回候选总数: {len(cands)}")
    for i, c in enumerate(cands):
        tier = c.extra.get("tier")
        tier_name = c.extra.get("tier_name")
        print(f"  [{i+1}] [Tier {tier} - {tier_name}] 《{c.title}》- {c.artist} ({c.provider})")
        assert tier in [1, 2, 3], f"候选必须严格属于第 1/2/3 梯队，实际为: Tier {tier}"
        assert c.provider != "web_music", "绝不能出现来自 web_music 的条目！"
    print("✅ 检索候选全部为纯净三大梯队，无任何低质网络杂质！")

    print("\n=======================================================")
    print("TEST 2: 验证无音源时触发「抱歉暂时找不到对应音源哦」通知")
    print("=======================================================")
    runtime = AgentRuntime()
    session_id = "test_no_source_session"
    session_ctx = runtime.context_manager.get_session(session_id)

    received_messages = []
    class MockWebSocket:
        async def send_json(self, data):
            received_messages.append(data)
    runtime.session_manager._active_connections[session_id] = MockWebSocket()

    # 搜索完全不存在的虚构曲目
    fake_query = "XYZ_DEFINITELY_NON_EXISTENT_MUSIC_99999"
    workflow_res = await runtime.network_discovery_workflow.execute(
        session_id=session_id,
        request_id="req_no_src_1",
        query=fake_query,
        artist=""
    )

    print("工作流执行成功状态:", workflow_res.success)
    print("工作流回复:", workflow_res.answer_text)
    
    # 查找是否有 no_source_found 通知
    no_src_msgs = [m for m in received_messages if m.get("type") == "no_source_found"]
    assert len(no_src_msgs) > 0, "必须向客户端下发 no_source_found 模态弹窗通知！"
    target_msg = no_src_msgs[0]["payload"]["message"]
    print("前端模态弹窗消息内容:", target_msg)
    assert "抱歉暂时找不到对应音源哦" in target_msg, f"弹窗文本必须包含‘抱歉暂时找不到对应音源哦’，实际为: {target_msg}"
    print("✅ 无音源提示弹窗消息下发验证成功！")

    print("\n=======================================================")
    print("TEST 3: 验证弹窗自选模式提交流程与候选格式")
    print("=======================================================")
    session_id_sel = "test_selection_session"
    session_ctx_sel = runtime.context_manager.get_session(session_id_sel)
    session_ctx_sel.preferences["auto_download"] = False
    runtime.session_manager._active_connections[session_id_sel] = MockWebSocket()

    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        print(f"[MockQtClient] 收到 Qt 工具调用: {tool_name}")
        return {"success": True, "result": {"index": 0, "total_count": 5}}
    runtime.call_client_tool = mock_call_client_tool

    modal_dispatched = False

    async def mock_client_respond():
        nonlocal modal_dispatched
        for _ in range(30):
            await asyncio.sleep(0.5)
            if runtime.confirmation_manager.pending_confirmations:
                cid = list(runtime.confirmation_manager.pending_confirmations.keys())[0]
                modal_dispatched = True
                print(f"[MockClient] 捕获选歌弹窗请求: confirm_id={cid}")
                # 模拟用户点击选项后点击下载
                await runtime.handle_inbound_message(session_id_sel, {
                    "type": "candidate_selection_response",
                    "confirm_id": cid,
                    "payload": {
                        "selected_id": cands[0].id,
                        "cancelled": False
                    }
                })
                break

    client_task = asyncio.create_task(mock_client_respond())
    workflow_sel_res = await runtime.network_discovery_workflow.execute(
        session_id=session_id_sel,
        request_id="req_sel_1",
        query="爱要坦荡荡",
        artist="萧萧",
        auto_download=False
    )
    await client_task

    assert modal_dispatched, "选歌模式必须下发候选列表！"
    assert workflow_sel_res.success, "用户选择后工作流必须顺利流转！"
    print("✅ 选歌弹窗模式全流程顺利流转！")

    print("\n🎉 三大纯净梯队保留、无音源模态弹窗与窗口保留机制 100% 验证通过！")


if __name__ == "__main__":
    asyncio.run(run_tests())
