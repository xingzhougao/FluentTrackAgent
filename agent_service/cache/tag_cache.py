"""
AgentTagCache 标签持久化与检索缓存 (基于 Step 4 架构要求)
记录曲目路径、标题、歌手、情绪 (mood)、场景 (scene)、能量度 (energy)、语言 (language)、置信度 (confidence) 与来源 (source)。
"""
import os
import sqlite3
import time
import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("AgentLogger")


class TagRecord(BaseModel):
    """单首歌曲的结构化标签记录"""
    track_path: str
    title: str = ""
    artist: str = ""
    mood: str = ""          # 情绪：开心/欢快/治愈/轻快/温暖/悲伤/平静/浪漫/怀旧
    scene: str = ""         # 场景：日常/工作/写代码/专注/助眠/运动/通勤/放松
    energy: float = 0.5     # 能量感：0.0 (极轻柔纯音/催眠) ~ 1.0 (极快电音/摇滚)
    language: str = "zh"    # 语言：zh (国语/中文), yue (粤语), en (英语), ja (日语), instrumental (纯音乐)
    tags: List[str] = Field(default_factory=list)
    confidence: float = 0.8
    source: str = "heuristic"  # heuristic | llm | rule | manual
    updated_at: float = Field(default_factory=time.time)

def _tag_record_to_dict(self) -> Dict[str, Any]:
    return {
        "track_path": self.track_path,
        "title": self.title,
        "artist": self.artist,
        "mood": self.mood,
        "scene": self.scene,
        "energy": self.energy,
        "language": self.language,
        "tags": self.tags,
        "confidence": self.confidence,
        "source": self.source,
        "updated_at": self.updated_at
    }

TagRecord.to_dict = _tag_record_to_dict


class AgentTagCache:
    """基于 SQLite 的本地音乐标签高效缓存"""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "music_tags.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tag_cache (
                    track_path TEXT PRIMARY KEY,
                    title TEXT,
                    artist TEXT,
                    mood TEXT,
                    scene TEXT,
                    energy REAL,
                    language TEXT,
                    tags TEXT,
                    confidence REAL,
                    source TEXT,
                    updated_at REAL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_mood ON tag_cache(mood);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_scene ON tag_cache(scene);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tag_artist ON tag_cache(artist);")
            conn.commit()

    def get(self, track_path: str) -> Optional[TagRecord]:
        """根据歌曲本地路径获取标签缓存"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tag_cache WHERE track_path = ?", (track_path,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def get_by_title_artist(self, title: str, artist: str = "") -> Optional[TagRecord]:
        """根据标题和歌手查询标签缓存"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if artist:
                cursor.execute(
                    "SELECT * FROM tag_cache WHERE title = ? AND artist = ? LIMIT 1",
                    (title.strip(), artist.strip())
                )
            else:
                cursor.execute(
                    "SELECT * FROM tag_cache WHERE title = ? LIMIT 1",
                    (title.strip(),)
                )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def upsert(self, record: TagRecord):
        """插入或更新单条标签"""
        tags_json = json.dumps(record.tags, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tag_cache (track_path, title, artist, mood, scene, energy, language, tags, confidence, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_path) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    mood = excluded.mood,
                    scene = excluded.scene,
                    energy = excluded.energy,
                    language = excluded.language,
                    tags = excluded.tags,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at;
            """, (
                record.track_path,
                record.title,
                record.artist,
                record.mood,
                record.scene,
                record.energy,
                record.language,
                tags_json,
                record.confidence,
                record.source,
                record.updated_at
            ))
            conn.commit()

    def bulk_upsert(self, records: List[TagRecord]):
        """批量更新标签"""
        if not records:
            return
        data = [
            (
                r.track_path,
                r.title,
                r.artist,
                r.mood,
                r.scene,
                r.energy,
                r.language,
                json.dumps(r.tags, ensure_ascii=False),
                r.confidence,
                r.source,
                r.updated_at
            )
            for r in records
        ]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO tag_cache (track_path, title, artist, mood, scene, energy, language, tags, confidence, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_path) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    mood = excluded.mood,
                    scene = excluded.scene,
                    energy = excluded.energy,
                    language = excluded.language,
                    tags = excluded.tags,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at;
            """, data)
            conn.commit()

    def get_all(self) -> List[TagRecord]:
        """获取所有已缓存的标签记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tag_cache")
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    def count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tag_cache")
            return cursor.fetchone()[0]

    def _row_to_record(self, row: sqlite3.Row) -> TagRecord:
        try:
            tags = json.loads(row["tags"]) if row["tags"] else []
        except Exception:
            tags = []
        return TagRecord(
            track_path=row["track_path"],
            title=row["title"] or "",
            artist=row["artist"] or "",
            mood=row["mood"] or "",
            scene=row["scene"] or "",
            energy=row["energy"] or 0.5,
            language=row["language"] or "zh",
            tags=tags,
            confidence=row["confidence"] or 0.8,
            source=row["source"] or "heuristic",
            updated_at=row["updated_at"] or 0.0
        )
