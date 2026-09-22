"""
BaseMusicProvider & TrackCandidate 数据模型定义 (Step 5 核心多源抽象)
声明统一的资源候选格式与 Provider 能力集，规范网络音乐发现体系。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ProviderCapabilities:
    """Provider 能力描述符 (Step 5 Issue 07 落地)"""
    can_search: bool = True
    can_resolve: bool = True
    can_stream: bool = False
    can_download: bool = True

    def to_list(self) -> List[str]:
        caps = []
        if self.can_search:
            caps.append("search")
        if self.can_resolve:
            caps.append("resolve")
        if self.can_stream:
            caps.append("stream")
        if self.can_download:
            caps.append("download")
        return caps


@dataclass
class TrackCandidate:
    """多源网络发现的统一曲目候选实体"""
    id: str
    title: str
    artist: str
    album: str = ""
    duration: int = 0  # 秒
    bitrate: int = 320  # kbps
    format: str = "mp3"
    size_bytes: int = 0
    url: Optional[str] = None
    cover_url: Optional[str] = None
    provider: str = "unknown"
    source_type: str = "web"  # "web" | "p2p" | "api"
    confidence: float = 1.0
    capabilities: List[str] = field(default_factory=lambda: ["search", "resolve", "download"])
    extra: Dict[str, Any] = field(default_factory=dict)

    def format_size(self) -> str:
        """友好展示文件大小"""
        if self.size_bytes <= 0:
            # 根据时长和码率粗略估算大小
            dur = self.duration if self.duration > 0 else 240
            est_bytes = int((self.bitrate * 1000 / 8) * dur)
            mb = est_bytes / (1024 * 1024)
            return f"约 {mb:.1f} MB"
        
        mb = self.size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB"

    def format_duration(self) -> str:
        """展示分:秒"""
        dur = self.duration if self.duration > 0 else 0
        minutes = dur // 60
        seconds = dur % 60
        return f"{minutes:02d}:{seconds:02d}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "duration_str": self.format_duration(),
            "bitrate": self.bitrate,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "size_str": self.format_size(),
            "url": self.url,
            "cover_url": self.cover_url,
            "provider": self.provider,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "capabilities": self.capabilities
        }


class BaseMusicProvider(ABC):
    """网络音乐发现 Provider 抽象基类"""

    def __init__(self, name: str, capabilities: ProviderCapabilities):
        self.name = name
        self.capabilities = capabilities

    @abstractmethod
    async def search(self, query: str, artist: str = "", limit: int = 5) -> List[TrackCandidate]:
        """异步并发检索网络候选曲目"""
        pass

    @abstractmethod
    async def resolve_download_url(self, candidate: TrackCandidate) -> Optional[str]:
        """解析直链或准备下载资源"""
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """检查该 Provider 的服务可用性 (例如服务探针、外置进程健康检查)"""
        pass
