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

logger = logging.getLogger("AgentLogger")


class MusicProviderManager:
    """多源网络音乐管理器"""

    def __init__(self):
        self.providers: Dict[str, BaseMusicProvider] = {}
        # 依据 Step 5 规格说明书顺序注册核心 Provider：
        # 1. 下歌吧 (免费商业与无损主力)
        # 2. Soulseek P2P (全球用户共享、无版权限制主力)
        # 3. WebMusicProvider (开放网络备用与热门歌曲库)
        self.register_provider(XiagebaProvider())
        self.register_provider(SoulseekMusicProvider())
        self.register_provider(WebMusicProvider())

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

        # 优先级权重表：严格优先 Soulseek P2P 与下歌吧 (刘明野)，作为免费高保真主力
        provider_weight = {
            "soulseek_p2p": 1.60,
            "xiageba": 1.45,
            "web_music": 0.80
        }

        user_wants_remix = any(k in query.lower() for k in ["remix", "dj", "慢摇", "串烧"])
        user_wants_cover = any(k in query.lower() for k in ["cover", "翻唱"])

        deduped: Dict[str, TrackCandidate] = {}
        for cand in raw_candidates:
            v_tag = (cand.extra or {}).get("version_tag", "")
            is_remix = (cand.extra or {}).get("is_remix", False)
            is_cover = (cand.extra or {}).get("is_cover", False)
            is_netdisk = (cand.extra or {}).get("is_netdisk", False)

            weight = provider_weight.get(cand.provider, 1.0)
            if is_netdisk:
                weight *= 0.90  # 网盘高品质无损仅轻微折减，依然优先于普通网络翻唱

            # 若用户未明确要求搜 DJ 慢摇，对串烧和慢摇混音版进行强降权，避免挤占原版
            if is_remix and not user_wants_remix:
                weight *= 0.35
            # 若用户未明确要求搜翻唱，对翻唱版进行适度降权
            if is_cover and not user_wants_cover:
                weight *= 0.60

            adjusted_score = cand.confidence * weight

            # 区分不同音质或不同版本，保留真实多样性
            norm_key = f"{cand.provider}__{cand.format}__{v_tag}__{cand.title.strip().lower()}__{cand.artist.strip().lower()}"

            if norm_key not in deduped:
                cand._sort_key = (adjusted_score, cand.bitrate)
                deduped[norm_key] = cand
            else:
                existing = deduped[norm_key]
                existing_sort = getattr(existing, "_sort_key", (existing.confidence, existing.bitrate))
                if (adjusted_score, cand.bitrate) > existing_sort:
                    cand._sort_key = (adjusted_score, cand.bitrate)
                    deduped[norm_key] = cand

        final_list = list(deduped.values())

        # 智能综合排序：加权得分最高 > 码率最高
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
