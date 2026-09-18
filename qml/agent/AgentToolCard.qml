import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property string toolName: "播放控制"
    property string toolAction: "player_control"
    property string toolParams: ""
    property string status: "success" // "running", "success", "failed"
    property string resultText: ""

    implicitWidth: parent ? parent.width : 420
    implicitHeight: mainLayout.implicitHeight + 20
    radius: 10
    color: "#111a26"
    border.color: root.status === "failed" ? "#ef4444" : (root.status === "running" ? "#3b82f6" : "#223348")
    border.width: 1

    Behavior on border.color { ColorAnimation { duration: 150 } }

    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // 头部：工具图标、标题与状态标签
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // 状态小圆标或图标
            Rectangle {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                radius: 11
                color: root.status === "failed" ? "#451a1a" : (root.status === "running" ? "#1e3a5f" : "#133826")
                border.color: root.status === "failed" ? "#f87171" : (root.status === "running" ? "#60a5fa" : "#34d399")
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: root.status === "failed" ? "✕" : (root.status === "running" ? "⚙" : "✓")
                    color: root.status === "failed" ? "#f87171" : (root.status === "running" ? "#93c5fd" : "#34d399")
                    font.pixelSize: 11
                    font.weight: Font.Bold

                    RotationAnimation on rotation {
                        running: root.status === "running"
                        loops: Animation.Infinite
                        from: 0
                        to: 360
                        duration: 1200
                    }
                }
            }

            Text {
                text: root.toolName
                color: "#e2e8f0"
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }

            Rectangle {
                Layout.preferredHeight: 18
                implicitWidth: actionText.implicitWidth + 10
                radius: 4
                color: "#1e293b"

                Text {
                    id: actionText
                    anchors.centerIn: parent
                    text: root.toolAction
                    color: "#94a3b8"
                    font.pixelSize: 10
                    font.family: "Consolas, monospace"
                }
            }

            Item { Layout.fillWidth: true }

            // 状态徽章
            Rectangle {
                Layout.preferredHeight: 20
                implicitWidth: statusLabel.implicitWidth + 12
                radius: 10
                color: root.status === "failed" ? "#381c1c" : (root.status === "running" ? "#182a44" : "#143323")

                Text {
                    id: statusLabel
                    anchors.centerIn: parent
                    text: root.status === "failed" ? "执行失败" : (root.status === "running" ? "执行中..." : "执行成功")
                    color: root.status === "failed" ? "#fca5a5" : (root.status === "running" ? "#93c5fd" : "#86efac")
                    font.pixelSize: 10
                    font.weight: Font.Medium
                }
            }
        }

        // 参数信息
        Rectangle {
            Layout.fillWidth: true
            visible: root.toolParams.length > 0
            implicitHeight: paramsText.implicitHeight + 8
            radius: 6
            color: "#0a1017"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8

                Text {
                    text: "参数:"
                    color: "#64748b"
                    font.pixelSize: 11
                }

                Text {
                    id: paramsText
                    Layout.fillWidth: true
                    text: root.toolParams
                    color: "#cbd5e1"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }
        }

        // 结果信息
        Text {
            Layout.fillWidth: true
            visible: root.resultText.length > 0
            text: root.resultText
            color: root.status === "failed" ? "#fca5a5" : "#a7f3d0"
            font.pixelSize: 12
            wrapMode: Text.Wrap
        }
    }
}
