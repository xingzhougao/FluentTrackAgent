#pragma once

#include <QObject>
#include <QJsonObject>
#include <QPointer>

class PlayerController;
class FavoriteManager;

class ToolDispatcher : public QObject
{
    Q_OBJECT
public:
    explicit ToolDispatcher(QObject *parent = nullptr);
    ~ToolDispatcher() override = default;

    void setPlayerController(PlayerController *player);
    void setFavoriteManager(FavoriteManager *favoriteManager);

    /**
     * @brief 执行指定的原子工具
     * @param toolName 工具名称
     * @param arguments 入参 JSON
     * @return 包含 success, result, error 的标准化回执对象
     */
    QJsonObject executeTool(const QString &toolName, const QJsonObject &arguments);

private:
    QJsonObject handleGetPlayerState();
    QJsonObject handleSetVolume(const QJsonObject &args);
    QJsonObject handlePause();
    QJsonObject handleResume();
    QJsonObject handleTogglePlay();
    QJsonObject handleNextTrack();
    QJsonObject handlePreviousTrack();
    QJsonObject handleToggleFavorite();
    QJsonObject handleSetPlayMode(const QJsonObject &args);
    QJsonObject handleSeek(const QJsonObject &args);

private:
    QPointer<PlayerController> m_player;
    QPointer<FavoriteManager> m_favoriteManager;
};
