#include "AgentMessageModel.h"

AgentMessageModel::AgentMessageModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int AgentMessageModel::rowCount(const QModelIndex &parent) const
{
    if (parent.isValid()) return 0;
    return m_messages.size();
}

QVariant AgentMessageModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_messages.size())
        return QVariant();

    const auto &item = m_messages.at(index.row());
    switch (role) {
    case RoleRole: return item.role;
    case ContentRole: return item.content;
    case ThinkingContentRole: return item.thinkingContent;
    case IsThinkingRole: return item.isThinking;
    case DurationMsRole: return item.durationMs;
    case ToolsRole: return item.tools;
    case TimestampRole: return item.timestamp;
    default: return QVariant();
    }
}

QHash<int, QByteArray> AgentMessageModel::roleNames() const
{
    QHash<int, QByteArray> roles;
    roles[RoleRole] = "role";
    roles[ContentRole] = "content";
    roles[ThinkingContentRole] = "thinkingContent";
    roles[IsThinkingRole] = "isThinking";
    roles[DurationMsRole] = "durationMs";
    roles[ToolsRole] = "tools";
    roles[TimestampRole] = "timestamp";
    return roles;
}

int AgentMessageModel::count() const
{
    return m_messages.size();
}

void AgentMessageModel::appendUserMessage(const QString &content)
{
    beginInsertRows(QModelIndex(), m_messages.size(), m_messages.size());
    AgentMessageItem item;
    item.role = "user";
    item.content = content;
    item.timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    m_messages.append(item);
    endInsertRows();
    emit countChanged();
}

void AgentMessageModel::startAssistantMessage()
{
    beginInsertRows(QModelIndex(), m_messages.size(), m_messages.size());
    AgentMessageItem item;
    item.role = "assistant";
    item.isThinking = true;
    item.timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    m_messages.append(item);
    endInsertRows();
    emit countChanged();
}

void AgentMessageModel::appendDelta(const QString &deltaType, const QString &text)
{
    if (m_messages.isEmpty() || m_messages.last().role != "assistant") {
        startAssistantMessage();
    }

    int lastIdx = m_messages.size() - 1;
    auto &item = m_messages[lastIdx];

    if (deltaType == "think") {
        item.thinkingContent.append(text);
        item.isThinking = true;
    } else {
        item.content.append(text);
        item.isThinking = false;
    }

    QModelIndex idx = index(lastIdx);
    emit dataChanged(idx, idx, {ContentRole, ThinkingContentRole, IsThinkingRole});
}

void AgentMessageModel::finishAssistantMessage(const QString &content, const QString &thinking, int durationMs, const QVariantList &tools)
{
    if (m_messages.isEmpty() || m_messages.last().role != "assistant") {
        startAssistantMessage();
    }

    int lastIdx = m_messages.size() - 1;
    auto &item = m_messages[lastIdx];
    if (!content.isEmpty()) {
        item.content = content;
    }
    if (!thinking.isEmpty()) {
        item.thinkingContent = thinking;
    }
    item.durationMs = durationMs;
    item.tools = tools;
    item.isThinking = false;

    QModelIndex idx = index(lastIdx);
    emit dataChanged(idx, idx, {ContentRole, ThinkingContentRole, IsThinkingRole, DurationMsRole, ToolsRole});
}

void AgentMessageModel::appendSystemMessage(const QString &content)
{
    beginInsertRows(QModelIndex(), m_messages.size(), m_messages.size());
    AgentMessageItem item;
    item.role = "system";
    item.content = content;
    item.timestamp = QDateTime::currentDateTime().toString("HH:mm:ss");
    m_messages.append(item);
    endInsertRows();
    emit countChanged();
}

void AgentMessageModel::clear()
{
    if (m_messages.isEmpty()) return;
    beginResetModel();
    m_messages.clear();
    endResetModel();
    emit countChanged();
}
