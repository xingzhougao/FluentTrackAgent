#ifndef MUSICAGENTCONTROLLER_H
#define MUSICAGENTCONTROLLER_H

#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include "MusicAgentTransport.h"
#include "AgentMessageModel.h"
#include "ToolDispatcher.h"

class PlayerController;
class FavoriteManager;
class MusicLibraryModel;
class PlaylistManager;

class MusicAgentController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool isConnected READ isConnected NOTIFY isConnectedChanged)
    Q_PROPERTY(QString agentStatus READ agentStatus NOTIFY agentStatusChanged)
    Q_PROPERTY(QString statusText READ statusText NOTIFY statusTextChanged)
    Q_PROPERTY(QString currentModel READ currentModel NOTIFY currentModelChanged)
    Q_PROPERTY(AgentMessageModel* messageModel READ messageModel CONSTANT)

public:
    explicit MusicAgentController(QObject *parent = nullptr);
    ~MusicAgentController() override;

    bool isConnected() const;
    QString agentStatus() const;
    QString statusText() const;
    QString currentModel() const;
    AgentMessageModel* messageModel() const;

    void setPlayerController(PlayerController *player);
    void setFavoriteManager(FavoriteManager *favoriteManager);
    void setMusicLibrary(MusicLibraryModel *library);
    void setPlaylistManager(PlaylistManager *playlistManager);

public slots:
    void sendMessage(const QString &text);
    void newSession();
    void updateLlmConfig(const QString &provider, const QString &baseUrl, const QString &apiKey, const QString &modelName, bool enableThinking = false);
    void reconnect();
    void respondConfirmation(const QString &confirmId, bool confirmed);

signals:
    void isConnectedChanged(bool connected);
    void agentStatusChanged(const QString &status);
    void statusTextChanged(const QString &text);
    void currentModelChanged(const QString &model);
    void errorOccurred(const QString &error);
    void confirmationRequired(const QString &confirmId, const QString &title, const QString &message, const QString &details);

private slots:
    void onTransportConnected();
    void onTransportDisconnected();
    void onTransportMessageReceived(const QJsonObject &message);
    void onTransportError(const QString &error);

private:
    MusicAgentTransport *m_transport;
    AgentMessageModel *m_messageModel;
    ToolDispatcher m_toolDispatcher;

    QString m_agentStatus; // "ready", "thinking", "offline"
    QString m_statusText;
    QString m_currentModel;
};

#endif // MUSICAGENTCONTROLLER_H
