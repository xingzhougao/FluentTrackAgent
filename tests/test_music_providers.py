"""
Unit tests for Step 5 Music Providers & Provider Manager
"""
import sys
import os
import asyncio

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
AGENT_SERVICE_DIR = os.path.join(PROJECT_ROOT, "agent_service")

if AGENT_SERVICE_DIR not in sys.path:
    sys.path.insert(0, AGENT_SERVICE_DIR)

from providers.music.base import TrackCandidate, ProviderCapabilities
from providers.music.web_provider import WebMusicProvider
from providers.music.soulseek_provider import SoulseekMusicProvider
from providers.music.manager import MusicProviderManager


async def test_track_candidate_model():
    cand = TrackCandidate(
        id="test_01",
        title="夜曲",
        artist="周杰伦",
        album="十一月的萧邦",
        duration=226,
        bitrate=320,
        format="mp3",
        size_bytes=9040000,
        url="http://test.url/song.mp3",
        provider="web_music",
        source_type="web",
        confidence=0.95
    )
    assert cand.format_size() == "8.6 MB"
    assert cand.format_duration() == "03:46"
    d = cand.to_dict()
    assert d["title"] == "夜曲"
    assert d["artist"] == "周杰伦"
    assert "download" in d["capabilities"]
    print("✅ test_track_candidate_model passed!")


async def test_web_music_provider():
    provider = WebMusicProvider()
    assert await provider.check_availability() is True

    # 命中已知曲库
    res = await provider.search("反方向的钟", "周杰伦", limit=5)
    assert len(res) >= 1
    assert res[0].title == "反方向的钟"
    assert res[0].artist == "周杰伦"
    assert res[0].confidence >= 0.9

    # 兜底冷门曲目解析
    cold_res = await provider.search("冷门网络新歌xyz", limit=5)
    assert len(cold_res) >= 1
    assert cold_res[0].title == "冷门网络新歌xyz"
    print("✅ test_web_music_provider passed!")


async def test_soulseek_fallback():
    provider = SoulseekMusicProvider(api_base_url="http://127.0.0.1:59999/api/v0", timeout=0.5)
    # 当独立服务不可达时，必须静默降级为 False，且不崩溃
    avail = await provider.check_availability()
    assert avail is False
    res = await provider.search("任意歌曲")
    assert res == []
    print("✅ test_soulseek_fallback passed!")


async def test_provider_manager():
    mgr = MusicProviderManager()
    res = await mgr.search("夜曲", "周杰伦", limit=3)
    assert len(res) >= 1
    top = res[0]
    assert top.title == "夜曲"
    assert top.artist == "周杰伦"
    assert top.bitrate >= 320
    print("✅ test_provider_manager passed!")


async def main():
    print("🚀 运行 Step 5 Music Providers 单元测试集...")
    await test_track_candidate_model()
    await test_web_music_provider()
    await test_soulseek_fallback()
    await test_provider_manager()
    print("🎉 Step 5 Music Providers 全部测试通过！")


if __name__ == "__main__":
    asyncio.run(main())
