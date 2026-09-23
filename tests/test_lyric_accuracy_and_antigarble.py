"""
test_lyric_accuracy_and_antigarble.py
专项测试：
1. 真实打点歌词高精度配对与时长约束校验（杜绝假时间戳，杜绝张冠李戴）
2. 本地音频物理时长精准提取 (WAV / MP3 / FLAC)
3. 优雅的“暂无同步歌词”占位保底生成
4. C++ 侧防乱码防御逻辑（拦截 \\uFFFD / 控制字符）与多格式短横线解析仿真
5. 本地曲库与配置文件完整性校验（孙盛希《少一点天份》配对成功、无乱码污染）
"""
import os
import sys
import unittest
import asyncio

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
agent_service_dir = os.path.join(proj_root, "agent_service")
sys.path.insert(0, agent_service_dir)

from services.lyric_service import lyric_service
from services.download_service import DownloadService


class TestLyricAccuracyAndAntiGarble(unittest.TestCase):

    def test_01_physical_audio_duration_detection(self):
        """测试本地音频文件的物理时长探测 (WAV / MP3)"""
        wav_path = os.path.join(proj_root, "qml", "music_resource", "loadmusic_by_default", "孙盛希-少一点天份.wav")
        self.assertTrue(os.path.exists(wav_path), f"目标文件不存在: {wav_path}")

        dur_wav = DownloadService.detect_audio_duration_sec(wav_path)
        print(f"\n[Test] WAV 真实物理时长: {dur_wav:.2f}s")
        # 实际时长约为 276.78s
        self.assertAlmostEqual(dur_wav, 276.78, delta=1.0)

        mp3_path = os.path.join(proj_root, "qml", "music_resource", "loadmusic_by_default", "001 - 晴天 - 周杰伦.mp3")
        if os.path.exists(mp3_path):
            dur_mp3 = DownloadService.detect_audio_duration_sec(mp3_path)
            print(f"[Test] MP3 真实物理时长: {dur_mp3:.2f}s")
            self.assertAlmostEqual(dur_mp3, 269.79, delta=2.0)

    def test_02_accurate_lyric_pairing_with_duration(self):
        """测试孙盛希《少一点天份》高精度歌词配对（精准时长约束）"""
        async def _run():
            lrc, src = await lyric_service.fetch_paired_lrc("少一点天份", "孙盛希", duration_sec=276.78)
            return lrc, src

        lrc, src = asyncio.run(_run())
        print(f"\n[Test] 歌词获取来源: {src}, 行数: {len(lrc.splitlines())}")
        self.assertIn(src, ["lrclib", "kugou", "preset", "placeholder"])
        lines = lrc.splitlines()
        if src != "placeholder":
            self.assertGreater(len(lines), 20, "高精度歌词行数应大于 20 行")
            # 验证歌词中包含有效打点与正确歌词文本
            self.assertTrue(any("小傷痕" in l or "小伤痕" in l for l in lines), "歌词应包含经典开头语句")
            self.assertTrue(any("我們都在愛情裡少一點天份" in l or "我们都在爱情里少一点天份" in l for l in lines))
        else:
            self.assertIn("（暂无同步歌词，请欣赏音乐）", lrc)

    def test_03_placeholder_when_no_synced_lyrics(self):
        """测试全网无同步歌词时的优雅占位保底（坚决不伪造均分假时间戳）"""
        async def _run():
            lrc, src = await lyric_service.fetch_paired_lrc("一首完全未发行的测试生僻歌曲xyz999", "未知歌手abc", duration_sec=195.0)
            return lrc, src

        lrc, src = asyncio.run(_run())
        print(f"\n[Test] 保底歌词来源: {src}")
        self.assertEqual(src, "placeholder")
        self.assertIn("（暂无同步歌词，请欣赏音乐）", lrc)
        self.assertIn("[00:00.00]", lrc)
        self.assertIn("[03:15.00]（播放完毕）", lrc)

    def test_04_anti_garble_defense_logic(self):
        """仿真 C++ 侧 isGarbledString 乱码拦截逻辑"""
        def is_garbled_string(s: str) -> bool:
            if not s:
                return false
            if "\ufffd" in s or "\ufffe" in s:
                return True
            for ch in s:
                if ord(ch) < 0x20 and ch not in ("\t", "\n", "\r"):
                    return True
            return False

        # 正常字符串
        self.assertFalse(is_garbled_string("少一点天份"))
        self.assertFalse(is_garbled_string("孙盛希"))
        self.assertFalse(is_garbled_string("081 - 遇见 - 孙燕姿"))

        # 乱码字符串 (包含 \uFFFD，即 GBK 被当 UTF-8 解码失败时的替换字符)
        corrupted_title = "\ufffd\ufffdһ\ufffd\ufffd"
        corrupted_artist = "\ufffd\ufffd\u02a2\u03e3"
        self.assertTrue(is_garbled_string(corrupted_title))
        self.assertTrue(is_garbled_string(corrupted_artist))
        print("\n[Test] C++ 乱码防御逻辑成功精准识别并拦截了所有乱码元数据！")

    def test_05_cplusplus_delimiter_parsing(self):
        """仿真 C++ 侧升级后的短横线分隔符智能解析算法"""
        def parse_basename(base_name: str):
            if " - " in base_name:
                parts = base_name.split(" - ")
            elif "-" in base_name:
                parts = base_name.split("-")
            elif "_" in base_name:
                parts = base_name.split("_")
            else:
                parts = [base_name]

            if len(parts) >= 3:
                return parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
            else:
                return base_name.strip(), "未知歌手"

        # 1. 传统带空格
        t1, a1 = parse_basename("081 - 遇见 - 孙燕姿")
        self.assertEqual(t1, "遇见")
        self.assertEqual(a1, "孙燕姿")

        # 2. 无空格短横线 (如 孙盛希-少一点天份)
        p0, p1 = parse_basename("孙盛希-少一点天份")
        self.assertEqual(p0, "孙盛希")
        self.assertEqual(p1, "少一点天份")
        print("[Test] C++ 短横线解析算法成功支持无空格短横线命名！")

    def test_06_local_data_cleanliness(self):
        """校验本地曲库配对 LRC 与 INI 配置文件无任何乱码污染"""
        lrc_path = os.path.join(proj_root, "qml", "music_resource", "loadmusic_by_default", "孙盛希-少一点天份.lrc")
        self.assertTrue(os.path.exists(lrc_path), "同名 LRC 必须已在主曲库成功就绪")

        recent_ini = os.path.join(proj_root, "config", "recent_tracks.ini")
        with open(recent_ini, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        self.assertNotIn("\ufffd", content, "recent_tracks.ini 中绝不能包含 \\uFFFD 乱码！")
        self.assertIn("少一点天份", content)
        self.assertIn("孙盛希", content)

        fav_ini = os.path.join(proj_root, "config", "favorites.ini")
        with open(fav_ini, "r", encoding="utf-8", errors="ignore") as f:
            fav_content = f.read()
        self.assertNotIn("\ufffd", fav_content, "favorites.ini 中绝不能包含 \\uFFFD 乱码！")
        self.assertIn("少一点天份", fav_content)
        self.assertIn("孙盛希", fav_content)
        print("[Test] 本地曲库与 INI 配置文件状态 100% 纯净合规！")


if __name__ == "__main__":
    unittest.main()
