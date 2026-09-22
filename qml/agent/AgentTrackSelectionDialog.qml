import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: selectionDialogItem

    property string confirmId: ""
    property string dialogTitle: "选择要下载的音乐版本"
    property string queryText: ""
    property string artistText: ""
    property int selectedIndex: 0

    signal trackSelected(string cid, string selectedCandidateId)
    signal rejected(string cid)

    visible: false
    anchors.fill: parent
    z: 1001

    ListModel {
        id: candidateModel
    }

    function open(cid, titleText, q, art, candidates) {
        selectionDialogItem.confirmId = cid || "";
        selectionDialogItem.dialogTitle = titleText || "选择要下载的音乐版本";
        selectionDialogItem.queryText = q || "";
        selectionDialogItem.artistText = art || "";
        selectionDialogItem.selectedIndex = 0;

        candidateModel.clear();
        if (candidates && candidates.length) {
            for (var i = 0; i < candidates.length; ++i) {
                var c = candidates[i];
                candidateModel.append({
                    cid: c.id || "",
                    title: c.title || "",
                    artist: c.artist || "",
                    album: c.album || "",
                    provider: c.provider || "",
                    source_label: c.source_label || "网络音频",
                    format: c.format || "MP3",
                    bitrate: c.bitrate || "320k",
                    size_str: c.size_str || "",
                    is_netdisk: !!c.is_netdisk,
                    version_tag: c.version_tag || "原版音频",
                    url: c.url || ""
                });
            }
        }
        selectionDialogItem.visible = true;
    }

    function close() {
        selectionDialogItem.visible = false;
    }

    function confirmCurrentSelection() {
        if (selectedIndex >= 0 && selectedIndex < candidateModel.count) {
            var item = candidateModel.get(selectedIndex);
            var cid = selectionDialogItem.confirmId;
            selectionDialogItem.close();
            if (typeof agentController !== "undefined" && agentController && cid !== "") {
                agentController.respondCandidateSelection(cid, item.cid, false);
            }
            selectionDialogItem.trackSelected(cid, item.cid);
            selectionDialogItem.confirmId = "";
        }
    }

    function cancelSelection() {
        var cid = selectionDialogItem.confirmId;
        selectionDialogItem.close();
        if (typeof agentController !== "undefined" && agentController && cid !== "") {
            agentController.respondCandidateSelection(cid, "", true);
        }
        selectionDialogItem.rejected(cid);
        selectionDialogItem.confirmId = "";
    }

    // 半透明背景遮罩
    Rectangle {
        anchors.fill: parent
        color: "#aa000000"

        MouseArea {
            anchors.fill: parent
            onClicked: {}
        }
    }

    // 模态对话框容器
    Rectangle {
        id: dialogCard
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 560)
        height: Math.min(parent.height - 48, contentCol.implicitHeight + 36)
        radius: 12
        color: "#131c28"
        border.color: "#2a3d54"
        border.width: 1

        ColumnLayout {
            id: contentCol
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 18
            spacing: 12

            // 1. 对话框头部
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: 32
                    Layout.preferredHeight: 32
                    radius: 16
                    color: "#1e3a8a"
                    border.color: "#3b82f6"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "🎵"
                        font.pixelSize: 15
                    }
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: selectionDialogItem.dialogTitle
                        color: "#f8fafc"
                        font.pixelSize: 15
                        font.weight: Font.Bold
                    }

                    Text {
                        text: "为你检索到关于「" + (selectionDialogItem.queryText || "目标曲目") + "」的 " + candidateModel.count + " 个版本，请选择："
                        color: "#94a3b8"
                        font.pixelSize: 12
                    }
                }

                Button {
                    id: closeBtn
                    flat: true
                    implicitWidth: 28
                    implicitHeight: 28
                    background: Rectangle {
                        color: closeBtn.hovered ? "#223145" : "transparent"
                        radius: 14
                    }
                    contentItem: Text {
                        text: "✕"
                        color: "#94a3b8"
                        font.pixelSize: 13
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: selectionDialogItem.cancelSelection()
                }
            }

            // 分割线
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: "#1f2e40"
            }

            // 2. 候选列表区域 (最多展示 5 项，支持滚动)
            ListView {
                id: candidateListView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(candidateModel.count * 64, 320)
                clip: true
                model: candidateModel
                spacing: 6

                delegate: Rectangle {
                    id: itemCard
                    width: candidateListView.width
                    height: 58
                    radius: 8

                    property bool isSelected: selectionDialogItem.selectedIndex === index
                    property bool isHovered: mouseArea.containsMouse

                    color: isSelected ? "#1c2b3d" : (isHovered ? "#162332" : "#0f1722")
                    border.color: isSelected ? "#3b82f6" : (isHovered ? "#293e56" : "#1e2c3d")
                    border.width: isSelected ? 1.5 : 1

                    // 获取版本标签的配色方案
                    function getTagBgColor(tag) {
                        if (tag.indexOf("无损") !== -1) return "#3b2506";
                        if (tag.indexOf("原版") !== -1) return "#063d2e";
                        if (tag.indexOf("网盘") !== -1) return "#172b54";
                        if (tag.indexOf("翻唱") !== -1) return "#351952";
                        if (tag.indexOf("DJ") !== -1 || tag.indexOf("混音") !== -1) return "#421d0a";
                        return "#1e293b";
                    }

                    function getTagBorderColor(tag) {
                        if (tag.indexOf("无损") !== -1) return "#f59e0b";
                        if (tag.indexOf("原版") !== -1) return "#10b981";
                        if (tag.indexOf("网盘") !== -1) return "#3b82f6";
                        if (tag.indexOf("翻唱") !== -1) return "#a855f7";
                        if (tag.indexOf("DJ") !== -1 || tag.indexOf("混音") !== -1) return "#f97316";
                        return "#475569";
                    }

                    function getTagTextColor(tag) {
                        if (tag.indexOf("无损") !== -1) return "#fbbf24";
                        if (tag.indexOf("原版") !== -1) return "#34d399";
                        if (tag.indexOf("网盘") !== -1) return "#60a5fa";
                        if (tag.indexOf("翻唱") !== -1) return "#c084fc";
                        if (tag.indexOf("DJ") !== -1 || tag.indexOf("混音") !== -1) return "#fb923c";
                        return "#cbd5e1";
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 10

                        // 单选指示圆点
                        Rectangle {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            radius: 8
                            color: "transparent"
                            border.color: itemCard.isSelected ? "#3b82f6" : "#475569"
                            border.width: 1.5

                            Rectangle {
                                anchors.centerIn: parent
                                width: 8
                                height: 8
                                radius: 4
                                color: "#3b82f6"
                                visible: itemCard.isSelected
                            }
                        }

                        // 版本标签徽章
                        Rectangle {
                            Layout.preferredHeight: 22
                            Layout.preferredWidth: tagText.implicitWidth + 12
                            radius: 4
                            color: itemCard.getTagBgColor(model.version_tag)
                            border.color: itemCard.getTagBorderColor(model.version_tag)
                            border.width: 1

                            Text {
                                id: tagText
                                anchors.centerIn: parent
                                text: model.version_tag
                                color: itemCard.getTagTextColor(model.version_tag)
                                font.pixelSize: 11
                                font.weight: Font.Medium
                            }
                        }

                        // 歌曲信息
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            RowLayout {
                                spacing: 8
                                Text {
                                    text: model.title
                                    color: "#f8fafc"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                    Layout.maximumWidth: 180
                                }
                                Text {
                                    text: "•  " + model.artist
                                    color: "#cbd5e1"
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    Layout.maximumWidth: 140
                                }
                            }

                            RowLayout {
                                spacing: 6
                                Text {
                                    text: model.source_label
                                    color: "#64748b"
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: " | " + model.album
                                    color: "#475569"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.maximumWidth: 200
                                }
                            }
                        }

                        // 音质规格与大小
                        ColumnLayout {
                            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                            spacing: 2

                            Text {
                                text: model.format + "  " + model.bitrate
                                color: model.format === "FLAC" ? "#fbbf24" : "#94a3b8"
                                font.pixelSize: 12
                                font.weight: Font.Bold
                                horizontalAlignment: Text.AlignRight
                            }

                            Text {
                                text: model.size_str
                                color: "#64748b"
                                font.pixelSize: 11
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    MouseArea {
                        id: mouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            selectionDialogItem.selectedIndex = index;
                        }
                        onDoubleClicked: {
                            selectionDialogItem.selectedIndex = index;
                            selectionDialogItem.confirmCurrentSelection();
                        }
                    }
                }
            }

            // 分割线
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: "#1f2e40"
            }

            // 3. 底部操作栏
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: "💡 双击任意选项即可立即下载入库并播放"
                    color: "#64748b"
                    font.pixelSize: 11
                    Layout.fillWidth: true
                }

                Button {
                    id: cancelBtn
                    text: "取消"
                    implicitWidth: 78
                    implicitHeight: 32
                    background: Rectangle {
                        color: cancelBtn.hovered ? "#243548" : "#1a2636"
                        border.color: "#2e4157"
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
                    onClicked: selectionDialogItem.cancelSelection()
                }

                Button {
                    id: confirmBtn
                    property bool isNetdisk: selectionDialogItem.selectedIndex >= 0 &&
                                             selectionDialogItem.selectedIndex < candidateModel.count &&
                                             candidateModel.get(selectionDialogItem.selectedIndex).is_netdisk

                    text: isNetdisk ? "直达网盘转存 🚀" : "下载并开播 🎵"
                    implicitWidth: 128
                    implicitHeight: 32
                    background: Rectangle {
                        color: confirmBtn.hovered ? "#2563eb" : "#1d4ed8"
                        radius: 6
                    }
                    contentItem: Text {
                        text: confirmBtn.text
                        color: "#ffffff"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: selectionDialogItem.confirmCurrentSelection()
                }
            }
        }
    }
}
