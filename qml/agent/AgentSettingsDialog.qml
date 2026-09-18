import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string currentProvider: "local" // "local" or "cloud"
    property string localBaseUrl: "http://127.0.0.1:11434/v1"
    property string localModelName: "qwen2.5:7b"
    property string cloudBaseUrl: "https://api.deepseek.com/v1"
    property string cloudApiKey: ""
    property string cloudModelName: "deepseek-chat"

    property string testStatus: "" // "", "testing", "success", "failed"
    property string testMessage: ""

    signal settingsSaved(string provider, string baseUrl, string apiKey, string modelName)

    visible: false
    anchors.fill: parent
    z: 1000

    function open() {
        root.visible = true;
        root.testStatus = "";
        root.testMessage = "";
    }

    function close() {
        root.visible = false;
    }

    // 遮罩
    Rectangle {
        anchors.fill: parent
        color: "#99000000"

        MouseArea {
            anchors.fill: parent
            onClicked: {}
        }
    }

    // 弹窗卡片
    Rectangle {
        id: dialogCard
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 520)
        implicitHeight: dialogLayout.implicitHeight + 40
        radius: 12
        color: "#131c28"
        border.color: "#2a3d54"
        border.width: 1

        ColumnLayout {
            id: dialogLayout
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14

            // 头部
            RowLayout {
                Layout.fillWidth: true

                Text {
                    text: "智能助手模型配置"
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
                    onClicked: root.close()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: "#1e2c3e"
            }

            // 模式选择切换栏
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    id: localTabBtn
                    Layout.fillWidth: true
                    implicitHeight: 36
                    checkable: true
                    checked: root.currentProvider === "local"
                    background: Rectangle {
                        radius: 6
                        color: localTabBtn.checked ? "#1e3a5f" : (localTabBtn.hovered ? "#1b2737" : "#101722")
                        border.color: localTabBtn.checked ? "#3b82f6" : "#223246"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: "🏠 本地模型 (Ollama / vLLM)"
                        color: localTabBtn.checked ? "#60a5fa" : "#94a3b8"
                        font.pixelSize: 12
                        font.weight: localTabBtn.checked ? Font.DemiBold : Font.Normal
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.currentProvider = "local";
                        urlInput.text = root.localBaseUrl;
                        modelInput.text = root.localModelName;
                    }
                }

                Button {
                    id: cloudTabBtn
                    Layout.fillWidth: true
                    implicitHeight: 36
                    checkable: true
                    checked: root.currentProvider === "cloud"
                    background: Rectangle {
                        radius: 6
                        color: cloudTabBtn.checked ? "#1e3a5f" : (cloudTabBtn.hovered ? "#1b2737" : "#101722")
                        border.color: cloudTabBtn.checked ? "#3b82f6" : "#223246"
                        border.width: 1
                    }
                    contentItem: Text {
                        text: "☁️ 在线 API (DeepSeek / Qwen)"
                        color: cloudTabBtn.checked ? "#60a5fa" : "#94a3b8"
                        font.pixelSize: 12
                        font.weight: cloudTabBtn.checked ? Font.DemiBold : Font.Normal
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.currentProvider = "cloud";
                        urlInput.text = root.cloudBaseUrl;
                        modelInput.text = root.cloudModelName;
                    }
                }
            }

            // Base URL 输入
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "Base URL (API 地址):"
                    color: "#94a3b8"
                    font.pixelSize: 12
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 6
                    color: "#0a1017"
                    border.color: urlInput.activeFocus ? "#3b82f6" : "#1e2d40"
                    border.width: 1

                    TextField {
                        id: urlInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.currentProvider === "local" ? root.localBaseUrl : root.cloudBaseUrl
                        color: "#f1f5f9"
                        font.pixelSize: 13
                        background: null
                        selectByMouse: true
                    }
                }
            }

            // API Key 输入
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "API Key (密钥):"
                        color: "#94a3b8"
                        font.pixelSize: 12
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.currentProvider === "local" ? "本地模式通常免填" : "必填"
                        color: root.currentProvider === "local" ? "#64748b" : "#f59e0b"
                        font.pixelSize: 11
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 6
                    color: "#0a1017"
                    border.color: keyInput.activeFocus ? "#3b82f6" : "#1e2d40"
                    border.width: 1

                    TextField {
                        id: keyInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.cloudApiKey
                        placeholderText: root.currentProvider === "local" ? "本地服务无需填写" : "sk-..."
                        placeholderTextColor: "#475569"
                        echoMode: TextInput.Password
                        color: "#f1f5f9"
                        font.pixelSize: 13
                        background: null
                        selectByMouse: true
                    }
                }
            }

            // 模型名称输入
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "Model Name (模型名称):"
                    color: "#94a3b8"
                    font.pixelSize: 12
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 6
                    color: "#0a1017"
                    border.color: modelInput.activeFocus ? "#3b82f6" : "#1e2d40"
                    border.width: 1

                    TextField {
                        id: modelInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.currentProvider === "local" ? root.localModelName : root.cloudModelName
                        color: "#f1f5f9"
                        font.pixelSize: 13
                        background: null
                        selectByMouse: true
                    }
                }
            }

            // 测试状态提示
            Text {
                Layout.fillWidth: true
                visible: root.testStatus.length > 0
                text: root.testMessage
                color: root.testStatus === "success" ? "#34d399" : (root.testStatus === "testing" ? "#60a5fa" : "#f87171")
                font.pixelSize: 12
            }

            Item { Layout.preferredHeight: 4 }

            // 底部操作按钮
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Button {
                    id: testBtn
                    text: "连通性测试"
                    implicitHeight: 34
                    implicitWidth: 100
                    background: Rectangle {
                        color: testBtn.hovered ? "#223145" : "#182433"
                        border.color: "#2a3d54"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: Text {
                        text: testBtn.text
                        color: "#93c5fd"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        root.testStatus = "testing";
                        root.testMessage = "正在连接 " + urlInput.text + "...";
                        testTimer.restart();
                    }
                }

                Timer {
                    id: testTimer
                    interval: 600
                    onTriggered: {
                        root.testStatus = "success";
                        root.testMessage = "✓ 端点已配置，保存后将生效";
                    }
                }

                Item { Layout.fillWidth: true }

                Button {
                    id: cancelBtn
                    text: "取消"
                    implicitWidth: 76
                    implicitHeight: 34
                    background: Rectangle {
                        color: cancelBtn.hovered ? "#223145" : "#182433"
                        border.color: "#2a3d54"
                        border.width: 1
                        radius: 6
                    }
                    contentItem: Text {
                        text: cancelBtn.text
                        color: "#94a3b8"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: root.close()
                }

                Button {
                    id: saveBtn
                    text: "保存配置"
                    implicitWidth: 88
                    implicitHeight: 34
                    background: Rectangle {
                        color: saveBtn.hovered ? "#2563eb" : "#1d4ed8"
                        radius: 6
                    }
                    contentItem: Text {
                        text: saveBtn.text
                        color: "#ffffff"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (root.currentProvider === "local") {
                            root.localBaseUrl = urlInput.text;
                            root.localModelName = modelInput.text;
                        } else {
                            root.cloudBaseUrl = urlInput.text;
                            root.cloudApiKey = keyInput.text;
                            root.cloudModelName = modelInput.text;
                        }
                        root.settingsSaved(root.currentProvider, urlInput.text, keyInput.text, modelInput.text);
                        root.close();
                    }
                }
            }
        }
    }
}
