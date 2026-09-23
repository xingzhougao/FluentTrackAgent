#include "PlayerController.h"
#include "RecentManager.h"
#include "FavoriteManager.h"

#include <QMediaMetaData>
#include <QRandomGenerator>
#include <QUrl>
#include <QtGlobal>
#include <QDebug>
#include <QFile>
#include <QFileInfo>
#include <QTextStream>
#include <QRegularExpression>
#include <algorithm>

PlayerController::PlayerController(MusicLibraryModel * library,QObject * parent): QObject(parent),m_player(new QMediaPlayer(this)),m_audioOutput(new QAudioOutput(this))
{
    m_player->setAudioOutput(m_audioOutput);        //设置音频播放器
    m_audioOutput->setVolume(0.7);                  //设置音量
    //播放位置改变
    connect(m_player,&QMediaPlayer::positionChanged,this,[this](qint64 position){
        emit positionChanged();
        emit progressChanged();
        //根据当前播放未知更新歌词
        updateCurrentLyric(position);
    });
    //音乐总长度改变
    connect(m_player,&QMediaPlayer::durationChanged,this,[this](qint64){
        emit durationChanged();
        emit progressChanged();
        readMetaData();
    });
    //播放/暂停状态改变
    connect(m_player,&QMediaPlayer::playbackStateChanged,this,[this](QMediaPlayer::PlaybackState){
        emit playingChanged();
    });
    //MP3元数据读取完成/发生变化s
    connect(m_player,&QMediaPlayer::metaDataChanged,this,&PlayerController::readMetaData);
    //播放状态
    connect(m_player,&QMediaPlayer::mediaStatusChanged,this,[this](QMediaPlayer::MediaStatus status){
        if(status == QMediaPlayer::EndOfMedia)
        {
            handleEndOfMedia();
        }
    });
    //播放错误
    connect(m_player,&QMediaPlayer::errorOccurred,this,[this](QMediaPlayer::Error,const QString &errorString){
        emit playbackError(errorString);
    });
    //音量变化
    connect(m_audioOutput,&QAudioOutput::volumeChanged,this,[this](float){
        emit volumeChanged();
    });
    //静音变化
    connect(m_audioOutput,&QAudioOutput::mutedChanged,this,[this](bool){
        emit mutedChanged();
    });
    //MusicLibraryModel 当前歌曲数据变化 PlayerController的title / artist属性也需要通知QML更新
    setLibrary(library);
    if(m_library && m_library->count() > 0)
        selectTrack(0,false);
}

QString PlayerController::title() const
{
    if(m_library && m_index >= 0 && m_index < m_library->count())
        return m_library->trackAt(m_index).title;

    return m_currentTrack.title;
}

QString PlayerController::artist() const
{
    if(m_library && m_index >= 0 && m_index < m_library->count())
        return m_library->trackAt(m_index).artist;

    return m_currentTrack.artist;
}

QString PlayerController::album() const
{
    if(m_library && m_index >= 0 && m_index < m_library->count())
        return m_library->trackAt(m_index).album;

    return m_currentTrack.album;
}

QString PlayerController::coverUrl() const
{
    if(m_library && m_index >= 0 && m_index < m_library->count())
        return m_library->trackAt(m_index).coverUrl;

    return m_currentTrack.coverUrl;
}

//当前是否正在播放
bool PlayerController::playing() const
{
    return m_player->playbackState() == QMediaPlayer::PlayingState;
}

//当前播放进度 返回方位0.0-1.0 给PlayerBar.qml的 Slider使用
double PlayerController::progress() const
{
    const qint64 totalDuration = m_player->duration();
    if(totalDuration <= 0)
        return 0.0;

    return static_cast<double>(m_player->position()) / static_cast<double>(totalDuration);
}

//当前音量 QAudioOutput 本身就是处于0.0 - 1.0
double PlayerController::volume() const
{
    return m_audioOutput->volume();
}

//当前播放位置 单位毫秒
qint64 PlayerController::position() const
{
    return m_player->position();
}

//当前歌曲总时长 单位毫秒
qint64 PlayerController::duration() const
{
    return m_player->duration();
}

