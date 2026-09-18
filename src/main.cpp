#include <QGuiApplication>              //Qt GUI程序基础应用对象
#include <QQmlApplicationEngine>        //用于加载运行QML
#include <QQmlContext>
#include <QQuickStyle>
#include "PlayerController.h"
#include "MusicLibraryModel.h"
#include "PlaylistManager.h"
#include "RecentManager.h"
#include "FavoriteManager.h"
#include "AppConfig.h"
#include "agent/MusicAgentController.h"
#include <QDir>

int main(int argc,char * argv[])
{
    QQuickStyle::setStyle("Basic");
    QGuiApplication app(argc,argv);

    AppConfig & config = AppConfig::instance();

    //创建音乐库Model
    MusicLibraryModel library;
    library.scanDirectory(config.localMusicDir());

    //创建推荐音乐库 每次程序启动后重新抽取
    MusicLibraryModel recommendLibrary;
    recommendLibrary.scanRandomDirectory(config.recommendMusicDir(), config.recommendCount());

    //创建播放器
    PlayerController player(&library);
    //创建歌单管理器
    PlaylistManager playlistManager;
    //创建最近播放管理器
    RecentManager recentManager;
    player.setRecentManager(&recentManager);
    //创建我的喜欢音乐管理器
    FavoriteManager favoriteManager;
    favoriteManager.registerModel(&library);
    favoriteManager.registerModel(&recommendLibrary);
    favoriteManager.registerModel(recentManager.model());

    MusicLibraryModel searchLibrary;
    MusicLibraryModel suggestLibrary;
    favoriteManager.registerModel(&searchLibrary);
    favoriteManager.registerModel(&suggestLibrary);

    player.setFavoriteManager(&favoriteManager);
    playlistManager.setFavoriteManager(&favoriteManager);

    MusicAgentController agentController;

    QQmlApplicationEngine engine;       //创建QML引擎
    engine.rootContext()->setContextProperty("appConfig", &config);
    engine.rootContext()->setContextProperty("player",&player);
    engine.rootContext()->setContextProperty("musicLibrary",&library);
    engine.rootContext()->setContextProperty("recommendLibrary",&recommendLibrary);
    engine.rootContext()->setContextProperty("playlistManager",&playlistManager);
    engine.rootContext()->setContextProperty("recentManager",&recentManager);
    engine.rootContext()->setContextProperty("recentLibrary",recentManager.model());
    engine.rootContext()->setContextProperty("favoriteManager",&favoriteManager);
    engine.rootContext()->setContextProperty("favoriteLibrary",favoriteManager.model());
    engine.rootContext()->setContextProperty("searchLibrary",&searchLibrary);
    engine.rootContext()->setContextProperty("suggestLibrary",&suggestLibrary);
    engine.rootContext()->setContextProperty("agentController", &agentController);
    engine.rootContext()->setContextProperty("agentMessageModel", agentController.messageModel());

    QObject::connect(&engine,&QQmlApplicationEngine::objectCreationFailed,&app,
                     [](){QCoreApplication::exit(-1);},Qt::QueuedConnection);

    //从名为FluentWinUI_Musicplayer的QML模块中加载Main.qml
    engine.loadFromModule("FluentWinUI_Musicplayer","Main");
    return app.exec();
}