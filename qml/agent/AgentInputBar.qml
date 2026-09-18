import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property bool isBusy: false

    signal sendRequested(string text)
    signal suggestionClicked(string text)

    implicitHeight: mainLayout.implicitHeight + 20
    radius: 12
    color: "#111822"
    border.color: "#1f2c3c"
    border.width: 1

    ColumnLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // 快捷指令推荐标签流
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff

            Row {
                spacing: 8

                Repeater {
                    model: [
                        "🎵 播放晴天",
                        "🔉 音量调到 30%",
                        "☕ 适合写代码的歌",
                        "⏸️ 暂停播放",
                        "⏭️ 切到下一首",
                        "❓ 现在放的是什么歌"
                    ]

                    delegate: Button {
                        id: chipBtn
                        implicitHeight: 28
                        padding: 6
                        background: Rectangle {
                            radius: 14
                            color: chipBtn.hovered ? "#1e2e42" : "#141f2d"
                            border.color: chipBtn.hovered ? "#3b82f6" : "#223144"
                            border.width: 1
                        }
                        contentItem: Text {
                            text: modelData
                            color: chipBtn.hovered ? "#93c5fd" : "#8ea0b5"
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            root.suggestionClicked(modelData.replace(/^[\p{Emoji}\s]+/u, "").trim());
                        }
                    }
                }
            }
        }

        // 输入框与发送按钮栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(38, Math.min(inputArea.contentHeight + 14, 100))
                radius: 8
                color: "#0c131d"
                border.color: inputArea.activeFocus ? "#3b82f6" : "#1c2a3b"
                border.width: 1

                ScrollView {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    anchors.topMargin: 4
                    anchors.bottomMargin: 4
                    clip: true

                    TextArea {
                        id: inputArea
                        placeholderText: "输入指令或问题，例如：'播放周杰伦的晴天'、'把声音调到 25%'..."
                        placeholderTextColor: "#4d6074"
                        color: "#f1f5f9"
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        background: null
                        selectByMouse: true
                        enabled: !root.isBusy

                        Keys.onReturnPressed: function(event) {
                            if (event.modifiers & Qt.ShiftModifier) {
                                inputArea.insert(inputArea.cursorPosition, "\n");
                            } else {
                                event.accepted = true;
                                triggerSend();
                            }
                        }
                    }
                }
            }

            // 发送按钮
            Button {
                id: sendBtn
                Layout.preferredWidth: 42
                Layout.preferredHeight: 38
                enabled: !root.isBusy && inputArea.text.trim().length > 0
                background: Rectangle {
                    radius: 8
                    color: !sendBtn.enabled ? "#192433" : (sendBtn.hovered ? "#2563eb" : "#1d4ed8")
                }
                contentItem: Text {
                    text: root.isBusy ? "⏳" : "➤"
                    color: sendBtn.enabled ? "#ffffff" : "#4a5d73"
                    font.pixelSize: 15
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: triggerSend()
            }
        }
    }

    function triggerSend() {
        var txt = inputArea.text.trim();
        if (txt.length > 0 && !root.isBusy) {
            root.sendRequested(txt);
            inputArea.text = "";
        }
    }

    function setPrompt(text) {
        inputArea.text = text;
        inputArea.forceActiveFocus();
    }
}
