#include "MusicLibraryModel.h"
#include "FavoriteManager.h"
#include "CoverManager.h"
#include <QDirIterator>
#include <QFileInfo>
#include <QFile>
#include <QTextStream>
#include <QRegularExpression>
#include <algorithm>
#include <QRandomGenerator>

MusicLibraryModel::MusicLibraryModel(QObject * parent) : QAbstractListModel(parent){}

int MusicLibraryModel::rowCount(const QModelIndex & parent) const
{
    if(parent.isValid())
        return 0;
    return m_tracks.size();
}

int MusicLibraryModel::count() const
{
    return m_tracks.size();
}

QVariant MusicLibraryModel::data(const QModelIndex & index,int role) const
{
    if(!index.isValid())
        return {};

    if(index.row() < 0 || index.row() >= m_tracks.size())
        return {};

    const MusicTrack & track = m_tracks[index.row()];
    switch(role)
    {
    case FilePathRole:
        return track.filePath;
    case TitleRole:
        return track.title;
    case ArtistRole:
        return track.artist;
    case AlbumRole:
        return track.album;
    case DurationRole:
        return track.duration;
    case FavoriteRole:
        return track.favorite;
    case LastPlayedRole:
        return track.lastPlayed;
    case CoverUrlRole:
        return track.coverUrl;
    default:
        return {};
    }
}

QHash<int,QByteArray> MusicLibraryModel::roleNames() const
{
    return {
        {FilePathRole, "filePath"},
        {TitleRole, "title"},
        {ArtistRole,"artist"},
        {AlbumRole,"album"},
        {DurationRole,"duration"},
        {FavoriteRole,"favorite"},
        {LastPlayedRole,"lastPlayed"},
        {CoverUrlRole, "coverUrl"}
    };
}

void MusicLibraryModel::scanDirectory(const QString & directory)
{
    beginResetModel();
    m_tracks.clear();
    QStringList filters {
        "*.mp3",
        "*.wav",
        "*.flac",
        "*.m4a",
        "*.aac",
        "*.ogg"
    };
    //从哪里开始扫描   哪些文件名符合要求  只要求扫描文件  递归扫描子目录
    QDirIterator iterator(directory,filters,QDir::Files,QDirIterator::Subdirectories);
    while(iterator.hasNext())
    {
        QString filePath = iterator.next();
        QFileInfo info(filePath);
        MusicTrack track;
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

        //提取文件名中的序号 歌曲 歌手
        if(parts.size() >= 3)
        {
            track.title = parts[1].trimmed();
            track.artist = parts[2].trimmed();
            track.album = track.title + " (单曲)";
        }else if(parts.size() == 2)
        {
            track.title = parts[0].trimmed();
            track.artist = parts[1].trimmed();
            track.album = track.title + " (单曲)";
        }else {
            track.title = baseName;
            track.artist = "未知歌手";
            track.album = "热门单曲";
        }
        //读取同名.lrc文件解析最后一行的时间戳得到毫秒总时长
        QString lrcPath = info.absolutePath() + "/" + baseName + ".lrc";
        QFile lrcFile(lrcPath);
        if(lrcFile.exists() && lrcFile.open(QIODevice::ReadOnly | QIODevice::Text))
        {
            QTextStream stream(&lrcFile);
            static const QRegularExpression regex(R"(\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\])");
            qint64 lastTimestamp = 0;
            while(!stream.atEnd())
            {
                QString line = stream.readLine();
                QRegularExpressionMatchIterator it = regex.globalMatch(line);
                while(it.hasNext())
                {
                    QRegularExpressionMatch match = it.next();
                    int mm = match.captured(1).toInt();     //分
                    int ss = match.captured(2).toInt();     //秒
                    QString frac = match.captured(3);
                    int ms = 0;
                    if(frac.length() == 1)
                    {
                        ms = frac.toInt() * 100;
                    }else if(frac.length() == 2)
                    {
                        ms = frac.toInt() * 10;
                    }else if(frac.length() >= 3)
                    {
                        ms = frac.left(3).toInt();
                    }
                    qint64 t = (mm * 60 + ss) * 1000 + ms;
                    if(t > lastTimestamp)
                        lastTimestamp = t;
                }
            }
            if(lastTimestamp > 0)
            {
                track.duration = lastTimestamp + 5000;
            }
            lrcFile.close();
        }
        if(track.duration <= 0 && info.size() > 0)
        {
            track.duration = (info.size() / 16000) * 1000;  //兜底估算
        }
        if(m_favoriteManager)
        {
            track.favorite = m_favoriteManager->isFavorite(track.filePath);
        }
        track.coverUrl = CoverManager::instance().getCoverUrl(track.filePath);
        m_tracks.append(track);
    }
    std::sort(m_tracks.begin(),m_tracks.end(),[](const MusicTrack & a,const MusicTrack & b){
        return a.filePath.localeAwareCompare(b.filePath) < 0;
    });
    endResetModel();
    emit countChanged();
}

