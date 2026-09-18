#ifndef MUSICAGENTTRANSPORT_H
#define MUSICAGENTTRANSPORT_H

#include <QObject>
#include <QWebSocket>
#include <QJsonObject>
#include <QJsonDocument>
#include <QTimer>
#include <QUrl>

/**
 * @brief 单 WebSocket 全双工通信传输层 (基于架构审查第 1 项)
 * 承载 Qt 客户端与 Python Agent 微服务之间的所有双向消息流通。
 */
class MusicAgentTransport : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool isConnected READ isConnected NOTIFY connectionStateChanged)
    Q_PROPERTY(QString serverUrl READ serverUrl WRITE setServerUrl NOTIFY serverUrlChanged)

public:
    explicit MusicAgentTransport(QObject *parent = nullptr);
    ~MusicAgentTransport() override;

    bool isConnected() const;
    QString serverUrl() const;
    void setServerUrl(const QString &url);

    void setToken(const QString &token);
    QString token() const;

public slots:
    void connectToServer();
    void disconnectFromServer();
    bool sendJson(const QJsonObject &json);

signals:
    void connected();
    void disconnected();
    void connectionStateChanged(bool connected);
    void serverUrlChanged(const QString &url);
    void messageReceived(const QJsonObject &message);
    void errorOccurred(const QString &error);

private slots:
    void onConnected();
    void onDisconnected();
    void onTextMessageReceived(const QString &message);
    void onError(QAbstractSocket::SocketError error);
    void onReconnectTimeout();

private:
    QWebSocket *m_webSocket;
    QTimer *m_reconnectTimer;
    QString m_serverUrl;
    QString m_token;
    bool m_manualClose;
};

#endif // MUSICAGENTTRANSPORT_H
