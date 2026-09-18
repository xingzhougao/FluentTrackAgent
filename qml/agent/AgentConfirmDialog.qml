import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string title: "操作确认"
    property string message: "即将执行敏感操作，是否继续？"
    property string details: ""
    property string confirmText: "确认执行"
    property string cancelText: "取消"

    signal confirmed()
    signal rejected()

    visible: false
    anchors.fill: parent
    z: 1000

    function open(titleText, msgText, detailText) {
        if (titleText) root.title = titleText;
        if (msgText) root.message = msgText;
        root.details = detailText || "";
        root.visible = true;
    }

    function close() {
        root.visible = false;
    }

    // 遮罩背景
    Rectangle {
        anchors.fill: parent
        color: "#99000000"

        MouseArea {
            anchors.fill: parent
            // 阻止点击穿透
            onClicked: {}
        }
    }

    // 模态对话框本体
    Rectangle {
        id: dialogCard
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 460)
        implicitHeight: dialogLayout.implicitHeight + 36
        radius: 12
        color: "#131c28"
        border.color: "#2a3d54"
        border.width: 1

        ColumnLayout {
            id: dialogLayout
            anchors.fill: parent
            anchors.margins: 20
            spacing: 14

            // 头部标题与警告图标
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    radius: 14
                    color: "#382914"
                    border.color: "#f59e0b"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "!"
                        color: "#fbbf24"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                    }
                }

                Text {
                    text: root.title
                    color: "#f8fafc"
                    font.pixelSize: 16
                    font.weight: Font.Bold
                }

                Item { Layout.fillWidth: true }

                Button {
                    flat: true
                    implicitWidth: 28
                    implicitHeight: 28
                    background: Rectangle {
                        color: parent.hovered ? "#223145" : "transparent"
                        radius: 14
                    }
                    contentItem: Text {
                        text: "✕"
                        color: "#94a3b8"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.close();
                        root.rejected();
                    }
                }
            }

            // 分割线
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: "#1f2e40"
            }

            // 正文提示
            Text {
                Layout.fillWidth: true
                text: root.message
                color: "#cbd5e1"
                font.pixelSize: 14
                lineHeight: 1.4
                wrapMode: Text.Wrap
            }

            // 详情区域 (可选)
            Rectangle {
                Layout.fillWidth: true
                visible: root.details.length > 0
                implicitHeight: detailsText.implicitHeight + 16
                radius: 6
                color: "#0c131c"
                border.color: "#1d2a3a"
                border.width: 1

                Text {
                    id: detailsText
                    anchors.fill: parent
                    anchors.margins: 10
                    text: root.details
                    color: "#94a3b8"
                    font.pixelSize: 11
                    font.family: "Consolas, monospace"
                    wrapMode: Text.Wrap
                }
            }

            Item { Layout.preferredHeight: 4 }

            // 按钮操作区
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                Button {
                    id: cancelBtn
                    text: root.cancelText
                    implicitWidth: 88
                    implicitHeight: 34
                    background: Rectangle {
                        color: cancelBtn.hovered ? "#243548" : "#1a2636"
                        border.color: "#2e4157"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: Text {
                        text: cancelBtn.text
                        color: "#94a3b8"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.close();
                        root.rejected();
                    }
                }

                Button {
                    id: okBtn
                    text: root.confirmText
                    implicitWidth: 98
                    implicitHeight: 34
                    background: Rectangle {
                        color: okBtn.hovered ? "#2563eb" : "#1d4ed8"
                        radius: 6
                    }
                    contentItem: Text {
                        text: okBtn.text
                        color: "#ffffff"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.close();
                        root.confirmed();
                    }
                }
            }
        }
    }
}