void MusicLibraryModel::appendDirectory(const QString & directory)
{
    if (directory.isEmpty())
        return;
    QDir dir(directory);
    if (!dir.exists())
        return;

    QStringList filters {
        "*.mp3",
        "*.wav",
        "*.flac",
        "*.m4a",
        "*.aac",
        "*.ogg"
    };

    QDirIterator iterator(directory, filters, QDir::Files, QDirIterator::Subdirectories);
    QVector<MusicTrack> newTracks;

    while (iterator.hasNext())
    {
        QString filePath = iterator.next();
        QFileInfo info(filePath);
        QString absPath = info.absoluteFilePath();

        QString baseName = info.completeBaseName();
        QString candidateTitle, candidateArtist, candidateAlbum;
        QStringList parts = baseName.split(" - ");
        if (parts.size() >= 3)
        {
            candidateTitle = parts[1].trimmed();
            candidateArtist = parts[2].trimmed();
            candidateAlbum = candidateTitle + " (单曲)";
        }
        else if (parts.size() == 2)
        {
            candidateTitle = parts[0].trimmed();
            candidateArtist = parts[1].trimmed();
            candidateAlbum = candidateTitle + " (单曲)";
        }
        else
        {
            candidateTitle = baseName;
            candidateArtist = "未知歌手";
            candidateAlbum = "热门单曲";
        }

        bool exists = false;
        for (const MusicTrack & existing : m_tracks)
        {
            if (existing.filePath == absPath ||
                (existing.title.compare(candidateTitle, Qt::CaseInsensitive) == 0 &&
                 existing.artist.compare(candidateArtist, Qt::CaseInsensitive) == 0))
            {
                exists = true;
                break;
            }
        }
        if (!exists)
        {
            for (const MusicTrack & added : newTracks)
            {
                if (added.filePath == absPath ||
                    (added.title.compare(candidateTitle, Qt::CaseInsensitive) == 0 &&
                     added.artist.compare(candidateArtist, Qt::CaseInsensitive) == 0))
                {
                    exists = true;
                    break;
                }
            }
        }
        if (exists)
            continue;

        MusicTrack track;
        track.filePath = absPath;
        track.title = candidateTitle;
        track.artist = candidateArtist;
        track.album = candidateAlbum;

        // 读取同名.lrc文件解析最后一行的时间戳得到毫秒总时长
        QString lrcPath = info.absolutePath() + "/" + baseName + ".lrc";
        QFile lrcFile(lrcPath);
        if (lrcFile.exists() && lrcFile.open(QIODevice::ReadOnly | QIODevice::Text))
        {
            QTextStream stream(&lrcFile);
            static const QRegularExpression regex(R"(\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\])");
            qint64 lastTimestamp = 0;
            while (!stream.atEnd())
            {
                QString line = stream.readLine();
                QRegularExpressionMatchIterator it = regex.globalMatch(line);
                while (it.hasNext())
                {
                    QRegularExpressionMatch match = it.next();
                    int mm = match.captured(1).toInt();
                    int ss = match.captured(2).toInt();
                    QString frac = match.captured(3);
                    int ms = 0;
                    if (frac.length() == 1)
                        ms = frac.toInt() * 100;
                    else if (frac.length() == 2)
                        ms = frac.toInt() * 10;
                    else if (frac.length() >= 3)
                        ms = frac.left(3).toInt();

                    qint64 t = (mm * 60 + ss) * 1000 + ms;
                    if (t > lastTimestamp)
                        lastTimestamp = t;
                }
            }
            if (lastTimestamp > 0)
                track.duration = lastTimestamp + 5000;
            lrcFile.close();
        }

        if (track.duration <= 0 && info.size() > 0)
            track.duration = (info.size() / 16000) * 1000;

        if (m_favoriteManager)
            track.favorite = m_favoriteManager->isFavorite(track.filePath);

        track.coverUrl = CoverManager::instance().getCoverUrl(track.filePath);
        newTracks.append(track);
    }

    if (!newTracks.isEmpty())
    {
        beginInsertRows(QModelIndex(), m_tracks.size(), m_tracks.size() + newTracks.size() - 1);
        m_tracks.append(newTracks);
        endInsertRows();
        emit countChanged();
    }
}


