#ifndef AGENTMESSAGEMODEL_H
#define AGENTMESSAGEMODEL_H

#include <QAbstractListModel>
#include <QVariantList>
#include <QDateTime>

struct AgentMessageItem {
    QString role;            // "user", "assistant", "system"
    QString content;         // 回复正文
    QString thinkingContent; // R1 推理思考过程
    bool isThinking = false; // 是否在思考中
    int durationMs = 0;      // 耗时毫秒
    QVariantList tools;      // 工具调用卡片列表
    QString timestamp;
};

class AgentMessageModel : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(int count READ count NOTIFY countChanged)

public:
    enum AgentRoles {
        RoleRole = Qt::UserRole + 1,
        ContentRole,
        ThinkingContentRole,
        IsThinkingRole,
        DurationMsRole,
        ToolsRole,
        TimestampRole
    };

    explicit AgentMessageModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QHash<int, QByteArray> roleNames() const override;

    int count() const;

public slots:
    void appendUserMessage(const QString &content);
    void startAssistantMessage();
    void appendDelta(const QString &deltaType, const QString &text);
    void finishAssistantMessage(const QString &content, const QString &thinking, int durationMs, const QVariantList &tools);
    void appendSystemMessage(const QString &content);
    void clear();

signals:
    void countChanged();

private:
    QList<AgentMessageItem> m_messages;
};

#endif // AGENTMESSAGEMODEL_H
