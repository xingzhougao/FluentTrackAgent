#include "PlaylistManager.h"
#include "FavoriteManager.h"
#include "AppConfig.h"
#include "CoverManager.h"
#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QSettings>
#include <QDateTime>
#include <QRegularExpression>
#include <QTextStream>
#include <QDir>
#include <QDebug>

PlaylistManager::PlaylistManager(QObject * parent)
    : QObject(parent)
{
    loadPlaylists();
}

PlaylistManager::~PlaylistManager()
{
    savePlaylists();
}

int PlaylistManager::playlistCount() const
{
    return m_playlists.size();
}

QVariantList PlaylistManager::getPlaylists() const
{
    QVariantList list;
    for (const auto & entry : m_playlists)
    {
        QVariantMap map;
        map["id"] = entry.id;
        map["name"] = entry.name;
        map["coverUrl"] = entry.coverUrl;
        map["count"] = entry.model ? entry.model->count() : 0;
        list.append(map);
    }
    return list;
}

QString PlaylistManager::createPlaylist(const QString & name, const QString & coverUrl)
{
    QString trimmedName = name.trimmed();
    if (trimmedName.isEmpty())
        trimmedName = QStringLiteral("新建歌单");

    PlaylistEntry entry;
    entry.id = QStringLiteral("pl_%1").arg(QDateTime::currentMSecsSinceEpoch());
    entry.name = trimmedName;
    entry.coverUrl = coverUrl.trimmed();
    entry.model = new MusicLibraryModel(this);
    if(m_favoriteManager)
    {
        m_favoriteManager->registerModel(entry.model);
    }

    m_playlists.append(entry);
    savePlaylists();
    emit playlistsChanged();
    return entry.id;
}

bool PlaylistManager::deletePlaylist(const QString & id)
{
    for (int i = 0; i < m_playlists.size(); ++i)
    {
        if (m_playlists[i].id == id)
        {
            if (m_playlists[i].model)
            {
                m_playlists[i].model->deleteLater();
                m_playlists[i].model = nullptr;
            }
            m_playlists.removeAt(i);
            savePlaylists();
            emit playlistsChanged();
            return true;
        }
    }
    return false;
}

MusicLibraryModel* PlaylistManager::getPlaylistModel(const QString & id) const
{
    for (const auto & entry : m_playlists)
    {
        if (entry.id == id)
            return entry.model;
    }
    return nullptr;
}

QString PlaylistManager::getPlaylistName(const QString & id) const
{
    for (const auto & entry : m_playlists)
    {
        if (entry.id == id)
            return entry.name;
    }
    return QString();
}

QString PlaylistManager::getPlaylistCover(const QString & id) const
{
    for (const auto & entry : m_playlists)
    {
        if (entry.id == id)
            return entry.coverUrl;
    }
    return QString();
}

bool PlaylistManager::addTrackToPlaylist(const QString & playlistId, MusicLibraryModel* source, int sourceIndex)
{
    if (!source || sourceIndex < 0 || sourceIndex >= source->count())
        return false;

    for (auto & entry : m_playlists)
    {
        if (entry.id == playlistId && entry.model)
        {
            entry.model->addTrackFromLibrary(source, sourceIndex);
            savePlaylists();
            emit playlistsChanged();
            return true;
        }
    }
    return false;
}

bool PlaylistManager::removeTrackFromPlaylist(const QString & playlistId, int trackIndex)
{
    for (auto & entry : m_playlists)
    {
        if (entry.id == playlistId && entry.model)
        {
            entry.model->removeTrack(trackIndex);
            savePlaylists();
            emit playlistsChanged();
            return true;
        }
    }
    return false;
}

bool PlaylistManager::moveTrackInPlaylist(const QString & playlistId, int fromIndex, int toIndex)
{
    for (auto & entry : m_playlists)
    {
        if (entry.id == playlistId && entry.model)
        {
            if (entry.model->moveTrack(fromIndex, toIndex))
            {
                savePlaylists();
                emit playlistsChanged();
                return true;
            }
        }
    }
    return false;
}

bool PlaylistManager::playlistContainsTrack(const QString & playlistId, const QString & filePath) const
{
    for (const auto & entry : m_playlists)
    {
        if (entry.id == playlistId && entry.model)
        {
            return entry.model->containsFilePath(filePath);
        }
    }
    return false;
}

QString PlaylistManager::getSaveFilePath() const
{
    return AppConfig::instance().playlistsIniPath();
}