//是否静音
bool PlayerController::muted() const
{
    return m_audioOutput->isMuted();
}

//当前播放模式 0 顺序播放 1随机播放 2单曲循环
int PlayerController::playMode() const
{
    return m_playMode;
}

//当前歌曲索引
int PlayerController::currentIndex() const{
    return m_index;
}

//播放/暂停
void PlayerController::togglePlay()
{
    if(!m_library || m_library->count() <= 0)
        return;

    //当前还没有选择歌曲 默认选择第一首
    if(m_index < 0)
    {
        selectTrack(0);
        return;
    }

    if(playing())
    {
        m_player->pause();
    }else{
        m_player->play();
    }
}

//停止播放并重置播放状态
void PlayerController::stop()
{
    m_player->stop();
    m_player->setSource(QUrl());
    m_index = -1;
    m_currentLyric.clear();
    m_currentLyricIndex = -1;
    m_lyricList.clear();
    emit currentIndexChanged();
    emit trackChanged();
    emit positionChanged();
    emit durationChanged();
    emit progressChanged();
    emit currentLyricChanged();
    emit currentLyricIndexChanged();
    emit lyricListChanged();
    emit favoriteChanged();
}

//上一首
void PlayerController::previous()
{
    if(!m_library || m_library->count() <=0)
        return;
    const int count = m_library->count();

    //当前还没有歌曲
    if(m_index < 0)
    {
        selectTrack(0);
        return;
    }

    const int newIndex = (m_index - 1 + count) % count;
    selectTrack(newIndex);
}

//下一首
void PlayerController::next()
{
    if(!m_library || m_library->count() <= 0)
        return;
    const int count = m_library->count();
    if(m_index < 0)
    {
        selectTrack(0);
        return;
    }
    //随机播放
    if(m_playMode == 1 && count > 1)
    {
        int newIndex = m_index;
        //保证随机出来的不是当前歌曲
        while(newIndex == m_index)
        {
            newIndex = QRandomGenerator::global()->bounded(count);
        }
        selectTrack(newIndex);
        return;
    }
    //顺序一下首 这里即使当前是单曲循环 用户点击下一首仍然切换到下一首 单曲循环只影响歌曲"自然播放速度"
    const int newIndex = (m_index + 1) % count;
    selectTrack(newIndex);
}

//重复播放当前歌曲
void PlayerController::restart()
{
    if(m_index < 0)
        return;
    m_player->setPosition(0);
    m_player->play();
}

//选择歌曲 index就是MusicLibraryModel中的行号
void PlayerController::selectTrack(int index,bool autoplay)
{
    if(!m_library)
        return;

    if(index < 0 || index >= m_library->count())
    {
        return;
    }

    const MusicTrack track = m_library->trackAt(index);
    if(track.filePath.isEmpty())
        return;

    m_isChangingTrack = true;
    m_currentTrack = track;

    //修改当前歌曲索引
    if(m_index != index)
    {
        m_index = index;
        emit currentIndexChanged();
    }
    //提前通知QML 即使MP3元数据还没读取出来 MusicLibraryModel当前已经有 文件名 未知歌手 所以PlayerBar可以立即显示
    emit trackChanged();
    emit favoriteChanged();
    //读取这首歌曲对应的歌词
    loadLyrics(index);
    //设置真实音乐文件
    m_player->setSource(QUrl::fromLocalFile(track.filePath));
    if(autoplay)
    {
        //标记最近播放并开始播放
        m_library->markPlayed(index);
        if(m_recentManager)
        {
            m_recentManager->recordTrack(track);
        }
        m_player->play();
    }
    m_isChangingTrack = false;
}

//设置播放进度 QML Slider
void PlayerController::setProgress(double value)
{
    const qint64 totalDuration = m_player->duration();
    if(totalDuration <= 0)
        return;
    value = qBound(0.0,value,1.0);
    const qint64 newPosition = static_cast<qint64>(value * totalDuration);
    m_player->setPosition(newPosition);
}

