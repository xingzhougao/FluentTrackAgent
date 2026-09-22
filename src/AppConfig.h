#pragma once

#include <QObject>
#include <QString>

class AppConfig : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString localMusicDir READ localMusicDir CONSTANT)
    Q_PROPERTY(QString downloadMusicDir READ downloadMusicDir CONSTANT)
    Q_PROPERTY(QString recommendMusicDir READ recommendMusicDir CONSTANT)
    Q_PROPERTY(int recommendCount READ recommendCount CONSTANT)
    Q_PROPERTY(QString configDir READ configDir CONSTANT)
    Q_PROPERTY(QString favoritesIniPath READ favoritesIniPath CONSTANT)
    Q_PROPERTY(QString recentTracksIniPath READ recentTracksIniPath CONSTANT)
    Q_PROPERTY(QString playlistsIniPath READ playlistsIniPath CONSTANT)
    Q_PROPERTY(QString playlistsFilePath READ playlistsFilePath CONSTANT)
    Q_PROPERTY(QString playlistsJsonPath READ playlistsJsonPath CONSTANT)

public:
    static AppConfig & instance();

    QString projectRoot() const;
    QString configIniPath() const;

    QString localMusicDir() const;
    QString downloadMusicDir() const;
    QString recommendMusicDir() const;
    int recommendCount() const;

    QString configDir() const;
    QString favoritesIniPath() const;
    QString recentTracksIniPath() const;
    QString playlistsIniPath() const;
    QString playlistsFilePath() const;
    QString playlistsJsonPath() const;

    Q_INVOKABLE QString resolvePath(const QString & path) const;
    void reload();

private:
    explicit AppConfig(QObject * parent = nullptr);
    ~AppConfig() override = default;
    Q_DISABLE_COPY(AppConfig)

    void findProjectRoot();
    void loadFromIni();

    QString m_projectRoot;
    QString m_configIniPath;

    QString m_localMusicDir;
    QString m_downloadMusicDir;
    QString m_recommendMusicDir;
    int m_recommendCount = 42;

    QString m_configDir;
    QString m_favoritesIniPath;
    QString m_recentTracksIniPath;
    QString m_playlistsJsonPath;
};
