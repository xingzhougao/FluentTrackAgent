"""
Step 3 确定性工具调用与 WebSocket 全双工协议全面测试套件
"""
import asyncio
import json
import websockets


async def test_case(ws, user_text, expected_tool, mock_tool_result):
    req_id = f"req_{expected_tool}"
    req = {
        "type": "user_message",
        "request_id": req_id,
        "payload": {"text": user_text}
    }
    await ws.send(json.dumps(req))
    print(f"\n[Test] 发送: '{user_text}'")

    while True:
        msg_str = await ws.recv()
        msg = json.loads(msg_str)
        mtype = msg.get("type")
        payload = msg.get("payload", {})

        if mtype == "tool_request":
            tool_name = payload.get("tool_name")
            tool_call_id = payload.get("tool_call_id")
            print(f"  -> 收到 Python tool_request: {tool_name}")
            assert tool_name == expected_tool, f"期望 {expected_tool}, 实际收到 {tool_name}"

            # 回传模拟结果
            reply = {
                "type": "tool_result",
                "request_id": msg.get("request_id"),
                "payload": {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": True,
                    "result": mock_tool_result,
                    "error": ""
                }
            }
            await ws.send(json.dumps(reply))

        elif mtype == "assistant_message":
            content = payload.get("content", "")
            tools = payload.get("tools", [])
            print(f"  -> 助手回应: {content}")
            print(f"  -> 工具卡片: {tools[0]['name']} - {tools[0]['result']}")
            assert len(tools) == 1
            assert tools[0]["action"] == expected_tool
            break


async def run_all_tests():
    uri = "ws://127.0.0.1:8765/ws?session_id=test_full_suite"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        await ws.recv() # connected
        print("✓ Connected successfully!")

        # 1. 音量控制
        await test_case(ws, "把声音调到 30%", "set_volume", {"previous_volume": 50, "current_volume": 30})

        # 2. 暂停
        await test_case(ws, "暂停播放", "pause", {"status": "paused", "playing": False})

        # 3. 恢复
        await test_case(ws, "继续播放", "resume", {"status": "playing", "playing": True})

        # 4. 下一首
        await test_case(ws, "切下一首歌", "next_track", {"title": "夜曲", "artist": "周杰伦"})

        # 5. 上一首
        await test_case(ws, "上一首", "previous_track", {"title": "晴天", "artist": "周杰伦"})

        # 6. 歌曲信息查询
        await test_case(ws, "现在放的是什么歌？", "get_player_state", {
            "title": "晴天",
            "artist": "周杰伦",
            "album": "叶惠美",
            "playing": True,
            "volume": 30,
            "position_ms": 12000,
            "duration_ms": 269000,
            "is_favorite": True,
            "play_mode": 0
        })

        # 7. 收藏歌曲
        await test_case(ws, "收藏这首歌", "toggle_favorite", {"title": "晴天", "is_favorite": True})

    print("\n==========================================")
    print("🎉 Step 3 全部 7 项播放控制原子工具测试 100% 通过！")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
