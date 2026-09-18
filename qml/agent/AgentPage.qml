import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var playerController: typeof player !== "undefined" ? player : null
    property color textPrimaryColor: "#f5f7fb"
    property color textSecondaryColor: "#8c99aa"
    property color accentColor: "#6ea8ff"
    property color borderColor: "#1f2b3a"

    // 助手状态属性 (优先联动 C++ agentController，未连接时自适应)
    property bool isConnected: typeof agentController !== "undefined" ? agentController.isConnected : false
    property string agentStatus: typeof agentController !== "undefined" ? agentController.agentStatus : "offline"
    property string statusText: typeof agentController !== "undefined" ? agentController.statusText : "服务未连接"

    // 1. 背景层 暗色 WinUI 风格渐变
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0f1724" }
            GradientStop { position: 0.4; color: "#0c131d" }
            GradientStop { position: 1.0; color: "#090e15" }
        }

        // 右上角环境光晕装饰
        Rectangle {
            width: 500
            height: 500
            radius: 250
            x: parent.width - 300
            y: -220
            color: "#1d3a63"
            opacity: 0.22
        }
    }

    // 2. 主体垂直布局
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 20
        anchors.bottomMargin: 16
        spacing: 12

        // 顶部导航与控制栏
        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            ColumnLayout {
                spacing: 2

                RowLayout {
                    spacing: 10

                    Text {
                        text: "智能助手"
                        color: root.textPrimaryColor
                        font.pixelSize: 24
                        font.weight: Font.Bold
                    }

                    // 状态指示器胶囊
                    Rectangle {
                        Layout.preferredHeight: 22
                        implicitWidth: statusRow.implicitWidth + 16
                        radius: 11
                        color: root.agentStatus === "ready" ? "#102a1e" : (root.agentStatus === "thinking" ? "#1c2b44" : "#2d1616")
                        border.color: root.agentStatus === "ready" ? "#22c55e" : (root.agentStatus === "thinking" ? "#3b82f6" : "#ef4444")
                        border.width: 1

                        RowLayout {
                            id: statusRow
                            anchors.centerIn: parent
                            spacing: 6

                            Rectangle {
                                Layout.preferredWidth: 6
                                Layout.preferredHeight: 6
                                radius: 3
                                color: root.agentStatus === "ready" ? "#22c55e" : (root.agentStatus === "thinking" ? "#60a5fa" : "#ef4444")

                                SequentialAnimation on opacity {
                                    running: root.agentStatus === "thinking"
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 0.3; to: 1.0; duration: 500 }
                                    NumberAnimation { from: 1.0; to: 0.3; duration: 500 }
                                }
                            }

                            Text {
                                text: root.statusText
                                color: root.agentStatus === "ready" ? "#86efac" : (root.agentStatus === "thinking" ? "#93c5fd" : "#fca5a5")
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }
                        }
                    }
                }

                Text {
                    text: "基于自然语言与确定性工作流的音乐智能协同引擎"
                    color: root.textSecondaryColor
                    font.pixelSize: 12
                }
            }

            Item { Layout.fillWidth: true }

            // 新建会话按钮
            Button {
                id: newChatBtn
                implicitHeight: 34
                implicitWidth: 92
                background: Rectangle {
                    radius: 8
                    color: newChatBtn.hovered ? "#1c293a" : "#131e2b"
                    border.color: "#25374d"
                    border.width: 1
                }
                contentItem: RowLayout {
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "+"; color: "#93c5fd"; font.pixelSize: 15; font.weight: Font.Bold }
                    Text { text: "新建会话"; color: "#cbd5e1"; font.pixelSize: 12 }
                }
                onClicked: {
                    if (typeof agentController !== "undefined" && agentController) {
                        agentController.newSession();
                    } else {
                        chatModel.clear();
                        root.agentStatus = "ready";
                        root.statusText = "已就绪";
                    }
                }
            }

            // 模型设置按钮
            Button {
                id: settingsBtn
                implicitHeight: 34
                implicitWidth: 92
                background: Rectangle {
                    radius: 8
                    color: settingsBtn.hovered ? "#1c293a" : "#131e2b"
                    border.color: "#25374d"
                    border.width: 1
                }
                contentItem: RowLayout {
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "⚙"; color: "#93c5fd"; font.pixelSize: 13 }
                    Text { text: "模型配置"; color: "#cbd5e1"; font.pixelSize: 12 }
                }
                onClicked: {
                    settingsDialog.open();
                }
            }
        }

        // 分割线
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: "#172332"
        }

        // 3. 对话流展示区
        AgentChatView {
            id: chatView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: (typeof agentMessageModel !== "undefined" && agentMessageModel) ? agentMessageModel : chatModel

            onStarterPromptClicked: function(prompt) {
                inputBar.setPrompt(prompt);
            }
        }

        // 4. 底部输入栏
        AgentInputBar {
            id: inputBar
            Layout.fillWidth: true
            isBusy: root.agentStatus === "thinking"

            onSendRequested: function(text) {
                handleUserMessage(text);
            }

            onSuggestionClicked: function(text) {
                handleUserMessage(text);
            }
        }
    }

    // 消息模型 (Step 1 前端阶段提供高保真实机验证，后续 Step 2 切换为 C++ AgentMessageModel)
    ListModel {
        id: chatModel
    }

    // 业务与交互处理器 (优先通过 C++ agentController 发送至 Python Agent)
    function handleUserMessage(userText) {
        if (typeof agentController !== "undefined" && agentController) {
            agentController.sendMessage(userText);
            return;
        }

        // 1. 本地 Mock 模式兜底
        chatModel.append({
            role: "user",
            content: userText,
            thinkingContent: "",
            isThinking: false,
            durationMs: 0,
            tools: []
        });

        root.agentStatus = "thinking";
        root.statusText = "思考决策中...";

        // 2. 模拟智能助手思考与执行流程
        mockResponseTimer.userQuery = userText;
        mockResponseTimer.restart();
    }

    Timer {
        id: mockResponseTimer
        interval: 800
        property string userQuery: ""
        onTriggered: {
            var q = userQuery.toLowerCase();
            var reply = "";
            var thought = "";
            var toolsList = [];

            if (q.indexOf("音量") !== -1 || q.indexOf("声音") !== -1) {
                thought = "1. 用户意图识别为 PLAYER_CONTROL (音量调节)\n2. 提取参数：目标音量数值\n3. 执行确定性工作流 PlayerCommandWorkflow -> set_volume\n4. 校验音量护栏 (0~100) -> 合法\n5. 回传控制状态并通知客户端";
                toolsList = [{
                    name: "调整播放器音量",
                    action: "set_volume",
                    params: "volume: 30",
                    status: "success",
                    result: "音量已成功由当前值调整为 30%"
                }];
                reply = "已为您将播放器音量调整至 30%。需要继续调大或微调吗？";
            } else if (q.indexOf("晴天") !== -1 || q.indexOf("播放") !== -1 || q.indexOf("放一首") !== -1) {
                thought = "1. 识别意图为 LOCAL_SEARCH & PLAY (搜索并点歌)\n2. 提取曲目关键词：'晴天' / '周杰伦'\n3. 启动 SearchAndPlayWorkflow\n4. 优先检索本地曲库 MusicLibraryModel\n5. 命中本地音乐，载入播放队列并触发开播";
                toolsList = [{
                    name: "检索本地曲库",
                    action: "search_local_music",
                    params: "keyword: '晴天'",
                    status: "success",
                    result: "在本地曲库中检索到 1 首匹配歌曲《晴天 - 周杰伦》"
                }, {
                    name: "播放指定曲目",
                    action: "play_track",
                    params: "title: '晴天', artist: '周杰伦'",
                    status: "success",
                    result: "已载入当前播放核心并开始播放"
                }];
                reply = "为您找到了本地歌曲《晴天 - 周杰伦》，已开始播放！";
            } else if (q.indexOf("代码") !== -1 || q.indexOf("歌单") !== -1 || q.indexOf("推荐") !== -1) {
                thought = "1. 识别意图为 SMART_PLAYLIST (智能场景歌单)\n2. 提取场景标签：Scene=Coding, Mood=Focused/Relax, Language=Chinese\n3. 启动 SmartPlaylistWorkflow，查询本地曲库与 AgentTagCache\n4. 根据历史播放与偏好加权排序，筛选出 5 首高匹配度曲目\n5. 创建临时播放列表并启动连续播放";
                toolsList = [{
                    name: "生成智能场景歌单",
                    action: "create_temp_playlist",
                    params: "scene: 'Coding', mood: 'Relaxing', count: 5",
                    status: "success",
                    result: "成功生成《专注编码时光》5 首候选歌单"
                }];
                reply = "已为您精心定制《专注编码时光》场景歌单（共 5 首），轻柔节奏助您沉浸思考，已自动加入播放列表！";
            } else if (q.indexOf("暂停") !== -1) {
                thought = "1. 意图：PLAYER_CONTROL -> pause\n2. 调用 Qt PlayerController.pause()";
                toolsList = [{
                    name: "暂停播放",
                    action: "pause",
                    params: "",
                    status: "success",
                    result: "播放已暂停"
                }];
                reply = "已为您暂停播放。";
            } else if (q.indexOf("下一首") !== -1 || q.indexOf("切歌") !== -1) {
                thought = "1. 意图：PLAYER_CONTROL -> next_track\n2. 调用 Qt PlayerController.next()";
                toolsList = [{
                    name: "切换曲目",
                    action: "next_track",
                    params: "",
                    status: "success",
                    result: "已切至下一首曲目"
                }];
                reply = "已为您切换到下一首歌曲。";
            } else {
                thought = "1. 用户日常对话或咨询\n2. 组织友好回答并提示其可体验的音乐助手指令";
                reply = "您好！我是 Fluent Music 智能助手。您可以直接对我说：“把音量调到 25%”、“播放晴天”、“给我推荐几首适合深夜听的歌”，我将为您自动规划并执行操控！";
            }

            chatModel.append({
                role: "assistant",
                content: reply,
                thinkingContent: thought,
                isThinking: false,
                durationMs: 950,
                tools: toolsList
            });

            root.agentStatus = "ready";
            root.statusText = "已就绪";
        }
    }

    // 5. 模态弹窗层
    AgentConfirmDialog {
        id: confirmDialog
        onConfirmed: {
            console.log("用户已确认敏感操作");
        }
        onRejected: {
            console.log("用户取消了敏感操作");
        }
    }

    AgentSettingsDialog {
        id: settingsDialog
        onSettingsSaved: function(provider, baseUrl, apiKey, modelName, enableThinking) {
            if (typeof agentController !== "undefined" && agentController) {
                agentController.updateLlmConfig(provider, baseUrl, apiKey, modelName, enableThinking);
            }
            console.log("模型配置已更新:", provider, baseUrl, modelName, "深度思考:", enableThinking);
        }
    }
}
