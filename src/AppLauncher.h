#pragma once

#include <QtCore/qglobal.h>

#if defined(FLUENT_CORE_LIBRARY)
#  define FLUENT_CORE_EXPORT Q_DECL_EXPORT
#else
#  define FLUENT_CORE_EXPORT Q_DECL_IMPORT
#endif

extern "C" FLUENT_CORE_EXPORT int runMusicPlayerApplication(int argc, char *argv[]);
