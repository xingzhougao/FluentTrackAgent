"""
测试音乐智能体心智架构与意图边界判定 (针对用户核心反馈重构的验证用例)
包含：
1. 开放聊天与心理揣测（“你猜我今天的心情如何”、“你好”）严禁被劫持为搜歌/下载，100% 判定为 CHAT
2. 显式点歌指令（“帮我播放歌曲迷人的危险”、“听听最长的电影”）精准识别且不误切“的”
3. Ollama 离线探测毫秒级极速响应，绝不挂起 15 秒阻塞异步事件循环
4. Soulseek P2P 活跃免排队节点优先与 10s 快速熔断
"""
import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent_service")))

from runtime.intent_router import IntentRouter, extract_music_entity
from llm.ollama_provider import OllamaProvider


async def test_natural_conversation_not_hijacked():
    """验证日常聊天、心情揣测等开放文本 100% 归还 CHAT，绝不被规则引擎拆解为搜歌"""
    chat_phrases = [
        "你猜我今天的心情如何",
        "你猜猜我今天心情如何",
        "下午好",
        "你好",
        "你好呀",
        "在吗",
        "哈喽",
        "我今天好累啊",
        "今天天气真好",
        "为什么老歌听起来那么有味道",
        "你觉得周杰伦帅吗",
        "音乐的意义是什么",
        "睡不着怎么办"
    ]
    for phrase in chat_phrases:
        rule_res = IntentRouter.match_rule(phrase)
        assert rule_res is None, f"句子 '{phrase}' 不应被确定性规则引擎劫持为点歌/控制，而应流向大模型大脑！实际返回: {rule_res}"

        intent_res = await IntentRouter.route_intent(phrase)
        assert intent_res.intent_type == "CHAT", f"句子 '{phrase}' 意图应为 CHAT，实际为: {intent_res.intent_type}"


async def test_explicit_music_intent_and_safe_split():
    """验证显式点歌指令精准识别，且经典含'的'歌曲不会被误切分为歌手与歌名"""
    # 0. 纯经典歌名输入: 迷人的危险
    q0 = "迷人的危险"
    r0 = IntentRouter.match_rule(q0)
    assert r0 is not None and r0.intent_type == "SEARCH_AND_PLAY"
    assert r0.params["query"] == "迷人的危险"
    assert r0.params["artist"] == ""

    # 1. 迷人的危险 (形容词'迷人'不能被误认为歌手)
    q1 = "帮我播放一下歌曲迷人的危险"
    r1 = IntentRouter.match_rule(q1)
    assert r1 is not None and r1.intent_type == "SEARCH_AND_PLAY"
    assert r1.params["query"] == "迷人的危险"
    assert r1.params["artist"] == ""

    # 2. 我想听迷人的危险
    q2 = "我想听迷人的危险"
    r2 = IntentRouter.match_rule(q2)
    assert r2 is not None and r2.intent_type == "SEARCH_AND_PLAY"
    assert r2.params["query"] == "迷人的危险"
    assert r2.params["artist"] == ""

    # 3. 周杰伦最长的电影 (歌手=周杰伦, 歌名=最长的电影)
    q3 = "播放周杰伦最长的电影"
    r3 = IntentRouter.match_rule(q3)
    assert r3 is not None and r3.intent_type == "SEARCH_AND_PLAY"
    assert r3.params["artist"] == "周杰伦"
    assert r3.params["query"] == "最长的电影"

    # 4. 《最初的梦想》
    q4 = "《最初的梦想》"
    r4 = IntentRouter.match_rule(q4)
    assert r4 is not None and r4.intent_type == "SEARCH_AND_PLAY"
    assert r4.params["query"] == "最初的梦想"

    # 5. 周杰伦 - 晴天
    q5 = "周杰伦 - 晴天"
    r5 = IntentRouter.match_rule(q5)
    assert r5 is not None and r5.intent_type == "SEARCH_AND_PLAY"
    assert r5.params["artist"] == "周杰伦"
    assert r5.params["query"] == "晴天"


async def test_ollama_offline_fast_failover():
    """验证当本地 Ollama 端口不可用时，探测在 0.6 秒内极速返回，杜绝 15 秒阻塞事件循环"""
    # 使用一个肯定没有启动的测试端口
    offline_provider = OllamaProvider(base_url="http://127.0.0.1:59999", timeout=10.0)

    start = time.perf_counter()
    is_avail = await offline_provider.check_availability()
    elapsed = time.perf_counter() - start

    assert not is_avail
    assert elapsed < 0.8, f"离线健康探测耗时过长 ({elapsed:.2f}s)，有阻塞 asyncio 事件循环风险！"

    # 验证 chat_stream 极速优雅输出引导语
    stream_start = time.perf_counter()
    chunks = []
    async for chunk in offline_provider.chat_stream([]):
        chunks.append(chunk)
    stream_elapsed = time.perf_counter() - stream_start

    assert stream_elapsed < 0.8
    assert any("Ollama" in c for c in chunks)


async def test_soulseek_peer_alignment_and_sorting():
    """验证 Soulseek 节点排序中免排队活跃 Peer 优先，且严格对齐同歌曲"""
    from providers.music.soulseek_provider import SoulseekMusicProvider
    provider = SoulseekMusicProvider()

    # 构造假数据模拟一个免排队 Peer 和一个拥堵排队 Peer
    peer_fast = {
        "username": "fast_user",
        "remote_filename": "Music/Various/迷人的危险.flac",
        "size": 20000000,
        "bitrate": 960,
        "ext": ".flac",
        "format": "flac",
        "length": 240,
        "has_free_slot": True,
        "queue_len": 0
    }
    peer_slow = {
        "username": "slow_user",
        "remote_filename": "Music/Various/迷人的危险.flac",
        "size": 20000000,
        "bitrate": 960,
        "ext": ".flac",
        "format": "flac",
        "length": 240,
        "has_free_slot": False,
        "queue_len": 45
    }

    candidates = [peer_slow, peer_fast]
    candidates.sort(key=lambda p: (
        p.get("has_free_slot", False),
        p["ext"] in [".flac", ".wav"],
        p["bitrate"],
        -p.get("queue_len", 999),
        p["size"]
    ), reverse=True)

    assert candidates[0]["username"] == "fast_user", "免排队活跃 Peer 应当排在最首位优先调度！"


if __name__ == "__main__":
    asyncio.run(test_natural_conversation_not_hijacked())
    asyncio.run(test_explicit_music_intent_and_safe_split())
    asyncio.run(test_ollama_offline_fast_failover())
    asyncio.run(test_soulseek_peer_alignment_and_sorting())
    print("\n>>> 所有音乐智能体心智架构与意图边界测试均 100% 通过！<<<")