//设置音量 0-1
void PlayerController::setVolume(double value)
{
    value = qBound(0.0,value,1.0);
    m_audioOutput->setVolume(static_cast<float>(value));
}

//设置静音
void PlayerController::setMuted(bool muted)
{
    m_audioOutput->setMuted(muted);
}

//设置播放模式 0 顺序 1随机 2单曲循环
void PlayerController::setPlayMode(int mode)
{
    mode = qBound(0,mode,2);
    if(m_playMode == mode)
        return;
    m_playMode = mode;
    emit playModeChanged();
}

// 辅助判定字符串是否为乱码（包含 Unicode 替换字符 \uFFFD 或非法不可见控制字符）
static bool isGarbledString(const QString &str)
{
    if (str.isEmpty())
        return false;
    if (str.contains(QChar(0xFFFD)) || str.contains(QChar(0xFFFE)))
        return true;
    for (const QChar &ch : str) {
        if (ch.isLowSurrogate() || ch.isHighSurrogate())
            continue;
        ushort u = ch.unicode();
        if (u < 0x20 && u != '\t' && u != '\n' && u != '\r')
            return true;
    }
    return false;
}

//读取MP3元数据 MP3->QMediaMetaData->MusicLibraryModel
void PlayerController::readMetaData()
{
    if(!m_library)
        return;

    if(m_index < 0 || m_index >= m_library->count())
        return;

    const QMediaMetaData metaData = m_player->metaData();
    MusicTrack currentExisting = m_library->trackAt(m_index);

    QString title = metaData.stringValue(QMediaMetaData::Title).trimmed();
    QString artist = metaData.stringValue(QMediaMetaData::ContributingArtist).trimmed();
    if(artist.isEmpty())
        artist = metaData.stringValue(QMediaMetaData::Author).trimmed();
    QString album = metaData.stringValue(QMediaMetaData::AlbumTitle).trimmed();
    qint64 musicDuration = m_player->duration();
    if(musicDuration <= 0)
        musicDuration = metaData.value(QMediaMetaData::Duration).toLongLong();

    // 乱码安全防护：若 QMediaPlayer 解码出的元数据包含乱码或替换符（常见于老式 GBK 编码音频），严禁覆盖有效数据
    if (isGarbledString(title)) {
        title = currentExisting.title;
    }
    if (isGarbledString(artist)) {
        artist = currentExisting.artist;
    }
    if (isGarbledString(album)) {
        album = currentExisting.album;
    }

    if (title.isEmpty()) title = currentExisting.title;
    if (artist.isEmpty()) artist = currentExisting.artist;
    if (album.isEmpty()) album = currentExisting.album;
    if (musicDuration <= 0) musicDuration = currentExisting.duration;

    //更新MusicLibraryModel
    m_library->updateMetadata(m_index,title,artist,album,musicDuration);
    m_currentTrack.title = title;
    m_currentTrack.artist = artist;
    m_currentTrack.album = album;
    if (musicDuration > 0) m_currentTrack.duration = musicDuration;
}

//当前歌曲自然播放结束
void PlayerController::handleEndOfMedia()
{
    if(m_isChangingTrack)
        return;

    if(!m_library || m_library->count() <= 0)
        return;

    // 只有当播放器真的播放到接近文件末尾时才算自然播放结束（避免setSource刷新媒体误报）
    qint64 dur = m_player->duration();
    qint64 pos = m_player->position();
    if(dur > 0 && pos < dur - 2000)
    {
        return;
    }

    //单曲循环
    if(m_playMode == 2)
    {
        m_player->setPosition(0);
        m_player->play();
        return;
    }
    //随机和顺序播放已在next()函数处理
    next();
}

QString PlayerController::formatTime(qint64 milliseconds) const
{
    if(milliseconds < 0)
        milliseconds = 0;

    const qint64 totalSeconds = milliseconds / 1000;  //毫秒->秒
    const qint64 hours = totalSeconds / 3600;
    const qint64 minutes = (totalSeconds % 3600) / 60;
    const qint64 seconds = totalSeconds % 60;
    if(hours > 0)
        return QStringLiteral("%1:%2:%3").arg(hours).arg(minutes,2,10,QLatin1Char('0')).arg(seconds,2,10,QLatin1Char('0'));
    return QStringLiteral("%1:%2").arg(minutes,2,10,QLatin1Char('0')).arg(seconds,2,10,QLatin1Char('0'));       //arg(数值,最小宽度,进制，补齐字符)
}

