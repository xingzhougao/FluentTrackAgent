import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property alias model: listView.model
    property alias count: listView.count

    signal starterPromptClicked(string prompt)

    function scrollToBottom() {
        if (listView.count > 0) {
            listView.positionViewAtEnd();
        }
    }

    // 消息列表
    ListView {
        id: listView
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        delegate: AgentMessageDelegate {
            width: listView.width
        }

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            width: 6
            background: Rectangle { color: "transparent" }
            contentItem: Rectangle {
                radius: 3
                color: parent.hovered ? "#3b82f6" : "#223145"
            }
        }

        onCountChanged: {
            Qt.callLater(root.scrollToBottom);
        }
    }

    // 空状态引导视图
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 600)
        visible: listView.count === 0
        spacing: 20

        // 头部欢迎
        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                radius: 28
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#1d4ed8" }
                    GradientStop { position: 1.0; color: "#3b82f6" }
                }

                Text {
                    anchors.centerIn: parent
                    text: "✨"
                    font.pixelSize: 26
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Fluent Music 智能助手"
                color: "#f8fafc"
                font.pixelSize: 22
                font.weight: Font.Bold
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "支持自然语言播放控制、本地曲库搜索、场景歌单与多源网络发现"
                color: "#7e92aa"
                font.pixelSize: 13
            }
        }

        // 四大能力卡片展示
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 12
            columnSpacing: 12

            Repeater {
                model: [
                    { icon: "🎛️", title: "播放与硬件控制", desc: "“音量调到30%”、“暂停播放”、“切到下一首”" },
                    { icon: "🔍", title: "本地精准搜歌", desc: "“播放周杰伦的晴天”、“来一首本地轻音乐”" },
                    { icon: "☕", title: "场景与情绪歌单", desc: "“给我推荐几首适合写代码的中文歌”" },
                    { icon: "🌐", title: "多源网络发现", desc: "“本地没有就网上找一找，确认后下载入库”" }
                ]

                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 68
                    radius: 10
                    color: "#111822"
                    border.color: cardMouse.containsMouse ? "#3b82f6" : "#1e2b3c"
                    border.width: 1

                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Text {
                            text: modelData.icon
                            font.pixelSize: 22
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: modelData.title
                                color: "#e2e8f0"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }

                            Text {
                                Layout.fillWidth: true
                                text: modelData.desc
                                color: "#64748b"
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }
                    }

                    MouseArea {
                        id: cardMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var sample = modelData.desc.replace(/[“”"]/g, "").split("、")[0];
                            root.starterPromptClicked(sample);
                        }
                    }
                }
            }
        }
    }
}