MusicTrack PlaylistManager::resolveTrackFromFile(const QString & filePath) const
{
    MusicTrack track;
    if (filePath.trimmed().isEmpty())
        return track;

    QString resolvedPath = AppConfig::instance().resolvePath(filePath);
    QFileInfo info(resolvedPath);
    if (!info.exists())
    {
        info.setFile(filePath);
    }
    if (!info.exists())
    {
        // 文件确实不存在（例如新机器上尚无歌曲），安全返回空 track，防止添加幽灵坏项
        return track;
    }

    track.filePath = info.absoluteFilePath();
    QString baseName = info.completeBaseName();
    QStringList parts;
    if (baseName.contains(QStringLiteral(" - "))) {
        parts = baseName.split(QStringLiteral(" - "));
    } else if (baseName.contains(QStringLiteral("-"))) {
        parts = baseName.split(QStringLiteral("-"));
    } else if (baseName.contains(QStringLiteral("_"))) {
        parts = baseName.split(QStringLiteral("_"));
    }

    if (parts.size() >= 3)
    {
        track.title = parts[1].trimmed();
        track.artist = parts[2].trimmed();
        track.album = track.title + QStringLiteral(" (单曲)");
    }
    else if (parts.size() == 2)
    {
        track.title = parts[0].trimmed();
        track.artist = parts[1].trimmed();
        track.album = track.title + QStringLiteral(" (单曲)");
    }
    else
    {
        track.title = baseName;
        track.artist = QStringLiteral("未知歌手");
        track.album = QStringLiteral("单曲");
    }

    // 解析同名 .lrc 获取时长
    QString lrcPath = info.absolutePath() + QStringLiteral("/") + baseName + QStringLiteral(".lrc");
    QFile lrcFile(lrcPath);
    if (lrcFile.exists() && lrcFile.open(QIODevice::ReadOnly | QIODevice::Text))
    {
        QTextStream stream(&lrcFile);
        static const QRegularExpression regex(R"(\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\])");
        qint64 lastTime = 0;
        while (!stream.atEnd())
        {
            QString line = stream.readLine();
            auto match = regex.match(line);
            if (match.hasMatch())
            {
                qint64 minutes = match.captured(1).toLongLong();
                qint64 seconds = match.captured(2).toLongLong();
                qint64 ms = 0;
                if (match.captured(3).length() == 2)
                    ms = match.captured(3).toLongLong() * 10;
                else if (match.captured(3).length() == 3)
                    ms = match.captured(3).toLongLong();
                qint64 totalMs = (minutes * 60 + seconds) * 1000 + ms;
                if (totalMs > lastTime)
                    lastTime = totalMs;
            }
        }
        if (lastTime > 0)
            track.duration = lastTime + 3000;
        lrcFile.close();
    }

    if (track.duration <= 0 && info.size() > 0)
    {
        track.duration = (info.size() / 16000) * 1000;
    }

    track.coverUrl = CoverManager::instance().getCoverUrl(track.filePath);

    return track;
}

void PlaylistManager::loadPlaylists()
{
    QString path = getSaveFilePath();
    m_playlists.clear();

    auto parseJsonData = [this](const QByteArray & data) -> bool {
        QJsonDocument doc = QJsonDocument::fromJson(data);
        if (!doc.isArray())
            return false;
        QJsonArray array = doc.array();
        for (const QJsonValue & val : array)
        {
            if (!val.isObject())
                continue;
            QJsonObject obj = val.toObject();

            PlaylistEntry entry;
            entry.id = obj[QStringLiteral("id")].toString();
            entry.name = obj[QStringLiteral("name")].toString();
            entry.coverUrl = obj[QStringLiteral("coverUrl")].toString();
            entry.model = new MusicLibraryModel(this);
            if (m_favoriteManager)
            {
                m_favoriteManager->registerModel(entry.model);
            }
            QJsonArray songs = obj[QStringLiteral("songs")].toArray();
            for (const QJsonValue & sVal : songs)
            {
                QString sPath = sVal.toString();
                if (!sPath.isEmpty())
                {
                    MusicTrack track = resolveTrackFromFile(sPath);
                    if (!track.filePath.isEmpty())
                    {
                        entry.model->appendTrack(track);
                    }
                }
            }
            m_playlists.append(entry);
        }
        return true;
    };

    // 1. 如果指定路径文件已存在
    if (QFile::exists(path))
    {
        if (path.endsWith(QStringLiteral(".json"), Qt::CaseInsensitive))
        {
            QFile file(path);
            if (file.open(QIODevice::ReadOnly))
            {
                parseJsonData(file.readAll());
                file.close();
                return;
            }
        }

        // 按 INI 格式加载
        QSettings settings(path, QSettings::IniFormat);
        int pSize = settings.beginReadArray(QStringLiteral("playlists"));
        for (int i = 0; i < pSize; ++i)
        {
            settings.setArrayIndex(i);
            PlaylistEntry entry;
            entry.id = settings.value(QStringLiteral("id")).toString();
            entry.name = settings.value(QStringLiteral("name")).toString();
            entry.coverUrl = settings.value(QStringLiteral("coverUrl")).toString();
            entry.model = new MusicLibraryModel(this);
            if (m_favoriteManager)
            {
                m_favoriteManager->registerModel(entry.model);
            }

            int sSize = settings.beginReadArray(QStringLiteral("songs"));
            for (int j = 0; j < sSize; ++j)
            {
                settings.setArrayIndex(j);
                QString sPath = settings.value(QStringLiteral("filePath")).toString();
                if (!sPath.isEmpty())
                {
                    MusicTrack track = resolveTrackFromFile(sPath);
                    if (!track.filePath.isEmpty())
                    {
                        entry.model->appendTrack(track);
                    }
                }
            }
            settings.endArray();

            m_playlists.append(entry);
        }
        settings.endArray();
        return;
    }

    // 2. 兼容历史数据：检查是否存在旧版 playlists.json，若存在则导入并平滑迁移到 INI
    QFileInfo fileInfo(path);
    QString legacyJsonPath = fileInfo.absolutePath() + QStringLiteral("/playlists.json");
    if (!QFile::exists(legacyJsonPath))
    {
        legacyJsonPath = QCoreApplication::applicationDirPath() + QStringLiteral("/playlists.json");
    }

    if (QFile::exists(legacyJsonPath))
    {
        QFile file(legacyJsonPath);
        if (file.open(QIODevice::ReadOnly))
        {
            if (parseJsonData(file.readAll()))
            {
                qDebug() << "[PlaylistManager] 从历史 JSON 导入" << m_playlists.size() << "个歌单，并自动转换为 INI 格式保存";
                savePlaylists();
            }
            file.close();
        }
    }
}

