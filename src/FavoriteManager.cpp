#include "FavoriteManager.h"
#include "MusicLibraryModel.h"
#include "AppConfig.h"
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QSettings>
#include <QDebug>

FavoriteManager::FavoriteManager(QObject * parent) : QObject(parent),m_model(new MusicLibraryModel(this))
{
    m_model->setFavoriteManager(this);
    connect(m_model,&MusicLibraryModel::countChanged,this,&FavoriteManager::countChanged);
    loadFavorites();
}

MusicLibraryModel * FavoriteManager::model() const
{
    return m_model;
}

int FavoriteManager::count() const
{
    return m_model ? m_model->count() : 0;
}

QString FavoriteManager::getIniPath() const
{
    return AppConfig::instance().favoritesIniPath();
}

bool FavoriteManager::isFavorite(const QString & filePath) const
{
    if(filePath.isEmpty())
        return false;
    return m_favoritePaths.contains(filePath);
}

void FavoriteManager::toggleFavoriteTrack(const MusicTrack & track)
{
    if(track.filePath.isEmpty())
        return;
    bool current = isFavorite(track.filePath);
    setTrackFavorite(track,!current);
}

void FavoriteManager::setTrackFavorite(const MusicTrack & track,bool favorite)
{
    if(track.filePath.isEmpty())
        return;

    if(favorite)
    {
        int existingIndex = m_model->indexOfFilePath(track.filePath);
        if(existingIndex == 0)
        {
            m_favoritePaths.insert(track.filePath);
            saveFavorites();
            syncFavoriteToModels(track.filePath,true);
            emit favoriteChanged(track.filePath,true);
            return;
        }

        if(existingIndex > 0)
        {
            //在列表中移动到首位
            m_model->moveTrack(existingIndex,0);
            m_model->setTrackFavorite(0,true);
        }
        else
        {
            //新加入喜欢列表的歌曲 序号为1
            MusicTrack favTrack = track;
            favTrack.favorite = true;
            m_model->insertTrack(0,favTrack);
        }
        m_favoritePaths.insert(track.filePath);

        //限制最多保留500首歌曲
        while(m_model->count() > 500)
        {
            int lastIdx = m_model->count() - 1;
            QString removedPath = m_model->trackAt(lastIdx).filePath;
            m_model->removeTrack(lastIdx);
            m_favoritePaths.remove(removedPath);
            syncFavoriteToModels(removedPath,false);
            emit favoriteChanged(removedPath,false);
        }

        saveFavorites();
        syncFavoriteToModels(track.filePath,true);
        emit favoriteChanged(track.filePath,true);
        emit countChanged();
    }
    else
    {
        //取消喜欢 从喜欢列表移除
        int existingIndex = m_model->indexOfFilePath(track.filePath);
        if(existingIndex >= 0)
        {
            m_model->removeTrack(existingIndex);
        }
        m_favoritePaths.remove(track.filePath);
        saveFavorites();
        syncFavoriteToModels(track.filePath,false);
        emit favoriteChanged(track.filePath,false);
        emit countChanged();
    }
}

void FavoriteManager::syncFavoriteToModels(const QString & filePath,bool isFavorite)
{
    for(MusicLibraryModel * model : m_registeredModels)
    {
        if(model && model != m_model)
        {
            model->setFavoriteByFilePath(filePath,isFavorite);
        }
    }
}

void FavoriteManager::registerModel(MusicLibraryModel * model)
{
    if(!model || m_registeredModels.contains(model))
        return;
    m_registeredModels.append(model);
    model->setFavoriteManager(this);
    applyToModel(model);
    connect(model,&QObject::destroyed,this,[this,model](){
        m_registeredModels.removeAll(model);
    });
}

void FavoriteManager::unregisterModel(MusicLibraryModel * model)
{
    m_registeredModels.removeAll(model);
}

void FavoriteManager::applyToModel(MusicLibraryModel * model)
{
    if(!model)
        return;

    for(int i = 0 ;i< model->count(); ++i)
    {
        MusicTrack t = model->trackAt(i);
        bool fav = m_favoritePaths.contains(t.filePath);
        if(t.favorite != fav)
        {
            model->setTrackFavorite(i,fav);
        }
    }
}

void FavoriteManager::loadFavorites()
{
    QString path = getIniPath();
    if(!QFile::exists(path))
    {
        saveFavorites();        //文件不存在生成空文件
        return;
    }
    QSettings settings(path,QSettings::IniFormat);
    int size = settings.beginReadArray(QStringLiteral("favorites"));
    m_favoritePaths.clear();
    m_model->clear();

    for(int i = 0; i< size && i < 500 ; ++i)
    {
        settings.setArrayIndex(i);
        QString filePath = settings.value(QStringLiteral("filePath")).toString();
        if(filePath.trimmed().isEmpty())
            continue;

        QString resolvedPath = AppConfig::instance().resolvePath(filePath);
        if (!QFileInfo::exists(resolvedPath)) {
            if (!QFileInfo::exists(filePath))
                continue;
            resolvedPath = filePath;
        }

        MusicTrack track;
        track.filePath = resolvedPath;
        track.title = settings.value(QStringLiteral("title")).toString();
        track.artist = settings.value(QStringLiteral("artist")).toString();
        track.album = settings.value(QStringLiteral("album")).toString();
        track.duration = settings.value(QStringLiteral("duration")).toLongLong();
        track.favorite = true;

        m_model->appendTrack(track);
        m_favoritePaths.insert(resolvedPath);
    }
    settings.endArray();
    qDebug() << "加载我喜欢的音乐完成,共" << m_model->count() << "首";
    emit countChanged();
}

void FavoriteManager::saveFavorites()
{
    QString path = getIniPath();
    QSettings settings(path,QSettings::IniFormat);
    settings.clear();
    QString projRoot = AppConfig::instance().projectRoot();
    QDir rootDir(projRoot);

    settings.beginWriteArray(QStringLiteral("favorites"),m_model->count());
    for(int i = 0; i < m_model->count(); ++i)
    {
        settings.setArrayIndex(i);
        const MusicTrack track = m_model->trackAt(i);
        QString rel = rootDir.relativeFilePath(track.filePath);
        if (!rel.startsWith(QStringLiteral("..")) && !QDir::isAbsolutePath(rel)) {
            settings.setValue(QStringLiteral("filePath"), rel);
        } else {
            settings.setValue(QStringLiteral("filePath"), track.filePath);
        }
        settings.setValue(QStringLiteral("title"),track.title);
        settings.setValue(QStringLiteral("artist"),track.artist);
        settings.setValue(QStringLiteral("album"),track.album);
        settings.setValue(QStringLiteral("duration"),track.duration);
        settings.setValue(QStringLiteral("favorite"),true);
    }
    settings.endArray();
    settings.sync();
}