void PlayerController::playIndex(int index)
{
    selectTrack(index,true);
}

bool PlayerController::favorite() const
{
    if(m_favoriteManager)
    {
        if(m_library && m_index >= 0 && m_index < m_library->count())
            return m_favoriteManager->isFavorite(m_library->trackAt(m_index).filePath);

        if(!m_currentTrack.filePath.isEmpty())
            return m_favoriteManager->isFavorite(m_currentTrack.filePath);

        return false;
    }

    if(m_library && m_index >= 0 && m_index < m_library->count())
        return m_library->trackAt(m_index).favorite;

    return m_currentTrack.favorite;
}

void PlayerController::toggleFavorite()
{
    if(m_favoriteManager)
    {
        if(m_library && m_index >= 0 && m_index < m_library->count())
        {
            m_favoriteManager->toggleFavoriteTrack(m_library->trackAt(m_index));
        }
        else if(!m_currentTrack.filePath.isEmpty())
        {
            m_favoriteManager->toggleFavoriteTrack(m_currentTrack);
            m_currentTrack.favorite = m_favoriteManager->isFavorite(m_currentTrack.filePath);
            emit favoriteChanged();
        }
        return;
    }

    if(!m_library)
        return;

    if(m_index < 0 || m_index >= m_library->count())
        return;

    m_library->toggleFavorite(m_index);
    emit favoriteChanged();
}

QVariantList  PlayerController::lyricList() const
{
    return m_lyricList;
}

int PlayerController::currentLyricIndex() const
{
    return m_currentLyricIndex;
}

QString PlayerController::currentLyric() const
{
    return m_currentLyric;
}

void PlayerController::seek(qint64 milliseconds)
{
    const qint64 totalDuration = m_player->duration();
    if(totalDuration > 0)
        milliseconds = qBound<qint64>(0,milliseconds,totalDuration);
    else
        milliseconds = qMax<qint64>(0,milliseconds);
    m_player->setPosition(milliseconds);
    updateCurrentLyric(milliseconds);
}

void PlayerController::seekToLyric(int index)
{
    QVector<LyricLine> lyrics;
    if(m_library && m_index >= 0 && m_index < m_library->count())
    {
        lyrics = m_library->trackAt(m_index).lyrics;
    }
    else
    {
        lyrics = m_currentTrack.lyrics;
    }

    if(index >= 0 && index < lyrics.size())
    {
        qint64 targetTime = lyrics[index].timeMs;
        m_player->setPosition(targetTime);
        m_currentLyricIndex = index;
        m_currentLyric = lyrics[index].text;
        emit currentLyricIndexChanged();
        emit currentLyricChanged();
        if(m_player->playbackState() != QMediaPlayer::PlayingState)
        {
            m_player->play();
        }
    }
}

