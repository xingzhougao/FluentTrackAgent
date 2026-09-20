#include "MusicAgentController.h"
#include <QDebug>
#include <QUuid>

MusicAgentController::MusicAgentController(QObject *parent)
    : QObject(parent)
    , m_transport(new MusicAgentTransport(this))
    , m_messageModel(new AgentMessageModel(this))
    , m_agentStatus("offline")
    , m_statusText("服务未连接")
    , m_currentModel("qwen2.5:7b")
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

    // 3. 构建 user_message 协议包
    QJsonObject payload;
    payload["text"] = trimmed;

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

    if (type == "error") {
        QString errorMsg = payload.value("message").toString();
        m_messageModel->appendSystemMessage(QString("【错误】%1").arg(errorMsg));
        emit errorOccurred(errorMsg);
        return;
    }
}

void MusicAgentController::onTransportError(const QString &error)
{
    qWarning() << "[MusicAgentController] Transport 错误:" << error;
}
