#include "MusicAgentTransport.h"
#include <QDebug>
#include <QUrlQuery>

MusicAgentTransport::MusicAgentTransport(QObject *parent)
    : QObject(parent)
    , m_webSocket(new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this))
    , m_reconnectTimer(new QTimer(this))
    , m_serverUrl("ws://127.0.0.1:8765/ws")
    , m_token("")
    , m_manualClose(false)
{
    connect(m_webSocket, &QWebSocket::connected, this, &MusicAgentTransport::onConnected);
    connect(m_webSocket, &QWebSocket::disconnected, this, &MusicAgentTransport::onDisconnected);
    connect(m_webSocket, &QWebSocket::textMessageReceived, this, &MusicAgentTransport::onTextMessageReceived);
    connect(m_webSocket, QOverload<QAbstractSocket::SocketError>::of(&QWebSocket::errorOccurred),
            this, &MusicAgentTransport::onError);

    m_reconnectTimer->setInterval(3000);
    connect(m_reconnectTimer, &QTimer::timeout, this, &MusicAgentTransport::onReconnectTimeout);
}

MusicAgentTransport::~MusicAgentTransport()
{
    m_manualClose = true;
    m_reconnectTimer->stop();
    m_webSocket->close();
}

bool MusicAgentTransport::isConnected() const
{
    return m_webSocket && m_webSocket->state() == QAbstractSocket::ConnectedState;
}

QString MusicAgentTransport::serverUrl() const
{
    return m_serverUrl;
}

void MusicAgentTransport::setServerUrl(const QString &url)
{
    if (m_serverUrl != url) {
        m_serverUrl = url;
        emit serverUrlChanged(url);
    }
}

void MusicAgentTransport::setToken(const QString &token)
{
    m_token = token;
}

QString MusicAgentTransport::token() const
{
    return m_token;
}

void MusicAgentTransport::connectToServer()
{
    if (isConnected()) return;

    m_manualClose = false;
    QUrl url(m_serverUrl);
    QUrlQuery query(url);
    query.addQueryItem("session_id", "default");
    if (!m_token.isEmpty()) {
        query.addQueryItem("token", m_token);
    }
    url.setQuery(query);

    qDebug() << "[MusicAgentTransport] 正在连接 WebSocket:" << url.toString();
    m_webSocket->open(url);
}

void MusicAgentTransport::disconnectFromServer()
{
    m_manualClose = true;
    m_reconnectTimer->stop();
    if (m_webSocket) {
        m_webSocket->close();
    }
}

bool MusicAgentTransport::sendJson(const QJsonObject &json)
{
    if (!isConnected()) {
        qWarning() << "[MusicAgentTransport] 无法发送消息，WebSocket 未就绪";
        return false;
    }

    QJsonDocument doc(json);
    QString text = QString::fromUtf8(doc.toJson(QJsonDocument::Compact));
    qint64 sent = m_webSocket->sendTextMessage(text);
    return sent > 0;
}

void MusicAgentTransport::onConnected()
{
    qDebug() << "[MusicAgentTransport] WebSocket 已连接成功";
    m_reconnectTimer->stop();
    emit connected();
    emit connectionStateChanged(true);
}

void MusicAgentTransport::onDisconnected()
{
    qDebug() << "[MusicAgentTransport] WebSocket 连接已断开";
    emit disconnected();
    emit connectionStateChanged(false);

    if (!m_manualClose && !m_reconnectTimer->isActive()) {
        m_reconnectTimer->start();
    }
}

void MusicAgentTransport::onTextMessageReceived(const QString &message)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(message.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        qWarning() << "[MusicAgentTransport] 收到非合法 JSON 消息:" << message;
        return;
    }

    emit messageReceived(doc.object());
}

void MusicAgentTransport::onError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error)
    QString errStr = m_webSocket->errorString();
    emit errorOccurred(errStr);

    if (!m_manualClose && !m_reconnectTimer->isActive()) {
        m_reconnectTimer->start();
    }
}

void MusicAgentTransport::onReconnectTimeout()
{
    if (!isConnected() && !m_manualClose) {
        connectToServer();
    }
}
