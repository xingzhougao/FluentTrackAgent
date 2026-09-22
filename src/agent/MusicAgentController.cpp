#include "MusicAgentController.h"
#include <QDebug>
#include <QUuid>
#include <QSettings>

MusicAgentController::MusicAgentController(QObject *parent)
    : QObject(parent)
    , m_transport(new MusicAgentTransport(this))
    , m_messageModel(new AgentMessageModel(this))
    , m_agentStatus("offline")
    , m_statusText("服务未连接")
    , m_currentModel("qwen2.5:7b")
    , m_autoDownloadMode(QSettings().value("Agent/AutoDownloadMode", false).toBool())
{
    connect(m_transport, &MusicAgentTransport::connected, this, &MusicAgentController::onTransportConnected);
    connect(m_transport, &MusicAgentTransport::disconnected, this, &MusicAgentController::onTransportDisconnected);
    connect(m_transport, &MusicAgentTransport::messageReceived, this, &MusicAgentController::onTransportMessageReceived);
    connect(m_transport, &MusicAgentTransport::errorOccurred, this, &MusicAgentController::onTransportError);

    // 默认自动尝试连接本地 Agent 微服务
    m_transport->connectToServer();
}

MusicAgentController::~MusicAgentController()
{
}

void MusicAgentController::setPlayerController(PlayerController *player)
{
    m_toolDispatcher.setPlayerController(player);
}

void MusicAgentController::setFavoriteManager(FavoriteManager *favoriteManager)
{
    m_toolDispatcher.setFavoriteManager(favoriteManager);
}

void MusicAgentController::setMusicLibrary(MusicLibraryModel *library)
{
    m_toolDispatcher.setMusicLibrary(library);
}

void MusicAgentController::setPlaylistManager(PlaylistManager *playlistManager)
{
    m_toolDispatcher.setPlaylistManager(playlistManager);
}

bool MusicAgentController::isConnected() const
{
    return m_transport->isConnected();
}

QString MusicAgentController::agentStatus() const
{
    return m_agentStatus;
}

QString MusicAgentController::statusText() const
{
    return m_statusText;
}

QString MusicAgentController::currentModel() const
{
    return m_currentModel;
}

bool MusicAgentController::autoDownloadMode() const
{
    return m_autoDownloadMode;
}

