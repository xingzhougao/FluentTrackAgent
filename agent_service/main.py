"""
Fluent Music AI Agent 微服务入口
启动方式: python main.py [--port 8765] [--token secret]
"""
import os
import sys

# 关键环境防御：清除可能被污染的第三方老版本 PYTHONPATH
if "PYTHONPATH" in os.environ:
    del os.environ["PYTHONPATH"]

import argparse
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from config import global_config
from runtime.agent_runtime import AgentRuntime
from runtime.agent_logger import global_logger
from services.slskd_daemon import slskd_daemon


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段：若启用了 soulseek，静默自启伴生 slskd 守护进程
    if global_config.soulseek.enabled:
        try:
            asyncio.create_task(slskd_daemon.start())
        except Exception as e:
            global_logger.warning(f"[Main] 启动伴生 slskd 守护进程异常: {e}")
    yield
    # 退出阶段：优雅终止伴生进程
    try:
        slskd_daemon.stop()
    except Exception as e:
        global_logger.debug(f"[Main] 关闭伴生 slskd 异常: {e}")


# 初始化 FastAPI 实例
app = FastAPI(title="Fluent Music AI Agent Service", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 实例化核心 AgentRuntime
runtime = AgentRuntime(global_config)


@app.get("/health")
async def health_check():
    """轻量健康探测接口"""
    provider = runtime.llm_manager.get_provider()
    return {
        "status": "ok",
        "service": "FluentMusicAgent",
        "provider": provider.__class__.__name__,
        "model": provider.model_name,
        "capabilities": provider.capabilities.model_dump()
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query("default"),
    token: str = Query(None)
):
    """
    单 WebSocket 全双工通信主通道
    承载: 用户输入、AI 流式响应、思维链推送、Tool 调用请求与执行结果回传
    """
    # 鉴权校验 (审查第 10 项)
    if not runtime.session_manager.verify_token(token):
        global_logger.warning(f"WebSocket 连接鉴权失败: token={token}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await runtime.session_manager.connect(session_id, websocket)

    # 发送连接成功欢迎与状态同步
    await runtime.session_manager.send_json(session_id, {
        "type": "connected",
        "payload": {
            "session_id": session_id,
            "message": "已连接至 Fluent Music AI Agent 核心",
            "model": runtime.llm_manager.get_provider().model_name
        }
    })

    try:
        while True:
            # 接收客户端 JSON 数据
            data = await websocket.receive_json()
            # 异步非阻塞派发，确保等待 tool_result 时接收循环能持续收包
            asyncio.create_task(runtime.handle_inbound_message(session_id, data))
    except WebSocketDisconnect:
        runtime.session_manager.disconnect(session_id)
    except Exception as e:
        global_logger.error(f"WebSocket 循环异常: {e}")
        runtime.session_manager.disconnect(session_id)


def main():
    parser = argparse.ArgumentParser(description="Fluent Music AI Agent Service")
    parser.add_argument("--host", type=str, default=global_config.host, help="绑定地址")
    parser.add_argument("--port", type=int, default=global_config.port, help="监听端口 (默认 8765)")
    parser.add_argument("--token", type=str, default=global_config.token, help="会话鉴权 Token")
    parser.add_argument("--dev", action="store_true", default=True, help="是否开启开发模式 (免强制 token)")

    args = parser.parse_args()

    global_config.host = args.host
    global_config.port = args.port
    global_config.token = args.token
    global_config.dev_mode = args.dev

    # 更新运行时配置
    runtime.session_manager.auth_token = args.token
    runtime.session_manager.dev_mode = args.dev

    global_logger.info(f"正在启动 Fluent Music AI Agent 微服务: http://{args.host}:{args.port}")
    global_logger.info(f"WebSocket 接入点: ws://{args.host}:{args.port}/ws")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="warning"  # 保持控制台清爽，由 AgentLogger 统一输出业务日志
    )


if __name__ == "__main__":
    main()
