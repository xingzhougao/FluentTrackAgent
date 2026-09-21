#include "ToolDispatcher.h"
#include "../PlayerController.h"
#include "../FavoriteManager.h"
#include "../MusicLibraryModel.h"
#include "../PlaylistManager.h"
#include <QJsonArray>
#include <QDebug>
#include <algorithm>

ToolDispatcher::ToolDispatcher(QObject *parent)
    : QObject(parent)
{
}

void ToolDispatcher::setPlayerController(PlayerController *player)
{
    m_player = player;
}

void ToolDispatcher::setFavoriteManager(FavoriteManager *favoriteManager)
{
    m_favoriteManager = favoriteManager;
}

void ToolDispatcher::setMusicLibrary(MusicLibraryModel *library)
{
    m_library = library;
}

void ToolDispatcher::setPlaylistManager(PlaylistManager *playlistManager)
{
    m_playlistManager = playlistManager;
}

QJsonObject ToolDispatcher::executeTool(const QString &toolName, const QJsonObject &arguments)
{
    QJsonObject response;
    response["tool_name"] = toolName;

    if (!m_player) {
        response["success"] = false;
        response["error"] = "PlayerController 实例未就绪";
        response["result"] = QJsonObject();
        return response;
    }

    try {
        if (toolName == "get_player_state") {
            response["result"] = handleGetPlayerState();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "set_volume") {
            response["result"] = handleSetVolume(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "pause") {
            response["result"] = handlePause();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "resume") {
            response["result"] = handleResume();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "toggle_play") {
            response["result"] = handleTogglePlay();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "next_track") {
            response["result"] = handleNextTrack();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "previous_track") {
            response["result"] = handlePreviousTrack();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "toggle_favorite") {
            response["result"] = handleToggleFavorite();
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "set_play_mode") {
            response["result"] = handleSetPlayMode(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "seek") {
            response["result"] = handleSeek(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "search_local_music") {
            response["result"] = handleSearchLocalMusic(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "play_local_track") {
            response["result"] = handlePlayLocalTrack(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "create_temp_playlist") {
            response["result"] = handleCreateTempPlaylist(arguments);
            response["success"] = true;
            response["error"] = "";
        } else if (toolName == "get_local_library_overview") {
            response["result"] = handleGetLocalLibraryOverview();
            response["success"] = true;
            response["error"] = "";
        } else {
            response["success"] = false;
            response["error"] = QString("未知的原子工具名称: %1").arg(toolName);
            response["result"] = QJsonObject();
        }
    } catch (const std::exception &e) {
        response["success"] = false;
        response["error"] = QString("执行异常: %1").arg(e.what());
        response["result"] = QJsonObject();
    }

    return response;
}

QJsonObject ToolDispatcher::handleGetPlayerState()
{
    QJsonObject state;
    state["title"] = m_player->title();
    state["artist"] = m_player->artist();
    state["album"] = m_player->album();
    state["cover_url"] = m_player->coverUrl();
    state["playing"] = m_player->playing();
    state["volume"] = static_cast<int>(m_player->volume() * 100);
    state["position_ms"] = m_player->position();
    state["duration_ms"] = m_player->duration();
    state["muted"] = m_player->muted();
    state["is_favorite"] = m_player->favorite();
    state["play_mode"] = m_player->playMode();
    state["current_index"] = m_player->currentIndex();
    return state;
}

QJsonObject ToolDispatcher::handleSetVolume(const QJsonObject &args)
{
    int prevVol = static_cast<int>(m_player->volume() * 100);
    double targetVol = 50.0;

    if (args.contains("volume")) {
        targetVol = args["volume"].toDouble();
    } else if (args.contains("delta")) {
        targetVol = prevVol + args["delta"].toDouble();
    }

    // 护栏限制 0 ~ 100
    targetVol = std::max(0.0, std::min(100.0, targetVol));
    m_player->setVolume(targetVol / 100.0);

    QJsonObject res;
    res["previous_volume"] = prevVol;
    res["current_volume"] = static_cast<int>(targetVol);
    return res;
}

QJsonObject ToolDispatcher::handlePause()
{
    if (m_player->playing()) {
        m_player->togglePlay();
    }
    QJsonObject res;
    res["status"] = "paused";
    res["playing"] = m_player->playing();
    return res;
}

QJsonObject ToolDispatcher::handleResume()
{
    if (!m_player->playing()) {
        m_player->togglePlay();
    }
    QJsonObject res;
    res["status"] = "playing";
    res["playing"] = m_player->playing();
    return res;
}

QJsonObject ToolDispatcher::handleTogglePlay()
{
    m_player->togglePlay();
    QJsonObject res;
    res["playing"] = m_player->playing();
    return res;
}

QJsonObject ToolDispatcher::handleNextTrack()
{
    m_player->next();
    QJsonObject res;
    res["title"] = m_player->title();
    res["artist"] = m_player->artist();
    return res;
}

QJsonObject ToolDispatcher::handlePreviousTrack()
{
    m_player->previous();
    QJsonObject res;
    res["title"] = m_player->title();
    res["artist"] = m_player->artist();
    return res;
}

QJsonObject ToolDispatcher::handleToggleFavorite()
{
    m_player->toggleFavorite();
    QJsonObject res;
    res["is_favorite"] = m_player->favorite();
    res["title"] = m_player->title();
    return res;
}

QJsonObject ToolDispatcher::handleSetPlayMode(const QJsonObject &args)
{
    int mode = args.value("mode").toInt(0);
    mode = std::max(0, std::min(2, mode));
    m_player->setPlayMode(mode);
    QJsonObject res;
    res["play_mode"] = mode;
    return res;
}

QJsonObject ToolDispatcher::handleSeek(const QJsonObject &args)
{
    qint64 posMs = 0;
    if (args.contains("position_ms")) {
        posMs = static_cast<qint64>(args["position_ms"].toDouble());
    } else if (args.contains("position_seconds")) {
        posMs = static_cast<qint64>(args["position_seconds"].toDouble() * 1000);
    }
    posMs = std::max(qint64(0), std::min(m_player->duration(), posMs));
    m_player->seek(posMs);
    QJsonObject res;
    res["position_ms"] = posMs;
    return res;
}

QJsonObject ToolDispatcher::handleSearchLocalMusic(const QJsonObject &args)
{
    if (!m_library) {
        throw std::runtime_error("本地音乐库未就绪");
    }

    QString query = args.value("query").toString().trimmed();
    int limit = args.value("limit").toInt(10);
    if (limit <= 0) limit = 10;

    struct ScoredTrack {
        int index;
        MusicTrack track;
        int score;
        bool isFavorite;
    };

    QVector<ScoredTrack> matches;
    const int total = m_library->count();

    for (int i = 0; i < total; ++i) {
        const MusicTrack t = m_library->trackAt(i);
        bool isFav = m_favoriteManager ? m_favoriteManager->isFavorite(t.filePath) : t.favorite;

        if (query.isEmpty() || query == "*") {
            matches.append({i, t, 10, isFav});
            continue;
        }

        int score = 0;
        if (t.title.compare(query, Qt::CaseInsensitive) == 0) {
            score = 100;
        } else if (t.artist.compare(query, Qt::CaseInsensitive) == 0) {
            score = 80;
        } else if (t.title.contains(query, Qt::CaseInsensitive)) {
            score = 60;
        } else if (t.artist.contains(query, Qt::CaseInsensitive)) {
            score = 50;
        } else if (t.album.contains(query, Qt::CaseInsensitive)) {
            score = 30;
        }

        if (score > 0) {
            matches.append({i, t, score, isFav});
        }
    }

    std::sort(matches.begin(), matches.end(), [](const ScoredTrack &a, const ScoredTrack &b) {
        return a.score > b.score;
    });

    QJsonArray trackArr;
    int takeCount = std::min(limit, static_cast<int>(matches.size()));
    for (int i = 0; i < takeCount; ++i) {
        const auto &m = matches[i];
        QJsonObject item;
        item["index"] = m.index;
        item["title"] = m.track.title;
        item["artist"] = m.track.artist;
        item["album"] = m.track.album;
        item["file_path"] = m.track.filePath;
        item["duration_ms"] = m.track.duration;
        item["is_favorite"] = m.isFavorite;
        item["score"] = m.score;
        trackArr.append(item);
    }

    QJsonObject res;
    res["tracks"] = trackArr;
    res["match_count"] = matches.size();
    res["total_library_tracks"] = total;
    return res;
}

QJsonObject ToolDispatcher::handlePlayLocalTrack(const QJsonObject &args)
{
    if (!m_library) {
        throw std::runtime_error("本地音乐库未就绪");
    }

    int targetIndex = -1;

    if (args.contains("index")) {
        targetIndex = args.value("index").toInt(-1);
    } else if (args.contains("file_path")) {
        QString path = args.value("file_path").toString();
        targetIndex = m_library->indexOfFilePath(path);
    } else if (args.contains("title")) {
        QString title = args.value("title").toString().trimmed();
        for (int i = 0; i < m_library->count(); ++i) {
            const MusicTrack t = m_library->trackAt(i);
            if (t.title.compare(title, Qt::CaseInsensitive) == 0 ||
                t.title.contains(title, Qt::CaseInsensitive)) {
                targetIndex = i;
                break;
            }
        }
    }

    if (targetIndex < 0 || targetIndex >= m_library->count()) {
        throw std::runtime_error("未在本地曲库找到该曲目或索引超出范围");
    }

    m_player->playFromModel(m_library, targetIndex);

    MusicTrack t = m_library->trackAt(targetIndex);
    QJsonObject res;
    res["status"] = "playing";
    res["index"] = targetIndex;
    res["title"] = t.title;
    res["artist"] = t.artist;
    res["album"] = t.album;
    res["file_path"] = t.filePath;
    return res;
}

QJsonObject ToolDispatcher::handleCreateTempPlaylist(const QJsonObject &args)
{
    if (!m_playlistManager) {
        throw std::runtime_error("PlaylistManager 实例未就绪");
    }
    if (!m_library) {
        throw std::runtime_error("本地音乐库未就绪");
    }

    QString name = args.value("name").toString("AI智能推荐歌单");
    bool autoPlay = args.value("auto_play").toBool(true);
    QJsonArray indices = args.value("track_indices").toArray();
    QJsonArray paths = args.value("track_paths").toArray();

    QString playlistId = m_playlistManager->createPlaylist(name);
    MusicLibraryModel *plModel = m_playlistManager->getPlaylistModel(playlistId);

    int addedCount = 0;
    if (!indices.isEmpty()) {
        for (const auto &val : indices) {
            int idx = val.toInt(-1);
            if (idx >= 0 && idx < m_library->count()) {
                if (m_playlistManager->addTrackToPlaylist(playlistId, m_library, idx)) {
                    addedCount++;
                }
            }
        }
    } else if (!paths.isEmpty()) {
        for (const auto &val : paths) {
            QString p = val.toString();
            int idx = m_library->indexOfFilePath(p);
            if (idx >= 0) {
                if (m_playlistManager->addTrackToPlaylist(playlistId, m_library, idx)) {
                    addedCount++;
                }
            }
        }
    }

    if (autoPlay && plModel && plModel->count() > 0) {
        m_player->playFromModel(plModel, 0);
    }

    QJsonObject res;
    res["playlist_id"] = playlistId;
    res["playlist_name"] = name;
    res["track_count"] = addedCount;
    res["auto_played"] = autoPlay;
    return res;
}

QJsonObject ToolDispatcher::handleGetLocalLibraryOverview()
{
    if (!m_library) {
        throw std::runtime_error("本地音乐库未就绪");
    }

    const int total = m_library->count();
    QJsonArray sampleArr;
    int limit = std::min(total, 50);

    for (int i = 0; i < limit; ++i) {
        MusicTrack t = m_library->trackAt(i);
        QJsonObject item;
        item["index"] = i;
        item["title"] = t.title;
        item["artist"] = t.artist;
        sampleArr.append(item);
    }

    QJsonObject res;
    res["total_tracks"] = total;
    res["sample_tracks"] = sampleArr;
    return res;
}
