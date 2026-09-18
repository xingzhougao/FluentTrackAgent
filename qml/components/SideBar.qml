import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle{
    id: root
    implicitWidth: 232
    color: "#0d141d"
    border.color: root.borderColor
    border.width: 1

    property int selectedIndex: 0
    property color borderColor: "#1f2b3a"
    property color textPrimaryColor: "#f5f7fb"
    property color textSecondaryColor: "#8c99aa"

    signal navigationRequested(int index)

    ColumnLayout{
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        Text{
            text: "音乐"
            color: "#68778a"
            font.pixelSize: 11
            font.weight: Font.DemiBold
            x:10
        }

        Repeater{
            model: [
                { t:"发现音乐",i:"../icons/discover_music.svg"},
                { t:"推荐",i:"../icons/recommend.svg"},
                { t:"歌单",i:"../icons/playlist.svg"},
                { t:"本地音乐",i:"../icons/local_music.svg"},
                { t:"最近播放",i:"../icons/recently_player.svg"}
            ]

            delegate: NavButton{
                required property var modelData
                required property int index

                Layout.fillWidth: true
                //Layout.fillHeight: false
                //Layout.preferredHeight: 46
                text: modelData.t
                iconSource: modelData.i
                selected: root.selectedIndex === index      // ===是比较

                onClicked: {
                    root.navigationRequested(index)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            color: "#1c2735"
        }

        Text{
            text: "我的音乐"
            color: "#68778a"
            font.pixelSize: 11
            font.weight: Font.DemiBold
            x:10
        }

        NavButton{
            Layout.fillWidth: true
            //Layout.fillHeight: false
            //Layout.preferredHeight: 46
            text: "我喜欢的音乐"
            iconSource:"../icons/my_love.svg"
            selected: root.selectedIndex === 5

            onClicked: {
                root.navigationRequested(5)
            }
        }

        NavButton{
            Layout.fillWidth: true
            text: "智能助手"
            iconSource: "../icons/agent.svg"
            selected: root.selectedIndex === 6

            onClicked: {
                root.navigationRequested(6)
            }
        }

        Item { Layout.fillHeight: true}         //加一个弹簧填充不然会自动拉伸控件
    }
}
