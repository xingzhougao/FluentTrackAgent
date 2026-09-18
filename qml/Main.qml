import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"
import "pages"
import "agent"

ApplicationWindow {
    id: window

    width: 1480
    height: 900
    minimumWidth: 1180
    minimumHeight: 720
    visible: true
    title: "Fluent Music"
    color: "#0b1017"

    property int selectedNav: 0
    property bool lyricViewOpen: false
    property string currentSearchKeyword: ""

    function openSearchResult(keyword) {
        var kw = (keyword || "").trim();
        if (kw.length === 0) return;
        currentSearchKeyword = kw;
        topBar.setSearchText(kw);
        if (typeof searchLibrary !== "undefined" && typeof musicLibrary !== "undefined") {
            searchLibrary.searchFromModel(musicLibrary, kw);
        }
        window.lyricViewOpen = false;
        window.selectedNav = 7;
        if (sideBar) sideBar.selectedIndex = -1;
    }

    function openSearchResultAndPlay(keyword, targetIndex) {
        openSearchResult(keyword);
        if (player && typeof searchLibrary !== "undefined" && searchLibrary.count > 0) {
            var idx = (targetIndex >= 0 && targetIndex < searchLibrary.count) ? targetIndex : 0;
            player.playFromModel(searchLibrary, idx);
        }
    }

    onSelectedNavChanged: {
        if (typeof sideBar !== "undefined" && sideBar) {
            if (window.selectedNav === 7) {
                sideBar.selectedIndex = -1;
            } else {
                sideBar.selectedIndex = window.selectedNav;
            }
        }
    }

    readonly property color panelColor: "#101721"
    readonly property color panelColor2: "#131c27"
    readonly property color borderColor: "#1f2b3a"
    readonly property color textPrimaryColor: "#f5f7fb"
    readonly property color textSecondaryColor: "#8c99aa"
    readonly property color accentColor: "#6ea8ff"

    //桌面歌词窗口
    DesktopLyricWindow{
        id: desktopLyric
    }

    Rectangle {
        anchors.fill: parent
        color: window.color

        Rectangle {
            width: 480
            height: 480
            radius: 240
            x: window.width - 280
            y: -280
            color: "#142b5d91"
            opacity: 0.24
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TopBar {
            id: topBar
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? implicitHeight : 0
            visible: !window.lyricViewOpen
            borderColor: window.borderColor
            textPrimaryColor: window.textPrimaryColor
            textSecondaryColor: window.textSecondaryColor

            onSearchRequested: function(keyword) {
                window.openSearchResult(keyword);
            }

            onSearchItemClicked: function(index, title) {
                window.openSearchResultAndPlay(title, index);
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            //主界面
            RowLayout {
                anchors.fill: parent
                spacing: 0
                visible: !window.lyricViewOpen

                SideBar {
                    id: sideBar
                    Layout.preferredWidth: implicitWidth
                    Layout.fillHeight: true

                    selectedIndex: window.selectedNav
                    borderColor: window.borderColor
                    textPrimaryColor: window.textPrimaryColor
                    textSecondaryColor: window.textSecondaryColor

                    onNavigationRequested: function(index) { window.selectedNav = index}
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    currentIndex: window.selectedNav

                    DiscoverPage {
                        playerController: player
                        recentModel: typeof recentLibrary !== "undefined" ? recentLibrary : null
                        favoriteMgr: typeof favoriteManager !== "undefined" ? favoriteManager : null
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        onPlayRecommendRequested: {
                            //1 为侧边栏推荐页面
                            window.selectedNav = 1;
                            sideBar.selectedIndex = 1;
                            if(player && typeof recommendLibrary !== "undefined" && recommendLibrary.count > 0)
                            {
                                player.playFromModel(recommendLibrary,0);
                            }
                        }
                        onViewAllRecentRequested: {
                            //4 为侧边栏最近播放页面
                            window.selectedNav = 4;
                            sideBar.selectedIndex = 4;
                        }
                    }

                    RecommendPage {
                        playerController: player
                        recommendModel: typeof recommendLibrary !== "undefined" ? recommendLibrary : null
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }
                    PlaylistPage {
                        playerController: player
                        localLibrary: typeof musicLibrary !== "undefined" ? musicLibrary : null
                        playlistMgr: typeof playlistManager !== "undefined" ? playlistManager : null
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }
                    LocalMusicPage {
                        playerController: player
                        musicModel: musicLibrary
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }
                    RecentPage {
                        playerController: player
                        recentModel: typeof recentLibrary !== "undefined" ? recentLibrary : null
                        recentMgr: typeof recentManager !== "undefined" ? recentManager : null
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }
                    FavoritePage {
                        playerController: player
                        favoriteModel: typeof favoriteLibrary !== "undefined" ? favoriteLibrary : null
                        favoriteMgr: typeof favoriteManager !== "undefined" ? favoriteManager : null
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }

                    // 索引 6: 智能助手
                    AgentPage {
                        id: agentPage
                        playerController: player
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }

                    // 索引 7: 搜索结果页
                    SearchResultPage {
                        id: searchResultPage
                        playerController: player
                        searchModel: typeof searchLibrary !== "undefined" ? searchLibrary : null
                        favoriteMgr: typeof favoriteManager !== "undefined" ? favoriteManager : null
                        keyword: window.currentSearchKeyword
                        textPrimaryColor: window.textPrimaryColor
                        textSecondaryColor: window.textSecondaryColor
                        accentColor: window.accentColor
                        borderColor: window.borderColor
                    }
                }
            }
            //全屏交互式歌词界面
            LyricPage {
                anchors.fill: parent
                visible: window.lyricViewOpen
                playerController: player
                textPrimaryColor: window.textPrimaryColor
                textSecondaryColor: window.textSecondaryColor
                accentColor: window.accentColor

                onBackRequested: {
                    window.lyricViewOpen = false
                }
            }
        }

        PlayerBar {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight

            playerController: player
            borderColor: window.borderColor
            textPrimaryColor: window.textPrimaryColor
            textSecondaryColor: window.textSecondaryColor

            onLyricRequested: {
                desktopLyric.visible = !desktopLyric.visible
            }

            //相应右下角封面点击
            onLyricPageRequested: {
                window.lyricViewOpen = !window.lyricViewOpen
            }
        }
    }
}
