"""
Step 4 全链路端到端集成测试 (test_step4_integration.py)
验证：
1. "我今天有点不开心 给我播放一首能让我心情愉悦的歌曲" -> SmartPlaylistWorkflow 端到端闭环
2. 跨轮指代 "你给我播放呀" -> 实体解析至《稻香》并调用 play_local_track
3. "我要写代码了，来几首轻快的中文歌" -> create_temp_playlist 歌单生成闭环
4. "播放晴天" -> SearchAndPlayWorkflow 精准点歌
"""
import sys
import os
import asyncio
from unittest.mock import AsyncMock

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
AGENT_SERVICE_DIR = os.path.join(PROJECT_ROOT, "agent_service")

if AGENT_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AGENT_SERVICE_DIR)

from runtime.agent_runtime import AgentRuntime
from runtime.intent_router import IntentRouter
from config import ServiceConfig, LlmConfig


# 模拟 Qt 本地曲库的真实曲目数据
MOCK_LOCAL_TRACKS = [
    {"index": 0, "title": "晴天", "artist": "周杰伦", "album": "叶惠美", "file_path": "d:/music/001 - 晴天 - 周杰伦.mp3", "duration_ms": 269000, "is_favorite": True},
    {"index": 1, "title": "七里香", "artist": "周杰伦", "album": "七里香", "file_path": "d:/music/002 - 七里香 - 周杰伦.mp3", "duration_ms": 299000, "is_favorite": False},
    {"index": 2, "title": "青花瓷", "artist": "周杰伦", "album": "我很忙", "file_path": "d:/music/003 - 青花瓷 - 周杰伦.mp3", "duration_ms": 239000, "is_favorite": False},
    {"index": 3, "title": "夜曲", "artist": "周杰伦", "album": "十一月的萧邦", "file_path": "d:/music/004 - 夜曲 - 周杰伦.mp3", "duration_ms": 226000, "is_favorite": False},
    {"index": 4, "title": "稻香", "artist": "周杰伦", "album": "魔杰座", "file_path": "d:/music/005 - 稻香 - 周杰伦.mp3", "duration_ms": 223000, "is_favorite": True},
    {"index": 5, "title": "简单爱", "artist": "周杰伦", "album": "范特西", "file_path": "d:/music/013 - 简单爱 - 周杰伦.mp3", "duration_ms": 270000, "is_favorite": False},
    {"index": 6, "title": "豆浆油条", "artist": "林俊杰", "album": "第二天堂", "file_path": "d:/music/041 - 豆浆油条 - 林俊杰.mp3", "duration_ms": 255000, "is_favorite": False},
    {"index": 7, "title": "江南", "artist": "林俊杰", "album": "第二天堂", "file_path": "d:/music/026 - 江南 - 林俊杰.mp3", "duration_ms": 268000, "is_favorite": True},
    {"index": 8, "title": "夏日漱石", "artist": "橘子海", "album": "浪潮上岸", "file_path": "d:/music/210 - 夏日漱石 - 橘子海.mp3", "duration_ms": 263000, "is_favorite": False},
    {"index": 9, "title": "离开地球表面", "artist": "五月天", "album": "离开地球表面", "file_path": "d:/music/114 - 离开地球表面 - 五月天.mp3", "duration_ms": 275000, "is_favorite": False}
]


