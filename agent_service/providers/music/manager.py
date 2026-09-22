"""
MusicProviderManager 多源网络音乐发现调度与聚合管理器
实现：多源异步并发查询、超时熔断、候选去重、下歌吧 (Xiageba) 与 Soulseek P2P 主力优先排序。
"""
import asyncio
import logging
from typing import List, Dict, Optional
from .base import BaseMusicProvider, TrackCandidate
from .xiageba_provider import XiagebaProvider
from .soulseek_provider import SoulseekMusicProvider
from .web_provider import WebMusicProvider

try:
    from utils.chinese_converter import get_artist_variations
except ImportError:
    from agent_service.utils.chinese_converter import get_artist_variations

logger = logging.getLogger("AgentLogger")


class MusicProviderManager:
    """多源网络音乐管理器"""

    def __init__(self):
        self.providers: Dict[str, BaseMusicProvider] = {}
        # 依据用户指示：停用第四级其他网络源 (WebMusicProvider/Meting)，仅保留三大真实主力音源：
        # 1. 下歌吧 (免费商业与无损主力)
        # 2. Soulseek P2P (全球用户共享、无版权限制主力)
        self.register_provider(XiagebaProvider())
        self.register_provider(SoulseekMusicProvider())
        # WebMusicProvider 已停用，杜绝低质网络噪音

    def register_provider(self, provider: BaseMusicProvider):
        """注册新 Provider"""
        self.providers[provider.name] = provider
        logger.info(f"[MusicProviderManager] 注册网络音乐 Provider: {provider.name}")

    def get_provider(self, name: str) -> Optional[BaseMusicProvider]:
        """获取指定名称的 Provider 实例"""
        return self.providers.get(name)

    async def search(
        self,
        query: str,
        artist: str = "",
        limit: int = 5,
        timeout: float = 30.0
    ) -> List[TrackCandidate]:
        """
        多源并发检索、去重与按主力源优先排序
        """
        if not query and not artist:
            return []

        tasks = []
        for name, provider in self.providers.items():
            tasks.append(self._safe_search(provider, query, artist, limit, timeout))

        # 并发执行各 Provider 检索
        provider_results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_candidates: List[TrackCandidate] = []
        for res in provider_results:
            if isinstance(res, list):
                raw_candidates.extend(res)
            elif isinstance(res, Exception):
                logger.warning(f"[MusicProviderManager] Provider 检索执行报错: {res}")

        # 遵照用户核心指令制定三大主力优先级体系（彻底移除第四级其他网络噪音）：
        # 第一级 (Tier 1, 基准 4000分): Soulseek P2P 歌名与歌手均匹配的原版高保真音频
        # 第二级 (Tier 2, 基准 3000分): 歌名匹配但作者不匹配的可直接播放音频 (含翻唱/改编/其他歌手版本)
        # 第三级 (Tier 3, 基准 2000分): 网盘资源 (下歌吧夸克/百度网盘转存，需扫码保底)

        user_wants_remix = any(k in query.lower() for k in ["remix", "dj", "慢摇", "串烧"])
        user_wants_cover = any(k in query.lower() for k in ["cover", "翻唱"])

        trad_query = ""
        try:
            from utils.chinese_converter import to_traditional
            trad_query = to_traditional(query)
        except Exception:
            pass

        deduped: Dict[str, TrackCandidate] = {}
        for cand in raw_candidates:
            v_tag = (cand.extra or {}).get("version_tag", "")
            is_remix = (cand.extra or {}).get("is_remix", False)
            is_cover = (cand.extra or {}).get("is_cover", False)
            is_netdisk = (cand.extra or {}).get("is_netdisk", False)
            art_matches = (cand.extra or {}).get("artist_matches", True)

            # 严格标题校验：曲目标题必须包含搜索关键词 (简繁任一包含)，彻底杜绝无关杂质
            cand_title_l = cand.title.lower()
            q_l = query.strip().lower()
            trad_q_l = trad_query.strip().lower()
            if q_l and (q_l not in cand_title_l and (not trad_q_l or trad_q_l not in cand_title_l)):
                continue

            # 判断歌手是否匹配 (若用户未指定歌手，则默认匹配)
            if artist.strip():
                cand_art_l = cand.artist.lower()
                art_vars = get_artist_variations(artist.strip())
                matched_art = any(v.lower() in cand_art_l or cand_art_l in v.lower() for v in art_vars)
                artist_is_matched = matched_art and art_matches
            else:
                artist_is_matched = True

            # 计算三大梯队基准分 (Tier Base)
            if cand.provider == "soulseek_p2p" and artist_is_matched and not is_remix:
                tier_base = 4000  # 第一级: Soulseek P2P 原版匹配 (绝对优先)
                tier_name = "Soulseek 原版"
                tier_num = 1
            elif cand.provider == "soulseek_p2p" or (not is_netdisk and (not artist_is_matched or is_cover or is_remix)):
                tier_base = 3000  # 第二级: 歌名匹配 但作者不匹配 (直接音频/翻唱)
                tier_name = "歌名匹配但歌手不同"
                tier_num = 2
            elif is_netdisk:
                tier_base = 2000  # 第三级: 网盘资源 (需扫码保底)
                tier_name = "网盘资源"
                tier_num = 3
            else:
                # 任何不属于三大梯队的内容直接丢弃，不予展示
                continue

            # 阶梯内部微调：
            # 1. 置信度打分 (cand.confidence * 80)
            # 2. 无损格式 (FLAC/WAV) +80分
            # 3. 高码率 (>=320k) +40分
            # 4. 未主动索求的 DJ 慢摇惩罚 -150分
            bonus = cand.confidence * 80
            if cand.format in ["flac", "wav"]:
                bonus += 80
            elif cand.bitrate >= 320:
                bonus += 40

            if is_remix and not user_wants_remix:
                bonus -= 150

            adjusted_score = tier_base + bonus
            if not cand.extra:
                cand.extra = {}
            cand.extra["tier_name"] = tier_name
            cand.extra["tier"] = tier_num

            # 区分不同音质或不同版本，保留真实多样性
            norm_key = f"{cand.provider}__{cand.format}__{v_tag}__{cand.title.strip().lower()}__{cand.artist.strip().lower()}"

            if norm_key not in deduped:
                cand._sort_key = (adjusted_score, cand.bitrate)
                deduped[norm_key] = cand
            else:
                existing = deduped[norm_key]
                existing_sort = getattr(existing, "_sort_key", (0, 0))
                if (adjusted_score, cand.bitrate) > existing_sort:
                    cand._sort_key = (adjusted_score, cand.bitrate)
                    deduped[norm_key] = cand

        final_list = list(deduped.values())

        # 智能综合排序：四级梯队最高 > 码率最高
        final_list.sort(
            key=lambda c: getattr(c, "_sort_key", (c.confidence, c.bitrate)),
            reverse=True
        )
        return final_list[:limit]

    async def _safe_search(
        self,
        provider: BaseMusicProvider,
        query: str,
        artist: str,
        limit: int,
        timeout: float
    ) -> List[TrackCandidate]:
        try:
            return await asyncio.wait_for(
                provider.search(query=query, artist=artist, limit=limit),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.debug(f"[MusicProviderManager] Provider {provider.name} 检索超时 ({timeout}s)")
            return []
        except Exception as e:
            logger.debug(f"[MusicProviderManager] Provider {provider.name} 检索失败: {e}")
            return []

    async def resolve_download_url(self, candidate: TrackCandidate) -> Optional[str]:
        """根据候选曲目的 provider 委托解析直链"""
        provider = self.providers.get(candidate.provider)
        if not provider:
            return candidate.url
        try:
            return await provider.resolve_download_url(candidate)
        except Exception as e:
            logger.error(f"[MusicProviderManager] 解析下载链接异常: {e}")
            return candidate.url
