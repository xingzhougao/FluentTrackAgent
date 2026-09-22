cmake_minimum_required(VERSION 3.16)

project(FluentWinUI_Musicplayer VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(QT_QML_GENERATE_QMLLS_INI ON)

find_package(Qt6 REQUIRED COMPONENTS Quick QuickControls2 Multimedia WebSockets Network)

qt_standard_project_setup(REQUIRES 6.8)

# Content of downloaded design from Figma to Qt or similar
if (EXISTS "${CMAKE_CURRENT_LIST_DIR}/importedcontent/CMakeLists.txt")
    add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/importedcontent)
endif()

qt_add_executable(appFluentWinUI_Musicplayer

)

qt_add_qml_module(appFluentWinUI_Musicplayer
    URI FluentWinUI_Musicplayer
    QML_FILES
    SOURCES src/main.cpp
    QML_FILES qml/Main.qml
    QML_FILES qml/components/TopBar.qml
    QML_FILES qml/components/SideBar.qml
    QML_FILES qml/components/NavButton.qml
    QML_FILES
    QML_FILES qml/components/AlbumCard.qml
    QML_FILES qml/components/MusicRow.qml
    QML_FILES qml/components/PlayerBar.qml
    QML_FILES qml/pages/DiscoverPage.qml
    QML_FILES qml/pages/LocalMusicPage.qml
    QML_FILES qml/pages/PlaylistPage.qml
    QML_FILES qml/pages/RecentPage.qml
    QML_FILES qml/pages/RecommendPage.qml
    QML_FILES qml/components/DesktopLyricWindow.qml
    QML_FILES qml/pages/LyricPage.qml
    QML_FILES qml/pages/FavoritePage.qml
    QML_FILES qml/pages/SearchResultPage.qml
    QML_FILES qml/agent/AgentPage.qml
    QML_FILES qml/agent/AgentChatView.qml
    QML_FILES qml/agent/AgentMessageDelegate.qml
    QML_FILES qml/agent/AgentToolCard.qml
    QML_FILES qml/agent/AgentThinkingIndicator.qml
    QML_FILES qml/agent/AgentConfirmDialog.qml
    QML_FILES qml/agent/AgentTrackSelectionDialog.qml
    QML_FILES qml/agent/AgentInputBar.qml
    QML_FILES qml/agent/AgentSettingsDialog.qml
    SOURCES
        src/PlayerController.h
        src/PlayerController.cpp
        src/MusicLibraryModel.h
        src/MusicLibraryModel.cpp
        src/PlaylistManager.h
        src/PlaylistManager.cpp
        src/RecentManager.h
        src/RecentManager.cpp
        src/MusicTrack.h
        src/Lyric.h
        src/FavoriteManager.h
        src/FavoriteManager.cpp
        src/AppConfig.h
        src/AppConfig.cpp
        src/CoverManager.h
        src/CoverManager.cpp
        src/agent/MusicAgentTransport.h
        src/agent/MusicAgentTransport.cpp
        src/agent/AgentMessageModel.h
        src/agent/AgentMessageModel.cpp
        src/agent/MusicAgentController.h
        src/agent/MusicAgentController.cpp
        src/agent/ToolDispatcher.h
        src/agent/ToolDispatcher.cpp

    RESOURCES
        qml/icons/agent.svg
        qml/icons/download_manager.svg
        qml/icons/my_love.svg
        qml/icons/discover_music.svg
        qml/icons/recommend.svg
        qml/icons/playlist.svg
        qml/icons/local_music.svg
        qml/icons/recently_player.svg
        qml/icons/setting_button.svg
        qml/icons/menu_bar.svg
        qml/icons/previous.svg
        qml/icons/next.svg
        qml/icons/play.svg
        qml/icons/pause.svg
        qml/icons/restart.svg
        qml/icons/volume.svg
        qml/icons/mute.svg
        qml/icons/sequence.svg
        qml/icons/random.svg
        qml/icons/repeat.svg
        qml/icons/like.svg
        qml/icons/cancel_like.svg
        qml/icons/cancel_like_blue.svg
        qml/icons/addvolume.svg
        qml/icons/recvolume.svg
        qml/icons/playlist_delete.svg
        qml/icons/search.svg
        qml/image_resource/alone_night.png
        qml/image_resource/city_wandering.png
        qml/image_resource/focused_coding.png
        qml/image_resource/midnight_neon.png
        qml/image_resource/morning_clarity.png
        qml/image_resource/night_road.png
        qml/image_resource/rainy_room.png
        qml/image_resource/weekend_coffee.png
        qml/image_resource/banner.png
)

# Qt for iOS sets MACOSX_BUNDLE_GUI_IDENTIFIER automatically since Qt 6.1.
# If you are developing for iOS or macOS you should consider setting an
# explicit, fixed bundle identifier manually though.
set_target_properties(appFluentWinUI_Musicplayer PROPERTIES
#    MACOSX_BUNDLE_GUI_IDENTIFIER com.example.appFluentWinUI_Musicplayer
    MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
    MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}
    MACOSX_BUNDLE TRUE
    WIN32_EXECUTABLE TRUE
)

target_link_libraries(appFluentWinUI_Musicplayer
    PRIVATE Qt6::Quick Qt6::QuickControls2 Qt6::Multimedia Qt6::WebSockets Qt6::Network
)

install(TARGETS appFluentWinUI_Musicplayer
    BUNDLE DESTINATION .
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