void MusicAgentController::setAutoDownloadMode(bool enabled)
{
    if (m_autoDownloadMode == enabled) return;
    m_autoDownloadMode = enabled;
    QSettings settings;
    settings.setValue("Agent/AutoDownloadMode", m_autoDownloadMode);
    emit autoDownloadModeChanged(m_autoDownloadMode);

    if (m_transport->isConnected()) {
        QJsonObject payload;
        payload["auto_download"] = m_autoDownloadMode;
        QJsonObject req;
        req["type"] = "update_preference";
        req["request_id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
        req["payload"] = payload;
        m_transport->sendJson(req);
    }
}

AgentMessageModel* MusicAgentController::messageModel() const
{
    return m_messageModel;
}

void MusicAgentController::sendMessage(const QString &text)
{
    QString trimmed = text.trimmed();
    if (trimmed.isEmpty()) return;

    // 1. 本地立即追加用户消息
    m_messageModel->appendUserMessage(trimmed);

    // 2. 检查连接状态
    if (!m_transport->isConnected()) {
        m_messageModel->appendSystemMessage("【提示】未连接到 AI Agent 服务 (127.0.0.1:8765)，正在尝试重连...");
        m_transport->connectToServer();
        return;
    }

    // 3. 构建 user_message 协议包 (携带 auto_download 偏好模式)
    QJsonObject payload;
    payload["text"] = trimmed;
    payload["auto_download"] = m_autoDownloadMode;

    QJsonObject req;
    req["type"] = "user_message";
    req["request_id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
    req["payload"] = payload;

    m_agentStatus = "thinking";
    m_statusText = "思考决策中...";
    emit agentStatusChanged(m_agentStatus);
    emit statusTextChanged(m_statusText);

    // 预先占位 assistant 气泡（置为思考态）
    m_messageModel->startAssistantMessage();

    m_transport->sendJson(req);
}

void MusicAgentController::newSession()
{
    m_messageModel->clear();
    if (m_transport->isConnected()) {
        QJsonObject req;
        req["type"] = "clear_context";
        req["request_id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
        m_transport->sendJson(req);
    }
    m_agentStatus = m_transport->isConnected() ? "ready" : "offline";
    m_statusText = m_transport->isConnected() ? "已就绪" : "服务未连接";
    emit agentStatusChanged(m_agentStatus);
    emit statusTextChanged(m_statusText);
}

void MusicAgentController::updateLlmConfig(const QString &provider, const QString &baseUrl, const QString &apiKey, const QString &modelName, bool enableThinking)
{
    if (!m_transport->isConnected()) return;

    QJsonObject payload;
    payload["provider_type"] = provider;
    payload["enable_thinking"] = enableThinking;
    if (provider == "local") {
        payload["local_base_url"] = baseUrl;
        payload["local_model"] = modelName;
    } else {
        payload["cloud_base_url"] = baseUrl;
        payload["cloud_api_key"] = apiKey;
        payload["cloud_model"] = modelName;
    }

    QJsonObject req;
    req["type"] = "update_llm_config";
    req["request_id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
    req["payload"] = payload;

    m_transport->sendJson(req);
    m_currentModel = modelName;
    emit currentModelChanged(m_currentModel);
}

void MusicAgentController::reconnect()
{
    m_transport->connectToServer();
}

void MusicAgentController::onTransportConnected()
{
    m_agentStatus = "ready";
    m_statusText = "已就绪 (127.0.0.1:8765)";
    emit isConnectedChanged(true);
    emit agentStatusChanged(m_agentStatus);
    emit statusTextChanged(m_statusText);

    // 连接建立后即刻同步当前下载模式偏好
    QJsonObject prefPayload;
    prefPayload["auto_download"] = m_autoDownloadMode;
    QJsonObject prefReq;
    prefReq["type"] = "update_preference";
    prefReq["request_id"] = QUuid::createUuid().toString(QUuid::WithoutBraces);
    prefReq["payload"] = prefPayload;
    m_transport->sendJson(prefReq);
}

void MusicAgentController::onTransportDisconnected()
{
    m_agentStatus = "offline";
    m_statusText = "服务未连接 (正在自动重试...)";
    emit isConnectedChanged(false);
    emit agentStatusChanged(m_agentStatus);
    emit statusTextChanged(m_statusText);
}

void MusicAgentController::onTransportMessageReceived(const QJsonObject &message)
{
    QString type = message.value("type").toString();
    QJsonObject payload = message.value("payload").toObject();

    if (type == "connected") {
        QString model = payload.value("model").toString();
        if (!model.isEmpty()) {
            m_currentModel = model;
            emit currentModelChanged(m_currentModel);
        }
        return;
    }

    if (type == "status_update") {
        QString status = payload.value("status").toString();
        QString msg = payload.value("message").toString();
        m_agentStatus = status;
        m_statusText = msg;
        emit agentStatusChanged(m_agentStatus);
        emit statusTextChanged(m_statusText);
        return;
    }

    if (type == "assistant_delta") {
        QString deltaType = payload.value("delta_type").toString(); // "think" or "answer"
        QString text = payload.value("text").toString();
        m_messageModel->appendDelta(deltaType, text);
        return;
    }

    if (type == "assistant_message") {
        QString content = payload.value("content").toString();
        QString thinking = payload.value("thinking_content").toString();
        int durationMs = payload.value("duration_ms").toInt();
        QJsonArray toolsArr = payload.value("tools").toArray();
        QVariantList toolsList;
        for (const auto &val : toolsArr) {
            toolsList.append(val.toVariant());
        }
        m_messageModel->finishAssistantMessage(content, thinking, durationMs, toolsList);
        return;
    }

    if (type == "tool_request") {
        QString requestId = message.value("request_id").toString();
        QString toolCallId = payload.value("tool_call_id").toString();
        QString toolName = payload.value("tool_name").toString();
        QJsonObject arguments = payload.value("arguments").toObject();

        qDebug() << "[MusicAgentController] 收到原子工具调用请求:" << toolName << arguments;
        QJsonObject toolExecRes = m_toolDispatcher.executeTool(toolName, arguments);

        // 构建并回传 tool_result
        QJsonObject reply;
        reply["type"] = "tool_result";
        reply["request_id"] = requestId;

        QJsonObject replyPayload;
        replyPayload["tool_call_id"] = toolCallId;
        replyPayload["tool_name"] = toolName;
        replyPayload["success"] = toolExecRes.value("success").toBool(false);
        replyPayload["result"] = toolExecRes.value("result").toObject();
        replyPayload["error"] = toolExecRes.value("error").toString();

        reply["payload"] = replyPayload;
        m_transport->sendJson(reply);
        return;
    }

    if (type == "confirmation_required") {
        QString confirmId = message.value("confirm_id").toString();
        QString title = payload.value("title").toString("操作确认");
        QString msg = payload.value("message").toString();
        QString details = payload.value("details").toString();

        qInfo() << "[MusicAgentController] 收到人工确认请求:" << confirmId << title << msg;
        emit confirmationRequired(confirmId, title, msg, details);
        return;
    }

    if (type == "candidate_selection_required") {
        QString confirmId = message.value("confirm_id").toString();
        QString title = payload.value("title").toString("选择要下载的音乐版本");
        QString query = payload.value("query").toString();
        QString artist = payload.value("artist").toString();
        QJsonArray candidates = payload.value("candidates").toArray();

        qInfo() << "[MusicAgentController] 收到候选版本多选弹窗请求:" << confirmId << "曲目:" << query << "候选数:" << candidates.size();
        emit candidateSelectionRequired(confirmId, title, query, artist, candidates);
        return;
    }

    if (type == "no_source_found") {
        QString title = payload.value("title").toString("未找到音源");
        QString msg = payload.value("message").toString("抱歉暂时找不到对应音源哦");
        QString query = payload.value("query").toString();
        QString artist = payload.value("artist").toString();

        qInfo() << "[MusicAgentController] 收到未找到对应音源通知:" << query << artist << msg;
        emit noSourceFound(msg, query, artist);
        return;
    }

    if (type == "error") {
        QString errorMsg = payload.value("message").toString();
        m_messageModel->appendSystemMessage(QString("【错误】%1").arg(errorMsg));
        emit errorOccurred(errorMsg);
        return;
    }
}

void MusicAgentController::respondConfirmation(const QString &confirmId, bool confirmed)
{
    if (!m_transport || !m_transport->isConnected()) {
        qWarning() << "[MusicAgentController] Transport 未连接，无法发送 confirmation_response";
        return;
    }

    QJsonObject reply;
    reply["type"] = "confirmation_response";
    reply["confirm_id"] = confirmId;

    QJsonObject payload;
    payload["confirm_id"] = confirmId;
    payload["confirmed"] = confirmed;
    reply["payload"] = payload;

    qInfo() << "[MusicAgentController] 回传人工确认响应:" << confirmId << "confirmed:" << confirmed;
    m_transport->sendJson(reply);
}

void MusicAgentController::respondCandidateSelection(const QString &confirmId, const QString &selectedId, bool cancelled)
{
    if (!m_transport || !m_transport->isConnected()) {
        qWarning() << "[MusicAgentController] Transport 未连接，无法发送 candidate_selection_response";
        return;
    }

    QJsonObject reply;
    reply["type"] = "candidate_selection_response";
    reply["confirm_id"] = confirmId;

    QJsonObject payload;
    payload["confirm_id"] = confirmId;
    payload["selected_id"] = selectedId;
    payload["cancelled"] = cancelled;
    reply["payload"] = payload;

    qInfo() << "[MusicAgentController] 回传候选版本选择响应:" << confirmId << "selectedId:" << selectedId << "cancelled:" << cancelled;
    m_transport->sendJson(reply);
}

void MusicAgentController::onTransportError(const QString &error)
{
    qWarning() << "[MusicAgentController] Transport 错误:" << error;
}
