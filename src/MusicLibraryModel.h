#pragma once

#include <QAbstractListModel>
#include <QVector>

#include "MusicTrack.h"

class FavoriteManager;

class MusicLibraryModel : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(int count READ count NOTIFY countChanged)

public:
    enum Roles {
        FilePathRole = Qt::UserRole + 1,
        TitleRole,
        ArtistRole,
        AlbumRole,
        DurationRole,
        FavoriteRole,
        LastPlayedRole,
        CoverUrlRole
    };

    Q_ENUM(Roles)

    explicit MusicLibraryModel (QObject * parent = nullptr);
    int rowCount(const QModelIndex & parent = QModelIndex()) const override;
    QVariant data(const QModelIndex & index, int role) const override;
    QHash<int,QByteArray> roleNames() const override;
    int count() const;

    //扫描一个音乐目录
    Q_INVOKABLE void scanDirectory(const QString & directory);
    //追加扫描一个音乐目录 (增量去重加入)
    Q_INVOKABLE void appendDirectory(const QString & directory);
    //可以在指定目录中随机抽取固定数量歌曲的接口
    Q_INVOKABLE void scanRandomDirectory(const QString & directory, int count = 42);
    //喜欢/取消喜欢
    Q_INVOKABLE void toggleFavorite(int index);
    //获取歌曲
    MusicTrack trackAt(int index) const;
    //QMediaPlayer读取元数据后更新Model
    void updateMetadata(int index,const QString &title,const QString &artist,const QString &album,qint64 duration);
    //标记最近播放
    void markPlayed(int index);
    void setLyrics(int index,const QVector<LyricLine> &lyrics);

    void setFavoriteManager(FavoriteManager * manager);
    FavoriteManager * favoriteManager() const;
    void setTrackFavorite(int index,bool favorite);
    void setFavoriteByFilePath(const QString & filePath, bool isFavorite);

    // 歌单动态增删歌曲
    void appendTrack(const MusicTrack & track);
    void insertTrack(int index, const MusicTrack & track);
    Q_INVOKABLE void addTrackFromLibrary(MusicLibraryModel* source, int sourceIndex);
    Q_INVOKABLE void removeTrack(int index);
    Q_INVOKABLE bool moveTrack(int from, int to);
    Q_INVOKABLE bool containsFilePath(const QString & filePath) const;
    Q_INVOKABLE int indexOfFilePath(const QString & filePath) const;
    QStringList allFilePaths() const;
    Q_INVOKABLE void clear();
    Q_INVOKABLE void searchFromModel(MusicLibraryModel * sourceModel, const QString & keyword);

signals:
    void countChanged();

private:
    QVector<MusicTrack> m_tracks;
    FavoriteManager * m_favoriteManager = nullptr;
};