async def run_integration_tests():
    print("=" * 70)
    print("🚀 开始运行 Step 4 确定性工作流全链路集成测试")
    print("=" * 70)

    cfg = ServiceConfig(token="test_token", dev_mode=True)
    runtime = AgentRuntime(cfg)

    # 模拟客户端 WebSocket 工具回执
    async def mock_call_client_tool(session_id, tool_name, arguments, timeout=5.0):
        print(f"   [Mock Qt Client] 收到工具调用: {tool_name}, 入参: {arguments}")
        if tool_name == "search_local_music":
            q = arguments.get("query", "").strip().lower()
            if not q or q == "*":
                return {"success": True, "error": "", "result": {"tracks": MOCK_LOCAL_TRACKS, "total_library_tracks": len(MOCK_LOCAL_TRACKS)}}
            matches = [t for t in MOCK_LOCAL_TRACKS if q in t["title"].lower() or q in t["artist"].lower()]
            return {"success": True, "error": "", "result": {"tracks": matches, "total_library_tracks": len(MOCK_LOCAL_TRACKS)}}

        elif tool_name == "play_local_track":
            idx = arguments.get("index", 0)
            track = MOCK_LOCAL_TRACKS[idx] if idx < len(MOCK_LOCAL_TRACKS) else MOCK_LOCAL_TRACKS[0]
            return {"success": True, "error": "", "result": {"status": "playing", "index": idx, "title": track["title"], "artist": track["artist"]}}

        elif tool_name == "create_temp_playlist":
            indices = arguments.get("track_indices", [])
            return {"success": True, "error": "", "result": {"playlist_id": "pl_mock_123", "playlist_name": arguments.get("name"), "track_count": len(indices), "auto_played": True}}

        elif tool_name == "set_volume":
            return {"success": True, "error": "", "result": {"current_volume": arguments.get("volume", 50)}}

        return {"success": False, "error": "未知工具", "result": {}}

    runtime.call_client_tool = AsyncMock(side_effect=mock_call_client_tool)

    session_id = "test_sess_001"
    session_ctx = runtime.context_manager.get_session(session_id)

    # -------------------------------------------------------------
    # 测试用例 1: 情绪治愈单曲点播并开播 (用户痛点：只推荐不播放)
    # -------------------------------------------------------------
    print("\n--- [Test 1] 心情不好推荐一首能让我心情愉悦的歌 ---")
    query_1 = "我今天有点不开心 给我播放一首能让我心情愉悦的歌曲"
    intent_1 = await IntentRouter.route_intent(query_1, context_session=session_ctx)
    assert intent_1.intent_type == "SMART_PLAYLIST", f"期望 SMART_PLAYLIST，实际: {intent_1.intent_type}"

    wf_res_1 = await runtime.smart_playlist_workflow.execute(
        session_id=session_id,
        request_id="req_001",
        mood=intent_1.params.get("mood", ""),
        scene=intent_1.params.get("scene", ""),
        count=intent_1.params.get("count", 1),
        raw_text=query_1
    )
    assert wf_res_1.success is True, "工作流执行应返回 success=True"
    assert len(wf_res_1.tools) == 1, "应生成 1 个工具卡片"
    assert wf_res_1.tools[0]["action"] == "play_local_track", f"工具动作应为 play_local_track，实际: {wf_res_1.tools[0]['action']}"
    assert "《稻香》" in wf_res_1.answer_text, f"治愈回答中应包含《稻香》，实际文本: {wf_res_1.answer_text}"
    print(f"✅ Test 1 通过！工具卡片: {wf_res_1.tools[0]['params']}")
    print(f"   回答摘要: {wf_res_1.answer_text[:70]}...")

    # 模拟 session 记录助手消息
    session_ctx.add_assistant_message(wf_res_1.answer_text, recommended_tracks=session_ctx.last_recommended_tracks)

    # -------------------------------------------------------------
    # 测试用例 2: 跨轮指代消歧与开播 (用户痛点：说“你给我播放呀”识别失效或 resume 旧歌)
    # -------------------------------------------------------------
    print("\n--- [Test 2] 跨轮指代：“你给我播放呀” ---")
    query_2 = "你给我播放呀"
    intent_2 = await IntentRouter.route_intent(query_2, context_session=session_ctx)
    assert intent_2.intent_type == "SEARCH_AND_PLAY", f"期望 SEARCH_AND_PLAY，实际: {intent_2.intent_type}"
    assert intent_2.params.get("query") == "稻香", f"上下文应准确解析出 稻香，实际: {intent_2.params.get('query')}"

    wf_res_2 = await runtime.search_play_workflow.execute(
        session_id=session_id,
        request_id="req_002",
        query=intent_2.params.get("query", ""),
        raw_text=query_2
    )
    assert wf_res_2.success is True
    assert wf_res_2.tools[0]["action"] == "play_local_track"
    assert "《稻香》" in wf_res_2.tools[0]["params"]
    print(f"✅ Test 2 通过！成功从上下文承接《稻香》并启动真实开播！")

    # -------------------------------------------------------------
    # 测试用例 3: 场景多曲歌单生成 (需求：我要写代码了，来几首轻快的中文歌)
    # -------------------------------------------------------------
    print("\n--- [Test 3] 场景多曲歌单生成：“我要写代码了，来几首轻快的中文歌” ---")
    query_3 = "我要写代码了，来几首轻快的中文歌"
    intent_3 = await IntentRouter.route_intent(query_3, context_session=session_ctx)
    assert intent_3.intent_type == "SMART_PLAYLIST"

    wf_res_3 = await runtime.smart_playlist_workflow.execute(
        session_id=session_id,
        request_id="req_003",
        mood=intent_3.params.get("mood", ""),
        scene=intent_3.params.get("scene", ""),
        raw_text=query_3
    )
    assert wf_res_3.success is True
    assert wf_res_3.tools[0]["action"] == "create_temp_playlist"
    print(f"✅ Test 3 通过！工具卡片: {wf_res_3.tools[0]['params']}")
    print(f"   回答摘要:\n{wf_res_3.answer_text[:120]}...")

    # -------------------------------------------------------------
    # 测试用例 4: 精准点歌：“播放晴天”
    # -------------------------------------------------------------
    print("\n--- [Test 4] 精准点歌：“播放晴天” ---")
    query_4 = "播放晴天"
    intent_4 = await IntentRouter.route_intent(query_4, context_session=session_ctx)
    assert intent_4.intent_type == "SEARCH_AND_PLAY"
    assert intent_4.params.get("query") == "晴天"

    wf_res_4 = await runtime.search_play_workflow.execute(
        session_id=session_id,
        request_id="req_004",
        query=intent_4.params.get("query", ""),
        raw_text=query_4
    )
    assert wf_res_4.success is True
    assert wf_res_4.tools[0]["action"] == "play_local_track"
    assert "《晴天》" in wf_res_4.tools[0]["params"]
    print(f"✅ Test 4 通过！已播放《晴天》！")

    print("\n" + "=" * 70)
    print("🎉 全部 4 项端到端全链路集成测试 100% 验证通过！")
    print("=" * 70)
    return True


if __name__ == "__main__":
    passed = asyncio.run(run_integration_tests())
    sys.exit(0 if passed else 1)