void PlayerController::loadLyrics(int index)
{
    if(!m_library)
        return;
    if(index < 0 || index >= m_library->count())
        return;

    const MusicTrack track = m_library->trackAt(index);

    QVector<LyricLine> lyrics;
    //切歌时先把当前歌词清掉
    m_currentLyric.clear();
    m_currentLyricIndex = -1;
    m_lyricList.clear();
    emit currentLyricChanged();
    emit currentLyricIndexChanged();
    emit lyricListChanged();

    QFileInfo musicInfo(track.filePath);
    const QString lrcPath = musicInfo.absolutePath() + "/" + musicInfo.completeBaseName() + ".lrc";
    qDebug() <<"歌词文件:"<<lrcPath;
    QFile file(lrcPath);
    if(!file.open(QIODevice::ReadOnly | QIODevice::Text))
    {
        qDebug() << "没有找到歌词:" <<lrcPath;
        m_currentLyric = QStringLiteral("暂无歌词");
        emit currentLyricChanged();

        //当前歌曲歌词设置为空
        m_library->setLyrics(index,{});
        return;
    }

    QTextStream stream(&file);
    QRegularExpression regex(R"(\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\])");
    while(!stream.atEnd())
    {
        const QString line = stream.readLine();
        QRegularExpressionMatchIterator iterator = regex.globalMatch(line);
        QString lyricText = line;
        //将[00:12.30]去掉
        lyricText.remove(regex);
        lyricText = lyricText.trimmed();
        if(lyricText.isEmpty())
            continue;
        while(iterator.hasNext())
        {
            const QRegularExpressionMatch match = iterator.next();
            const int minutes = match.captured(1).toInt();
            const int seconds = match.captured(2).toInt();
            const QString fraction = match.captured(3);
            int milliseconds = 0;
            if(fraction.length() == 1)
            {
                milliseconds =
                    fraction.toInt() * 100;
            }
            else if(fraction.length() == 2)
            {
                milliseconds =
                    fraction.toInt() * 10;
            }
            else if(fraction.length() == 3)
            {
                milliseconds =
                    fraction.toInt();
            }
            const qint64 timeMs = minutes * 60 * 1000 + seconds * 1000 + milliseconds;
            lyrics.append({timeMs,lyricText});
        }
    }
    std::sort(lyrics.begin(),lyrics.end(),[](const LyricLine & a,const LyricLine &b){
        return a.timeMs < b.timeMs;
    });
    //保存到MusicTrack
    m_library->setLyrics(index,lyrics);

    m_lyricList.clear();
    m_lyricList.reserve(lyrics.size());
    for(const auto &line : lyrics)
    {
        QVariantMap map;
        map.insert(QStringLiteral("time"),line.timeMs);
        map.insert(QStringLiteral("text"),line.text);
        m_lyricList.append(map);
    }
    emit lyricListChanged();

    qDebug()<<"歌词加载完成,共"<<lyrics.size()<<"句";
}

void PlayerController::updateCurrentLyric(qint64 position)
{
    if(!m_library)
        return;
    if(m_index < 0 || m_index >= m_library->count())
        return;

    const MusicTrack track = m_library->trackAt(m_index);
    if(track.lyrics.isEmpty())
    {
        if(m_currentLyricIndex != -1)
        {
            m_currentLyricIndex = -1;
            emit currentLyricIndexChanged();
        }
        return;
    }

    int activeIndex = -1;
    QString lyric;
    for(int i = track.lyrics.size() - 1;i >= 0;--i)
    {
        if(position >= track.lyrics[i].timeMs)
        {
            lyric = track.lyrics[i].text;
            activeIndex = i;
            break;
        }
    }

    if(m_currentLyricIndex != activeIndex)
    {
        m_currentLyricIndex = activeIndex;
        emit currentLyricIndexChanged();
    }

    if(lyric == m_currentLyric)
        return;
    m_currentLyric = lyric;
    emit currentLyricChanged();
}

MusicLibraryModel * PlayerController::currentLibrary() const
{
    return m_library.data();
}