void PlaylistManager::setFavoriteManager(FavoriteManager * manager)
{
    m_favoriteManager = manager;
    if(m_favoriteManager)
    {
        for(auto & entry : m_playlists)
        {
            if(entry.model)
            {
                m_favoriteManager->registerModel(entry.model);
            }
        }
    }
}

void PlaylistManager::savePlaylists()
{
    QString path = getSaveFilePath();
    QFileInfo info(path);
    QDir().mkpath(info.absolutePath());

    QString projRoot = AppConfig::instance().projectRoot();
    QDir rootDir(projRoot);

    if (path.endsWith(QStringLiteral(".json"), Qt::CaseInsensitive))
    {
        QFile file(path);
        if (!file.open(QIODevice::WriteOnly))
            return;

        QJsonArray array;
        for (const auto & entry : m_playlists)
        {
            QJsonObject obj;
            obj[QStringLiteral("id")] = entry.id;
            obj[QStringLiteral("name")] = entry.name;
            obj[QStringLiteral("coverUrl")] = entry.coverUrl;

            QJsonArray songs;
            if (entry.model)
            {
                const QStringList paths = entry.model->allFilePaths();
                for (const QString & p : paths)
                {
                    QString rel = rootDir.relativeFilePath(p);
                    if (!rel.startsWith(QStringLiteral("..")) && !QDir::isAbsolutePath(rel)) {
                        songs.append(rel);
                    } else {
                        songs.append(p);
                    }
                }
            }
            obj[QStringLiteral("songs")] = songs;
            array.append(obj);
        }

        QJsonDocument doc(array);
        file.write(doc.toJson(QJsonDocument::Indented));
        file.close();
        return;
    }

    // 保存为标准 INI 格式
    QSettings settings(path, QSettings::IniFormat);
    settings.clear();
    settings.beginWriteArray(QStringLiteral("playlists"), m_playlists.size());
    for (int i = 0; i < m_playlists.size(); ++i)
    {
        settings.setArrayIndex(i);
        const auto & entry = m_playlists[i];
        settings.setValue(QStringLiteral("id"), entry.id);
        settings.setValue(QStringLiteral("name"), entry.name);
        settings.setValue(QStringLiteral("coverUrl"), entry.coverUrl);

        QStringList paths = entry.model ? entry.model->allFilePaths() : QStringList();
        settings.beginWriteArray(QStringLiteral("songs"), paths.size());
        for (int j = 0; j < paths.size(); ++j)
        {
            settings.setArrayIndex(j);
            QString songPath = paths[j];
            QString rel = rootDir.relativeFilePath(songPath);
            if (!rel.startsWith(QStringLiteral("..")) && !QDir::isAbsolutePath(rel)) {
                settings.setValue(QStringLiteral("filePath"), rel);
            } else {
                settings.setValue(QStringLiteral("filePath"), songPath);
            }
        }
        settings.endArray();
    }
    settings.endArray();
    settings.sync();
}