//更新MP3元数据信息
void MusicLibraryModel::updateMetadata(int index,const QString &title,const QString &artist,const QString &album,qint64 duration)
{
    if(index < 0 || index >= m_tracks.size())
        return;

    MusicTrack & track = m_tracks[index];
    if(!title.isEmpty())
        track.title = title;
    if(!artist.isEmpty())
        track.artist = artist;
    if(!album.isEmpty())
        track.album = album;
    if(duration > 0)
        track.duration = duration;
    //index成员函数继承自QAbstractListModel  将index行转换为QModelIndex
    QModelIndex modelIndex = this->index(index);
    //继承自QAbstractItemModel的方法 QAbstractItemModel 是 QAbstractListModel的父类  从哪一行开始变化 到哪一行变化结束 哪些role发生了变化
    emit dataChanged(modelIndex,modelIndex,{TitleRole,ArtistRole,AlbumRole,DurationRole});
}

//最近播放
void MusicLibraryModel::markPlayed(int index)
{
    if(index < 0 || index >= m_tracks.size())
        return;
    m_tracks[index].lastPlayed = QDateTime::currentDateTime();
    QModelIndex modelIndex = this->index(index);
    emit dataChanged(modelIndex,modelIndex,{LastPlayedRole});
}

void MusicLibraryModel::setFavoriteManager(FavoriteManager * manager)
{
    m_favoriteManager = manager;
}

FavoriteManager * MusicLibraryModel::favoriteManager() const
{
    return m_favoriteManager;
}

void MusicLibraryModel::setTrackFavorite(int index,bool favorite)
{
    if(index < 0 || index >= m_tracks.size())
        return;
    if(m_tracks[index].favorite != favorite)
    {
        m_tracks[index].favorite = favorite;
        QModelIndex modelIndex = this->index(index);
        emit dataChanged(modelIndex,modelIndex,{FavoriteRole});
    }
}

void MusicLibraryModel::setFavoriteByFilePath(const QString & filePath,bool isFavorite)
{
    for(int i = 0; i< m_tracks.size();++i)
    {
        if(m_tracks[i].filePath == filePath)
        {
            if(m_tracks[i].favorite != isFavorite)
            {
                m_tracks[i].favorite = isFavorite;
                QModelIndex modelIndex = this->index(i);
                emit dataChanged(modelIndex,modelIndex,{FavoriteRole});
            }
        }
    }
}

