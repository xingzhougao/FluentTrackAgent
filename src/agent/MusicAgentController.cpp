#include "MusicAgentController.h"
#include "../AppConfig.h"
#include <QDebug>
#include <QUuid>
#include <QSettings>
#include <QProcess>
#include <QProcessEnvironment>
#include <QStandardPaths>
#include <QDir>
#include <QFile>
#include <QTcpSocket>
#include <QCoreApplication>

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

    // 自动拉起本地 Agent 微服务子进程（纯净环境，相对路径推导）
    startAgentService();

    // 默认自动尝试连接本地 Agent 微服务
    m_transport->connectToServer();

    if (qApp) {
        connect(qApp, &QCoreApplication::aboutToQuit, this, &MusicAgentController::stopAgentService);
    }
}

MusicAgentController::~MusicAgentController()
{
    stopAgentService();
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

void MusicAgentController::startAgentService()
{
    // 1. 快速探活 127.0.0.1:8765 是否已有运行中的实例（如开发者在终端单独调试）
    QTcpSocket probeSocket;
    probeSocket.connectToHost(QStringLiteral("127.0.0.1"), 8765);
    if (probeSocket.waitForConnected(200)) {
        qDebug() << "[MusicAgentController] 检测到本地 8765 端口已有 Agent 服务运行，直接复用连接";
        probeSocket.disconnectFromHost();
        return;
    }

    // 2. 定位 agent_service/main.py 相对路径
    QString projRoot = AppConfig::instance().projectRoot();
    QString scriptPath = QDir::cleanPath(projRoot + QStringLiteral("/agent_service/main.py"));
    if (!QFile::exists(scriptPath)) {
        qWarning() << "[MusicAgentController] 未找到 Agent 服务入口脚本:" << scriptPath;
        return;
    }

    // 3. 寻找 Python 解释器
    QString pythonExe = findPythonExecutable();
    qDebug() << "[MusicAgentController] 准备拉起 Agent 微服务，使用 Python:" << pythonExe;
    qDebug() << "[MusicAgentController] 脚本路径:" << scriptPath;

    // 4. 创建子进程并净化环境变量
    if (!m_agentProcess) {
        m_agentProcess = new QProcess(this);
    } else if (m_agentProcess->state() != QProcess::NotRunning) {
        return;
    }

    // 清除可能被外部第三方软件污染的环境变量（如 PYTHONPATH、PYTHONHOME）
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.remove(QStringLiteral("PYTHONPATH"));
    env.remove(QStringLiteral("PYTHONHOME"));
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
    env.insert(QStringLiteral("PYTHONUTF8"), QStringLiteral("1"));
    env.insert(QStringLiteral("PYTHONUNBUFFERED"), QStringLiteral("1"));
    m_agentProcess->setProcessEnvironment(env);
    m_agentProcess->setWorkingDirectory(projRoot);

    // 5. 绑定实时日志输出
    connect(m_agentProcess, &QProcess::readyReadStandardOutput, this, [this]() {
        if (!m_agentProcess) return;
        QByteArray out = m_agentProcess->readAllStandardOutput();
        QString str = QString::fromUtf8(out).trimmed();
        if (!str.isEmpty()) {
            qDebug().noquote() << "[AgentService stdout]" << str;
        }
    });
    connect(m_agentProcess, &QProcess::readyReadStandardError, this, [this]() {
        if (!m_agentProcess) return;
        QByteArray err = m_agentProcess->readAllStandardError();
        QString str = QString::fromUtf8(err).trimmed();
        if (!str.isEmpty()) {
            qDebug().noquote() << "[AgentService stderr]" << str;
        }
    });

    connect(m_agentProcess, &QProcess::errorOccurred, this, [](QProcess::ProcessError error) {
        qWarning() << "[MusicAgentController] Agent 服务进程发生异常，代码:" << error;
    });

    connect(m_agentProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [](int exitCode, QProcess::ExitStatus exitStatus) {
        qDebug() << "[MusicAgentController] Agent 服务进程已退出，退出码:" << exitCode << "状态:" << exitStatus;
    });

    // 6. 启动命令：-E 彻底屏蔽环境变量，-X utf8 开启 UTF-8 模式
    QStringList args;
    args << QStringLiteral("-E")
         << QStringLiteral("-X") << QStringLiteral("utf8")
         << scriptPath
         << QStringLiteral("--host") << QStringLiteral("127.0.0.1")
         << QStringLiteral("--port") << QStringLiteral("8765");

    m_agentProcess->start(pythonExe, args);
    qDebug() << "[MusicAgentController] 已由主程序自动下发 Agent 服务拉起命令";
}

void MusicAgentController::stopAgentService()
{
    if (!m_agentProcess) return;

    if (m_agentProcess->state() != QProcess::NotRunning) {
        qDebug() << "[MusicAgentController] 正在关闭 Agent 微服务子进程...";
        qint64 pid = m_agentProcess->processId();
#ifdef Q_OS_WIN
        if (pid > 0) {
            // Windows 下强制结束进程树，同时清理 Python 及其伴生守护进程（如 slskd.exe）
            QProcess::execute(QStringLiteral("taskkill"),
                              QStringList() << QStringLiteral("/F")
                                            << QStringLiteral("/T")
                                            << QStringLiteral("/PID")
                                            << QString::number(pid));
        }
#else
        m_agentProcess->terminate();
        if (!m_agentProcess->waitForFinished(1500)) {
            m_agentProcess->kill();
        }
#endif
        m_agentProcess->waitForFinished(1000);
        qDebug() << "[MusicAgentController] Agent 微服务子进程已安全清理";
    }
}

QString MusicAgentController::findPythonExecutable() const
{
    QString projRoot = AppConfig::instance().projectRoot();
    QStringList candidates = {
        projRoot + QStringLiteral("/.venv/Scripts/python.exe"),
        projRoot + QStringLiteral("/venv/Scripts/python.exe"),
        projRoot + QStringLiteral("/.venv/bin/python"),
        projRoot + QStringLiteral("/venv/bin/python")
    };

    for (const QString & cand : candidates) {
        if (QFile::exists(cand)) {
            return QDir::toNativeSeparators(cand);
        }
    }

    QString systemPython = QStandardPaths::findExecutable(QStringLiteral("python"));
    if (!systemPython.isEmpty()) {
        return systemPython;
    }

    QString systemPy = QStandardPaths::findExecutable(QStringLiteral("py"));
    if (!systemPy.isEmpty()) {
        return systemPy;
    }

    return QStringLiteral("python");
}

