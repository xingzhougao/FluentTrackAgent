import os
import sys
import asyncio

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

from runtime.context_manager import ContextManager
from runtime.intent_router import IntentRouter
from llm.base import ChatMessage

assistant_msg_content = """
这四首歌曲给你打打气：
### 🎵 第一首：《海阔天空》—— Beyond
这首歌是华语乐坛的热血图腾。

### 🎵 第二首：《倔强》—— 五月天
我和我最后的倔强，握紧双手绝对不放。

### 🎵 第三首：《骄傲的少年》—— 南征北战 NZBZ
编曲紧凑，鼓点密集。

### 4. 《红日》—— 李克勤
想要快速回血，这首歌绝对是急救良药。

你想先听哪一首？告诉我，我为你开播！
"""

async def test_decision_and_ordinal():
    ctx_mgr = ContextManager()
    session = ctx_mgr.get_session("test_decision")
    
    # 模拟前两轮对话
    session.add_user_message("今天好累啊 有没有什么激情的中文歌曲推荐")
    session.messages.append(ChatMessage(role="assistant", content=assistant_msg_content))
    
    test_queries = [
        "帮我播放你这四首歌中你最推荐的",
        "播放你最推荐的那首",
        "你帮我选一首播放",
        "播放第二首",
        "放第三首",
        "放最后一首",
        "放刚才推荐的"
    ]
    
    print("\n================= 上下文决策点播测试 =================")
    for q in test_queries:
        res = await IntentRouter.route_intent(q, context_session=session)
        print(f"用户输入: '{q}'")
        print(f"  -> intent={res.intent_type}, action={res.action}, target_song={res.params.get('query')}")

if __name__ == "__main__":
    asyncio.run(test_decision_and_ordinal())
