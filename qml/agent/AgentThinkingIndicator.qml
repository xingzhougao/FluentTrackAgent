import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string thinkingText: ""
    property bool isThinking: false
    property bool expanded: false
    property int durationMs: 0

    implicitWidth: parent ? parent.width : 400
    implicitHeight: mainColumn.implicitHeight

    ColumnLayout {
        id: mainColumn
        anchors.fill: parent
        spacing: 6

        // 思考状态栏卡片
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            radius: 8
            color: root.expanded ? "#162232" : "#121b27"
            border.color: root.isThinking ? "#3b82f6" : "#223246"
            border.width: 1

            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                // 思考动画图标
                Item {
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 16

                    Rectangle {
                        anchors.centerIn: parent
                        width: 8
                        height: 8
                        radius: 4
                        color: root.isThinking ? "#60a5fa" : "#94a3b8"

                        SequentialAnimation on scale {
                            running: root.isThinking
                            loops: Animation.Infinite
                            NumberAnimation { from: 0.8; to: 1.3; duration: 600; easing.type: Easing.InOutQuad }
                            NumberAnimation { from: 1.3; to: 0.8; duration: 600; easing.type: Easing.InOutQuad }
                        }
                    }
                }

                Text {
                    text: root.isThinking ? "深度思考中..." : (root.durationMs > 0 ? "已完成思考 (耗时 " + (root.durationMs / 1000).toFixed(1) + "s)" : "思考过程")
                    color: root.isThinking ? "#93c5fd" : "#8c9cb0"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }

                Item { Layout.fillWidth: true }

                // 展开/收起按钮
                Button {
                    id: toggleBtn
                    flat: true
                    implicitHeight: 26
                    padding: 4
                    background: Rectangle {
                        color: toggleBtn.hovered ? "#24354a" : "transparent"
                        radius: 4
                    }
                    contentItem: Text {
                        text: root.expanded ? "收起 ▲" : "展开详情 ▼"
                        color: "#6ea8ff"
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.expanded = !root.expanded
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.expanded = !root.expanded
                }
            }
        }

        // 展开的思考文本内容
        Rectangle {
            id: contentBox
            Layout.fillWidth: true
            Layout.preferredHeight: root.expanded ? Math.min(thoughtContentText.implicitHeight + 20, 260) : 0
            visible: Layout.preferredHeight > 0
            clip: true
            radius: 8
            color: "#0f1722"
            border.color: "#1c2a3b"
            border.width: 1

            Behavior on Layout.preferredHeight {
                NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
            }

            ScrollView {
                anchors.fill: parent
                anchors.margins: 10
                clip: true

                TextArea {
                    id: thoughtContentText
                    text: root.thinkingText
                    readOnly: true
                    wrapMode: Text.Wrap
                    color: "#94a3b8"
                    font.pixelSize: 12
                    font.family: "Consolas, 'Cascadia Code', monospace"
                    background: null
                    selectByMouse: true
                    padding: 0
                }
            }
        }
    }
}