void PlayerController::setLibrary(MusicLibraryModel * library)
{
    if(m_library == library)
        return;

    if(m_library)
    {
        //解绑旧模型信号连接
        disconnect(m_library,nullptr,this,nullptr);
    }

    m_library = library;
    if(m_library)
    {
        //监听新模型的数据变化 例如点赞 通知QML界面与playbar刷新
        connect(m_library,&MusicLibraryModel::dataChanged,this,[this](const QModelIndex & topLeft,const QModelIndex & bottomRight,const QList<int> &){
            if(m_index < 0)
                return;
            if(m_index >= topLeft.row() && m_index <= bottomRight.row())
            {
                emit trackChanged();
                emit favoriteChanged();
            }
        });

        //监听新模型删除行：如果删除的是当前正在播放的歌曲，停止播放并重置；如果删除的是之前的歌曲，修正索引
        connect(m_library,&MusicLibraryModel::rowsAboutToBeRemoved,this,[this](const QModelIndex &, int first, int last){
            if(m_index >= first && m_index <= last)
            {
                m_player->stop();
                m_player->setSource(QUrl());
                m_index = -1;
                m_currentLyric.clear();
                m_currentLyricIndex = -1;
                m_lyricList.clear();
                emit currentIndexChanged();
                emit trackChanged();
                emit positionChanged();
                emit durationChanged();
                emit progressChanged();
                emit currentLyricChanged();
                emit currentLyricIndexChanged();
                emit lyricListChanged();
            }
            else if(m_index > last)
            {
                m_index -= (last - first + 1);
                emit currentIndexChanged();
            }
        });

        //监听模型移动行：调整当前播放歌曲的索引
        connect(m_library,&MusicLibraryModel::rowsMoved,this,[this](const QModelIndex &, int sourceStart, int sourceEnd, const QModelIndex &, int destinationRow){
            if (m_index < 0)
                return;
            if (m_index >= sourceStart && m_index <= sourceEnd)
            {
                int target = (destinationRow > sourceStart) ? (destinationRow - 1) : destinationRow;
                m_index = target;
                emit currentIndexChanged();
            }
            else if (sourceStart < m_index && destinationRow > m_index)
            {
                m_index--;
                emit currentIndexChanged();
            }
            else if (sourceStart > m_index && destinationRow <= m_index)
            {
                m_index++;
                emit currentIndexChanged();
            }
        });

        //监听新模型的重置
        connect(m_library,&MusicLibraryModel::modelReset,this,[this](){
            if(!m_currentTrack.filePath.isEmpty() && m_library)
            {
                int foundIndex = m_library->indexOfFilePath(m_currentTrack.filePath);
                if(foundIndex != -1)
                {
                    m_index = foundIndex;
                    emit currentIndexChanged();
                    return;
                }
            }

            if(m_player->playbackState() == QMediaPlayer::PlayingState ||
               m_player->playbackState() == QMediaPlayer::PausedState)
            {
                m_index = -1;
                emit currentIndexChanged();
                return;
            }

            m_player->stop();
            m_player->setSource(QUrl());
            m_index = -1;
            m_currentTrack = MusicTrack();
            m_currentLyric.clear();
            m_currentLyricIndex = -1;
            m_lyricList.clear();
            emit currentIndexChanged();
            emit trackChanged();
            emit positionChanged();
            emit durationChanged();
            emit progressChanged();
            emit currentLyricChanged();
            emit currentLyricIndexChanged();
            emit lyricListChanged();
        });

        //监听模型销毁：若正在播放的歌单被删除，安全停止播放并解除指针
        connect(m_library,&QObject::destroyed,this,[this](){
            m_player->stop();
            m_player->setSource(QUrl());
            m_library = nullptr;
            m_index = -1;
            m_currentLyric.clear();
            m_currentLyricIndex = -1;
            m_lyricList.clear();
            emit currentIndexChanged();
            emit trackChanged();
            emit positionChanged();
            emit durationChanged();
            emit progressChanged();
            emit currentLyricChanged();
            emit currentLyricIndexChanged();
            emit lyricListChanged();
            emit favoriteChanged();
            emit currentLibraryChanged();
        });
    }

    emit currentLibraryChanged();
}

void PlayerController::setRecentManager(RecentManager * manager)
{
    m_recentManager = manager;
}

void PlayerController::setFavoriteManager(FavoriteManager * manager)
{
    m_favoriteManager = manager;
    if(m_favoriteManager)
    {
        connect(m_favoriteManager,&FavoriteManager::favoriteChanged,this,[this](const QString & filePath, bool){
            if((m_library && m_index >= 0 && m_index < m_library->count() && m_library->trackAt(m_index).filePath == filePath) ||
               (!m_currentTrack.filePath.isEmpty() && m_currentTrack.filePath == filePath))
            {
                emit favoriteChanged();
            }
        });
    }
}

void PlayerController::playFromModel(MusicLibraryModel * library,int index)
{
    if(!library)
        return;
    if(m_library != library)
        setLibrary(library);
    selectTrack(index,true);
}