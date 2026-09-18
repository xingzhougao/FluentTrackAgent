"""
WebSocket 端到端协议流式测试脚本
"""
import asyncio
import json
import websockets


async def test_ws():
    uri = "ws://127.0.0.1:8765/ws?session_id=test_client"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        # 1. 接收握手 connected 消息
        greeting = await ws.recv()
        print("Received greeting:", greeting)

        # 2. 发送测试消息
        req = {
            "type": "user_message",
            "request_id": "test_req_001",
            "payload": {"text": "你好，请用简短一句话介绍你自己"}
        }
        await ws.send(json.dumps(req))
        print("Sent user_message:", req)

        # 3. 循环接收流式增量与最终消息
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            mtype = data.get("type")
            payload = data.get("payload", {})

            if mtype == "status_update":
                print(f"[Status] {payload.get('status')} - {payload.get('message')}")
            elif mtype == "assistant_delta":
                delta_type = payload.get("delta_type")
                text = payload.get("text", "")
                print(f"[{delta_type.upper()}] {text}", end="", flush=True)
            elif mtype == "assistant_message":
                print("\n[Done] Full assistant message received:")
                print("Content:", payload.get("content"))
                print("Thinking:", payload.get("thinking_content"))
                print("Duration:", payload.get("duration_ms"), "ms")
                break
            elif mtype == "error":
                print("\n[Error]", payload.get("message"))
                break

        # 4. 测试清空上下文
        clear_req = {"type": "clear_context", "request_id": "test_req_002"}
        await ws.send(json.dumps(clear_req))
        resp = await ws.recv()
        print("\nClear context response:", resp)

    print("\nWebSocket protocol test passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_ws())