//喜欢歌曲
void MusicLibraryModel::toggleFavorite(int index)
{
    if(index < 0 || index >= m_tracks.size())
        return;
    if(m_favoriteManager)
    {
        m_favoriteManager->toggleFavoriteTrack(m_tracks[index]);
        return;
    }
    m_tracks[index].favorite = !m_tracks[index].favorite;
    QModelIndex modelIndex = this->index(index);
    emit dataChanged(modelIndex,modelIndex,{FavoriteRole});
}

//获取歌曲
MusicTrack MusicLibraryModel::trackAt(int index) const
{
    if(index < 0 || index >= m_tracks.size())
        return {};
    return m_tracks[index];
}

void MusicLibraryModel::setLyrics(int index,const QVector<LyricLine> &lyrics)
{
    if(index < 0 || index >= m_tracks.size())
        return;
    m_tracks[index].lyrics = lyrics;
}

void MusicLibraryModel::scanRandomDirectory(const QString & directory,int count)
{
    beginResetModel();
    m_tracks.clear();
    QStringList filters = { "*.mp3","*.flac","*.wav","*.ogg" };
    QDirIterator iterator(directory,filters,QDir::Files,QDirIterator::Subdirectories);
    QStringList allFiles;
    while(iterator.hasNext())
    {
        allFiles.append(iterator.next());
    }

    if(allFiles.isEmpty())
    {
        endResetModel();
        emit countChanged();
        return;
    }

    //使用Qt全局随机生成器将所有歌曲文件打乱
    std::shuffle(allFiles.begin(),allFiles.end(),*QRandomGenerator::global());

    //最多截取count首 (例如42首)
    int pickCount = qMin(count,allFiles.size());
    for(int i = 0; i < pickCount; ++i)
    {
        const QString & filePath = allFiles[i];
        QFileInfo info(filePath);
        MusicTrack track;
        track.filePath = info.absoluteFilePath();
        QString baseName = info.completeBaseName();
        QStringList parts = baseName.split(" - ");
        if(parts.size() >= 3)
        {
            //001 晴天 周杰伦
            track.title = parts[1].trimmed();
            track.artist = parts[2].trimmed();
            track.album = track.title + " (单曲)";
        }
        else if(parts.size() == 2)
        {
            //晴天 周杰伦
            track.title = parts[0].trimmed();
            track.artist = parts[1].trimmed();
            track.album = track.title + " (单曲)";
        }
        else
        {
            track.title = baseName;
            track.artist = "未知歌手";
            track.album = "热门单曲";
        }

        //解析同名 .lrc 获取歌曲时长
        QString lrcPath = info.absolutePath() + "/" + baseName + ".lrc";
        QFile lrcFile(lrcPath);
        if(lrcFile.exists() && lrcFile.open(QIODevice::ReadOnly | QIODevice::Text))
        {
            QTextStream stream(&lrcFile);
            static const QRegularExpression regex(R"(\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\])");
            qint64 lastTime = 0;
            while(!stream.atEnd())
            {
                QString line = stream.readLine();
                auto match = regex.match(line);
                if(match.hasMatch())
                {
                    qint64 minutes = match.captured(1).toLongLong();
                    qint64 seconds = match.captured(2).toLongLong();
                    qint64 ms = 0;
                    if(match.captured(3).length() == 2)
                        ms = match.captured(3).toLongLong() * 10;
                    else if(match.captured(3).length() == 3)
                        ms = match.captured(3).toLongLong();
                    qint64 totalMs = (minutes * 60 + seconds) * 1000 + ms;
                    if(totalMs > lastTime)
                        lastTime = totalMs;
                }
            }
            if(lastTime > 0)
            {
                //歌词最后一行多持续3秒
                track.duration = lastTime + 3000;
            }
            lrcFile.close();
        }
        //无歌词时的估算兜底
        if(track.duration <= 0 && info.size() > 0)
        {
            track.duration = (info.size() / 16000) * 1000;
        }
        if(m_favoriteManager)
        {
            track.favorite = m_favoriteManager->isFavorite(track.filePath);
        }
        track.coverUrl = CoverManager::instance().getCoverUrl(track.filePath);
        m_tracks.append(track);
    }
    endResetModel();
    emit countChanged();
}

