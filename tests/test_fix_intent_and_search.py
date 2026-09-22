import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent_service")))

from runtime.intent_router import extract_music_entity, IntentRouter


class TestIntentAndSearchFix(unittest.TestCase):

    def test_liaojuntao_shui_normal(self):
        text = "播放一下 廖俊涛的谁"
        ent = extract_music_entity(text)
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "廖俊涛")
        self.assertEqual(ent[1], "谁")

    def test_liaojuntao_shui_gequ(self):
        text = "播放一下廖俊涛的歌曲 谁"
        ent = extract_music_entity(text)
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "廖俊涛")
        self.assertEqual(ent[1], "谁")

    def test_complaint_and_directive(self):
        text = "不是啊 你给错了啊 是廖俊涛的歌曲谁 你要去搜索本地没有"
        ent = extract_music_entity(text)
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "廖俊涛")
        self.assertEqual(ent[1], "谁")

        rule = IntentRouter.match_rule(text)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.params.get("artist"), "廖俊涛")
        self.assertEqual(rule.params.get("query"), "谁")

    def test_complaint_zhoujielun(self):
        text = "你给错了 我要的是周杰伦的晴天"
        ent = extract_music_entity(text)
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "周杰伦")
        self.assertEqual(ent[1], "晴天")

    def test_jianxin(self):
        text = "播放一下 剑心"
        ent = extract_music_entity(text)
        self.assertIsNotNone(ent)
        self.assertEqual(ent[0], "")
        self.assertEqual(ent[1], "剑心")

    def test_search_and_play_rejects_wrong_artist(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from workflows.search_and_play_workflow import SearchAndPlayWorkflow

        mock_runtime = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.last_recommended_tracks = []
        mock_runtime.context_manager.get_session.return_value = mock_ctx

        # 模拟本地只检索到林俊杰的《不为谁而作的歌》
        mock_runtime.call_client_tool = AsyncMock(return_value={
            "success": True,
            "result": {
                "tracks": [
                    {"index": 33, "title": "不为谁而作的歌", "artist": "林俊杰"}
                ]
            }
        })

        # 模拟网络检索工作流
        mock_network_wf = MagicMock()
        mock_network_wf.execute = AsyncMock(return_value=MagicMock(success=True, answer_text="网络命中廖俊涛的《谁》"))
        mock_runtime.network_discovery_workflow = mock_network_wf

        wf = SearchAndPlayWorkflow(mock_runtime)

        # 执行“廖俊涛的谁”
        res = asyncio.run(wf.execute(
            session_id="default",
            request_id="test-1",
            query="谁",
            artist="廖俊涛",
            raw_text="播放一下 廖俊涛的谁"
        ))

        # 必须流转到网络检索，严禁播放林俊杰！
        mock_network_wf.execute.assert_called_once()
        call_kwargs = mock_network_wf.execute.call_args[1]
        self.assertEqual(call_kwargs.get("artist"), "廖俊涛")
        self.assertEqual(call_kwargs.get("query"), "谁")
        print(" [TEST PASSED] SearchAndPlayWorkflow 成功拒绝误播林俊杰，并精准流转至网络检索廖俊涛！")


if __name__ == "__main__":
    unittest.main()
