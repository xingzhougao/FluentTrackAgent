#include "ToolDispatcher.h"
#include "../PlayerController.h"
#include "../FavoriteManager.h"
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