void MusicLibraryModel::appendTrack(const MusicTrack & track)
{
    MusicTrack t = track;
    if (t.coverUrl.isEmpty() && !t.filePath.isEmpty())
    {
        t.coverUrl = CoverManager::instance().getCoverUrl(t.filePath);
    }
    beginInsertRows(QModelIndex(), m_tracks.size(), m_tracks.size());
    m_tracks.append(t);
    endInsertRows();
    emit countChanged();
}

void MusicLibraryModel::insertTrack(int index, const MusicTrack & track)
{
    if (index < 0 || index > m_tracks.size())
        return;
    MusicTrack t = track;
    if (t.coverUrl.isEmpty() && !t.filePath.isEmpty())
    {
        t.coverUrl = CoverManager::instance().getCoverUrl(t.filePath);
    }
    beginInsertRows(QModelIndex(), index, index);
    m_tracks.insert(index, t);
    endInsertRows();
    emit countChanged();
}

void MusicLibraryModel::addTrackFromLibrary(MusicLibraryModel* source, int sourceIndex)
{
    if (!source || sourceIndex < 0 || sourceIndex >= source->count())
        return;
    const MusicTrack track = source->trackAt(sourceIndex);
    if (containsFilePath(track.filePath))
        return;
    appendTrack(track);
}

void MusicLibraryModel::removeTrack(int index)
{
    if (index < 0 || index >= m_tracks.size())
        return;
    beginRemoveRows(QModelIndex(), index, index);
    m_tracks.removeAt(index);
    endRemoveRows();
    emit countChanged();
}

bool MusicLibraryModel::moveTrack(int from, int to)
{
    if (from < 0 || from >= m_tracks.size() || to < 0 || to >= m_tracks.size() || from == to)
        return false;

    int destinationChild = (to > from) ? (to + 1) : to;
    if (!beginMoveRows(QModelIndex(), from, from, QModelIndex(), destinationChild))
        return false;

    m_tracks.move(from, to);
    endMoveRows();
    return true;
}

bool MusicLibraryModel::containsFilePath(const QString & filePath) const
{
    return indexOfFilePath(filePath) != -1;
}

int MusicLibraryModel::indexOfFilePath(const QString & filePath) const
{
    for (int i = 0; i < m_tracks.size(); ++i) {
        if (m_tracks[i].filePath == filePath)
            return i;
    }
    return -1;
}

QStringList MusicLibraryModel::allFilePaths() const
{
    QStringList list;
    for (const auto & t : m_tracks) {
        list.append(t.filePath);
    }
    return list;
}

void MusicLibraryModel::clear()
{
    beginResetModel();
    m_tracks.clear();
    endResetModel();
    emit countChanged();
}

void MusicLibraryModel::searchFromModel(MusicLibraryModel * sourceModel, const QString & keyword)
{
    beginResetModel();
    m_tracks.clear();

    QString trimmed = keyword.trimmed();
    if (sourceModel && !trimmed.isEmpty()) {
        for (int i = 0; i < sourceModel->rowCount(); ++i) {
            MusicTrack t = sourceModel->trackAt(i);
            if (t.title.contains(trimmed, Qt::CaseInsensitive) ||
                t.artist.contains(trimmed, Qt::CaseInsensitive) ||
                t.album.contains(trimmed, Qt::CaseInsensitive)) {
                if (m_favoriteManager) {
                    t.favorite = m_favoriteManager->isFavorite(t.filePath);
                }
                m_tracks.append(t);
            }
        }
    }

    endResetModel();
    emit countChanged();
}
