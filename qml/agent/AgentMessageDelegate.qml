import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    // model properties expected:
    // role: "user" | "assistant" | "system"
    // content: string
    // thinkingContent: string
    // isThinking: bool
    // durationMs: int
    // tools: list of { name, action, params, status, result }
    // timestamp: string

    property var messageData: model

    implicitWidth: parent ? parent.width : 600
    implicitHeight: mainLayout.implicitHeight + 16

    ColumnLayout {
        id: mainLayout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 6

        // 1. 系统消息类型（居中胶囊卡片）
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: sysText.implicitHeight + 8
            visible: root.messageData.role === "system"

            Rectangle {
                anchors.centerIn: parent
                width: sysText.implicitWidth + 24
                height: parent.height
                radius: 12
                color: "#111a26"
                border.color: "#1c2a3b"
                border.width: 1

                Text {
                    id: sysText
                    anchors.centerIn: parent
                    text: root.messageData.content || ""
                    color: "#7e8fa4"
                    font.pixelSize: 11
                }
            }
        }

        // 2. 用户消息类型（靠右对齐）
        RowLayout {
            Layout.fillWidth: true
            visible: root.messageData.role === "user"
            spacing: 10

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.maximumWidth: Math.min(root.width * 0.72, 560)
                implicitWidth: userText.implicitWidth + 24
                implicitHeight: userText.implicitHeight + 20
                radius: 14
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#1e3d64" }
                    GradientStop { position: 1.0; color: "#284f80" }
                }
                border.color: "#355e94"
                border.width: 1

                Text {
                    id: userText
                    anchors.fill: parent
                    anchors.margins: 10
                    text: root.messageData.content || ""
                    color: "#ffffff"
                    font.pixelSize: 13
                    lineHeight: 1.35
                    wrapMode: Text.Wrap
                }
            }

            // 用户头像
            Rectangle {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignTop
                radius: 16
                color: "#1b2838"
                border.color: "#2a3d54"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "我"
                    color: "#94a3b8"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
            }
        }

        // 3. 智能助手消息类型（靠左对齐）
        RowLayout {
            Layout.fillWidth: true
            visible: root.messageData.role === "assistant"
            spacing: 10
            Layout.alignment: Qt.AlignTop

            // 助手头像
            Rectangle {
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignTop
                radius: 16
                color: "#152538"
                border.color: "#2b466b"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "🤖"
                    font.pixelSize: 14
                }
            }

            // 消息主体容器
            ColumnLayout {
                Layout.fillWidth: true
                Layout.maximumWidth: Math.min(root.width * 0.85, 680)
                spacing: 8

                // 思考过程 (DeepSeek-R1 <think>)
                AgentThinkingIndicator {
                    Layout.fillWidth: true
                    visible: (root.messageData.thinkingContent && root.messageData.thinkingContent.length > 0) || root.messageData.isThinking
                    thinkingText: root.messageData.thinkingContent || ""
                    isThinking: root.messageData.isThinking || false
                    durationMs: root.messageData.durationMs || 0
                }

                // 工具执行卡片列表
                Repeater {
                    model: root.messageData.tools || []

                    delegate: AgentToolCard {
                        Layout.fillWidth: true
                        toolName: modelData.name || "操作"
                        toolAction: modelData.action || ""
                        toolParams: modelData.params || ""
                        status: modelData.status || "success"
                        resultText: modelData.result || ""
                    }
                }

                // 最终回答正文气泡
                Rectangle {
                    Layout.fillWidth: true
                    visible: (root.messageData.content && root.messageData.content.length > 0) || (!root.messageData.thinkingContent && !root.messageData.isThinking && (!root.messageData.tools || root.messageData.tools.length === 0))
                    implicitHeight: assistantText.implicitHeight + 22
                    radius: 12
                    color: "#121b27"
                    border.color: "#1f2d3f"
                    border.width: 1

                    TextArea {
                        id: assistantText
                        anchors.fill: parent
                        anchors.margins: 11
                        text: root.messageData.content || (root.messageData.isThinking ? "正在思考与处理中..." : "")
                        color: "#e2e8f0"
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        readOnly: true
                        background: null
                        selectByMouse: true
                        padding: 0
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }
    }
}
