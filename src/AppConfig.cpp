#include "AppConfig.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QSettings>
#include <QDebug>

AppConfig & AppConfig::instance()
{
    static AppConfig config;
    return config;
}

AppConfig::AppConfig(QObject * parent)
    : QObject(parent)
{
    findProjectRoot();
    loadFromIni();
}

void AppConfig::findProjectRoot()
{
    const QString appDir = QCoreApplication::applicationDirPath();
    const QString currentDir = QDir::currentPath();

    // 探测候选根目录
    const QStringList candidates = {
        QDir::cleanPath(appDir + QStringLiteral("/../../")),   // Qt Shadow Build: build/Desktop_... -> 根目录
        QDir::cleanPath(appDir + QStringLiteral("/../")),
        appDir,
        currentDir
    };

    m_projectRoot = appDir; // 默认回退
    for (const QString & candidate : candidates)
    {
        if (QFile::exists(candidate + QStringLiteral("/config/config.ini")) ||
            QFile::exists(candidate + QStringLiteral("/CMakeLists.txt")) ||
            QDir(candidate + QStringLiteral("/config")).exists())
        {
            m_projectRoot = candidate;
            break;
        }
    }

    m_configIniPath = resolvePath(QStringLiteral("config/config.ini"));
    qDebug() << "[AppConfig] 探测到项目根目录:" << m_projectRoot;
    qDebug() << "[AppConfig] 配置文件路径:" << m_configIniPath;
}

QString AppConfig::resolvePath(const QString & path) const
{
    if (path.isEmpty())
        return {};
    if (QDir::isRelativePath(path))
    {
        return QDir::cleanPath(m_projectRoot + QStringLiteral("/") + path);
    }
    return QDir::cleanPath(path);
}

void AppConfig::loadFromIni()
{
    // 如果配置文件不存在，自动生成默认配置
    if (!QFile::exists(m_configIniPath))
    {
        QFileInfo iniInfo(m_configIniPath);
        QDir().mkpath(iniInfo.absolutePath());

        QSettings defaultSettings(m_configIniPath, QSettings::IniFormat);
        defaultSettings.setValue(QStringLiteral("Music/local_music_dir"), QStringLiteral("qml/music_resource/loadmusic_by_default"));
        defaultSettings.setValue(QStringLiteral("Music/recommend_music_dir"), QStringLiteral("downloaded_songs"));
        defaultSettings.setValue(QStringLiteral("Music/recommend_count"), 42);

        defaultSettings.setValue(QStringLiteral("Storage/config_dir"), QStringLiteral("config"));
        defaultSettings.setValue(QStringLiteral("Storage/playlists_file"), QStringLiteral("config/playlists.ini"));
        defaultSettings.setValue(QStringLiteral("Storage/favorites_file"), QStringLiteral("config/favorites.ini"));
        defaultSettings.setValue(QStringLiteral("Storage/recent_tracks_file"), QStringLiteral("config/recent_tracks.ini"));
        defaultSettings.sync();
    }

    QSettings settings(m_configIniPath, QSettings::IniFormat);

    // 读取音乐目录
    QString rawLocalDir = settings.value(QStringLiteral("Music/local_music_dir"), QStringLiteral("qml/music_resource/loadmusic_by_default")).toString();
    m_localMusicDir = resolvePath(rawLocalDir);
    QDir(m_localMusicDir).mkpath(QStringLiteral("."));

    QString rawDownloadDir = settings.value(QStringLiteral("Music/download_music_dir"), QStringLiteral("downloaded_songs")).toString();
    m_downloadMusicDir = resolvePath(rawDownloadDir);
    QDir(m_downloadMusicDir).mkpath(QStringLiteral("."));

    QString rawRecommendDir = settings.value(QStringLiteral("Music/recommend_music_dir"), QStringLiteral("downloaded_songs")).toString();
    m_recommendMusicDir = resolvePath(rawRecommendDir);
    // 若推荐目录不存在或为空，则自动回退到本地音乐目录
    if (!QDir(m_recommendMusicDir).exists() || QDir(m_recommendMusicDir).isEmpty())
    {
        m_recommendMusicDir = m_localMusicDir;
    }

    m_recommendCount = settings.value(QStringLiteral("Music/recommend_count"), 42).toInt();
    if (m_recommendCount <= 0)
        m_recommendCount = 42;

    // 读取存储文件路径
    QString rawConfigDir = settings.value(QStringLiteral("Storage/config_dir"), QStringLiteral("config")).toString();
    m_configDir = resolvePath(rawConfigDir);
    QDir(m_configDir).mkpath(QStringLiteral("."));

    QString rawFavorites = settings.value(QStringLiteral("Storage/favorites_file"), QStringLiteral("config/favorites.ini")).toString();
    m_favoritesIniPath = resolvePath(rawFavorites);

    QString rawRecent = settings.value(QStringLiteral("Storage/recent_tracks_file"), QStringLiteral("config/recent_tracks.ini")).toString();
    m_recentTracksIniPath = resolvePath(rawRecent);

    QString rawPlaylists = settings.value(QStringLiteral("Storage/playlists_file"), QStringLiteral("config/playlists.ini")).toString();
    m_playlistsJsonPath = resolvePath(rawPlaylists);

    qDebug() << "[AppConfig] 本地音乐目录:" << m_localMusicDir;
    qDebug() << "[AppConfig] 下载音乐目录:" << m_downloadMusicDir;
    qDebug() << "[AppConfig] 推荐音乐目录:" << m_recommendMusicDir;
    qDebug() << "[AppConfig] 收藏夹INI:" << m_favoritesIniPath;
    qDebug() << "[AppConfig] 最近播放INI:" << m_recentTracksIniPath;
    qDebug() << "[AppConfig] 歌单文件:" << m_playlistsJsonPath;
}

void AppConfig::reload()
{
    loadFromIni();
}

QString AppConfig::projectRoot() const { return m_projectRoot; }
QString AppConfig::configIniPath() const { return m_configIniPath; }
QString AppConfig::localMusicDir() const { return m_localMusicDir; }
QString AppConfig::downloadMusicDir() const { return m_downloadMusicDir; }
QString AppConfig::recommendMusicDir() const { return m_recommendMusicDir; }
int AppConfig::recommendCount() const { return m_recommendCount; }
QString AppConfig::configDir() const { return m_configDir; }
QString AppConfig::favoritesIniPath() const { return m_favoritesIniPath; }
QString AppConfig::recentTracksIniPath() const { return m_recentTracksIniPath; }
QString AppConfig::playlistsIniPath() const { return m_playlistsJsonPath; }
QString AppConfig::playlistsFilePath() const { return m_playlistsJsonPath; }
QString AppConfig::playlistsJsonPath() const { return m_playlistsJsonPath; }
