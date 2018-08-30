# -*- coding: utf-8 -*-
import json

import xbmc
import xbmcvfs
import xbmcaddon

from time import time

from Lib.Common import (
    getWindowProperty,
    setWindowProperty,
    setRawWindowProperty,
    testWindowProperty,
    clearWindowProperty
)


# Simple JSON and window property dictionary cache.

class SimpleCache():

    CACHE_PATH_DIR = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')).decode('utf-8')
    CACHE_FILENAME = 'cache.json'

    PROPERTY_CACHE = 'simplecache.cache' # JSON object for the cache, or nothing.

    # '1' if items were added to the memory cache and it should be saved to disk.
    # Otherwise clear.
    PROPERTY_CACHE_FILE_DIRTY = 'simplecache.dirty'

    # '1' if there's data in memory to fill the Python cache object.
    # Otherwise clear.
    # This memory is stored in the PROPERTY_CACHE property.
    PROPERTY_CACHE_MEMORY = 'simplecache.memory'

    # '1' if the Python object has new items that should be stored in memory.
    # Otherwise cleared.
    # Used at the end of long loops of adding items, so the flushing is only done once
    # instead of each time a new item is added.
    PROPERTY_CACHE_MEMORY_FLUSH = 'simplecache.memoryFlush'


    def __init__(self):
        self.cache = None


    def isCacheLoaded(self):
        # Test if there's a valid Python object and also if there's data in
        # memory that can be used to fill this object.
        # In Kodi <= 17.6 the object is reset at every directory change, but
        # the memory data persists.
        return self.cache and testWindowProperty(self.PROPERTY_CACHE_MEMORY)


    def ensureCacheLoaded(self):
        if not self.isCacheLoaded():
            # Try to load the cache from memory first.
            if not self.getMemoryCache():
                self.getFileCache()


    def getMemoryCache(self):
        self.cache = getWindowProperty(self.PROPERTY_CACHE)
        if self.cache:
            setRawWindowProperty(self.PROPERTY_CACHE_MEMORY, '1')
            clearWindowProperty(self.PROPERTY_CACHE_MEMORY_FLUSH)
            return True
        else:
            clearWindowProperty(self.PROPERTY_CACHE_MEMORY)
            return False


    def getFileCache(self):
        # Try to load or create the cache file.
        fullPath = self.CACHE_PATH_DIR + self.CACHE_FILENAME
        if xbmcvfs.exists(fullPath):
            file = xbmcvfs.File(fullPath)
            try:
                self.cache = json.loads(file.read())
                clearWindowProperty(self.PROPERTY_CACHE_FILE_DIRTY)
            except:
                # Error. Notification with no sound.
                from xbmcgui import Dialog, NOTIFICATION_INFO
                dialog = Dialog()
                dialog.notification('Cache', 'Could not read cache file', NOTIFICATION_INFO, 2500, False)
                self.cache = self.blankCache()
            finally:
                file.close()
        else:
            # Initialize a blank cache file.
            self.cache = self.blankCache()
            self._saveCache()
        # Store whatever is in the cache object into the persistent memory property.
        self.flushCacheToMemory(force = True)


    def getCacheItem(self, key):
        return self.cache.get(key, None)


    def addCacheItem(self, key, data):
        self.cache[key] = data
        setRawWindowProperty(self.PROPERTY_CACHE_FILE_DIRTY, '1') # Cache should be saved to a file and stored.
        setRawWindowProperty(self.PROPERTY_CACHE_MEMORY_FLUSH, '1') # in the persistent memory property as well.


    def flushCacheToMemory(self, force = False):
        if force or testWindowProperty(self.PROPERTY_CACHE_MEMORY_FLUSH):
            setWindowProperty(self.PROPERTY_CACHE, self.cache)
            setRawWindowProperty(self.PROPERTY_CACHE_MEMORY, '1')
            clearWindowProperty(self.PROPERTY_CACHE_MEMORY_FLUSH)


    def saveCacheIfDirty(self):
        if testWindowProperty(self.PROPERTY_CACHE_FILE_DIRTY):
            try:
                self._saveCache()
            finally:
                clearWindowProperty(self.PROPERTY_CACHE_FILE_DIRTY)


    def _saveCache(self):
            fullPath = self.CACHE_PATH_DIR + self.CACHE_FILENAME

            if not xbmcvfs.exists(fullPath):
                xbmcvfs.mkdir(self.CACHE_PATH_DIR)
            if not self.cache:
                self.getMemoryCache()

            file=xbmcvfs.File(fullPath, 'w')
            file.write(json.dumps(self.cache))
            file.close()


    def blankCache(self):
        return {'_': None} # Dummy value to initialise the JSON object.


cache = SimpleCache()
