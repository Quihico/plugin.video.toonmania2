# -*- coding: utf-8 -*-
import json
from time import time

import xbmc
import xbmcvfs
from xbmcgui import getCurrentWindowId, Window
import xbmcaddon


# A simple JSON and window property cache, specialized for XBMC video add-ons.

# Think of it like a way to save an add-on "session" onto disk. The intent is to make loading faster
# (loading from disk rather than web requests) and to spare the scraped sources from redundant requests.
# But also being economical with disk reads and writes, using as few as absolutely possible.

class SimpleCache():

    CACHE_VERSION = '1' # Cache version, for future extension. Used with properties saved to disk.

    LIFETIME_THREE_DAYS = 72 # 3 days, in hours.
    LIFETIME_ONE_WEEK = 168 # 7 days.
    LIFETIME_FOREVER = 0 # Never expires (see _loadFilePropertes())
    
    CACHE_PATH_DIR = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')).decode('utf-8')
    CACHE_FILENAME = 'cache.json'

    # Property name pointing to a set of property names that lead to cached data.
    # A property is guaranteed to exist if its name is in this set.
    PROPERTY_CACHE_NAMES = 'scache.prop.names'

    # Property name pointing to a comma-separated list of flags.
    # This list is converted to a set when read and used for quick boolean-style testing.
    # Testing a flag means seeing if it's present in the set or not.
    PROPERTY_FLAGS = 'scache.prop.memory'

    # Flag name for testing if items were added to the memory cache so it should be saved to disk.
    # Otherwise clear.
    FLAG_CACHE_FILE_FLUSH = 'scache.flag.fileFlush'

    # Flag name for testing if the Python 'cacheNames' object has data not yet in its corresponding
    # window memory property, meaning it's necessary to flush it to that window property.
    # It's done this way to let the add-on set several properties and then flush just once, at the end.
    FLAG_CACHE_MEMORY_FLUSH = 'scache.flag.memoryFlush'


    def __init__(self):
        # Initialised at every directory change in Kodi <= 17.6
        self.cacheNames = None
        self.flags = None
        self.window = Window(getCurrentWindowId())
        #self.window.clearProperty(self.PROPERTY_CACHE_NAMES)


    def _ensureCacheLoaded(self):
        if not self.cacheNames:
            # Try to load the cache names from memory first, then from file.
            if not self._loadMemoryCache() and not self._loadFileCache():
                self.cacheNames = set()
                

    def _loadMemoryCache(self):
        cacheNamesRaw = self.window.getProperty(self.PROPERTY_CACHE_NAMES)
        if cacheNamesRaw:
            self.cacheNames = self._stringToSet(cacheNamesRaw)
            return True
        else:
            return False


    def _loadFileCacheHelper(self, fileData):
        '''
        Internal.
        Helper function that loads window properties from data in the cache file.
        '''
        self.cacheNames = set()        
        hasExpiredProps = False
        currentTime = self._getEpochHours()

        allData = json.loads(fileData) # 'allData' is a JSON list of SimpleCache property entries.
        for propEntry in allData:
            # Interpret the property based on the cache version used to write it, allowing
            # for branching like expecting a certain format depending on version etc.
            #propVersion = propEntry['version']
            propEpoch = propEntry['epoch']
            lifetime = propEntry['lifetime']

            # Enact property lifetime.
            elapsedHours = currentTime - propEpoch
            if abs(elapsedHours) <= lifetime:
                # Load the entry as a window memory property, similar to setCacheProperty().
                # No need to store the original cache version as it became the latest version now.
                propName = propEntry['propName']
                self.cacheNames.add(propName)
                self.window.setProperty(propName, json.dumps((propEntry['data'], True, lifetime, propEpoch)))
            else:
                # Ignore it.
                hasExpiredProps = True                
        self.flushCacheNames()

        # Any expired properties are ignored. Request an overwrite of the cache file so they can be erased.
        if hasExpiredProps:
            self.setFlag(self.FLAG_CACHE_FILE_FLUSH)
        else:
            self.clearFlag(self.FLAG_CACHE_FILE_FLUSH)
        self.flushFlags()


    def _loadFileCache(self):
        '''
        Tries to load the cache file if it exists, or creates a blank cache file if it there isn't one.
        '''
        fullPath = self.CACHE_PATH_DIR + self.CACHE_FILENAME
        if xbmcvfs.exists(fullPath):
            file = xbmcvfs.File(fullPath)
            try:
                # Try to load the iist of disk-saved properties.
                self._loadFileCacheHelper(file.read())
            except:
                # Error. Notification with no sound.
                from xbmcgui import Dialog, NOTIFICATION_INFO
                dialog = Dialog()
                dialog.notification('Cache', 'Could not read cache file', NOTIFICATION_INFO, 3000, False)
                self.cacheNames = set()
            finally:
                file.close()
                return self.cacheNames
        else:
            # Initialize a blank cache file.
            xbmcvfs.mkdir(self.CACHE_PATH_DIR)
            file = xbmcvfs.File(fullPath, 'w')
            file.write('[]')
            file.close()
            return False


    def testFlag(self, flag):
        '''
        Returns True if a persistent flag is set in memory, else False.
        '''
        self._ensureFlags()
        return flag in self.flags


    def setFlag(self, flag):
        '''
        Adds a flag to memory.
        Do not use comma characters in the flag name, they're used internally for separation.
        '''
        self._ensureFlags()
        self.flags.add(flag)


    def clearFlag(self, flag):
        '''
        Removes a flag from memory.
        '''
        self._ensureFlags()
        self.flags.discard(flag)


    def flushFlags(self):
        '''
        This needs to be used **every time** after setting one or more flags.
        This stores all flags from the 'self.flags' Python object into a XBMC window memory property.
        '''
        self.window.setProperty(self.PROPERTY_FLAGS, self._setToString(self.flags))


    def _ensureFlags(self):
        '''
        Internal.
        Loads a set() into the 'self.flags' Python object from the data in the XBMC window memory property.
        '''
        if not self.flags:
            self.flags = self._stringToSet(self.window.getProperty(self.PROPERTY_FLAGS))


    def setCacheProperty(self, propName, data, saveToDisk, lifetime=72):
        '''
        Creates a persistent XBMC window memory property.
        *** The caller is expected to call flushCacheNames() *** after it has finished
        adding one or more properties.
        :param propName: Name/Identifier the property should have, used to retrieve it later.
        :param data: Data to store in the property, needs to be JSON-serializable.
        :param saveToDisk: Boolean if this property should be saved to the JSON cache file on
        disk to be loaded on later sessions. Best used for big collections of web-requested data.
        :param lifetime: When saving to disk, 'lifetime' specifies how many hours since its
        creation that the property should exist on disk, before being erased. Defaults to 72
        hours = 3 days. Setting ZERO will make it last forever.
        '''
        self.window.setProperty(propName, json.dumps((data, saveToDisk, lifetime, self._getEpochHours())))
        
        if saveToDisk:
            self._ensureCacheLoaded()
            self.cacheNames.add(propName)
            self.setFlag(self.FLAG_CACHE_FILE_FLUSH) # Used by saveCacheIfDirty().
            self.flushFlags()


    def flushCacheNames(self):
        '''
        This needs to be used **every time** after setting one or more properties, to make sure the latest
        cache name list is stored in its window memory property.
        '''
        self.window.setProperty(self.PROPERTY_CACHE_NAMES, self._setToString(self.cacheNames))


    def getCacheProperty(self, propName, readFromDisk):
        '''
        Tries to return the data from a window memory property.
        :param propName: Name of the property to retrieve.
        :param readFromDisk: Used with properties that might be saved on disk (it tries to load
        from memory first though).
        :returns: The property data, if it exists, or None.
        '''
        if readFromDisk:
            self._ensureCacheLoaded()            
            if propName in self.cacheNames:
                propRaw = self.window.getProperty(propName)
                return json.loads(propRaw)[0] if propRaw else None # **Important** Return index [0], data.
            else:
                return None
        else:
            # Use JSON on this memory-only property.
            # If the caller wants the pure string from the window property they could use
            # setRaw(...)\getRaw(...) instead.
            data = self.window.getProperty(propName)
            return json.loads(data)[0] if data else None # **Index [0], data**

            
    def clearCacheProperty(self, propName, readFromDisk):
        '''
        Removes a property from memory. The next time the cache is saved this property
        won't be included and therefore forgotten.
        *** The caller is expected to call flushCacheNames() *** after it has cleared
        one or more properties.
        '''
        self.window.clearProperty(propName)
        if readFromDisk:
            self._ensureCacheLoaded()
            if propName in self.cacheNames:
                self.cacheNames.discard(propName)
            

    def setRawProperty(self, propName, data):
        '''
        Convenience function to set a window memory property that doesn't
        need JSON serialization or saving to disk.
        Used for unimportant properties that should persist between add-on directories.
        :param propName: The name of the property used to identify the data, later used
        to retrieve it.
        :param rawData: String data, stored as it is.
        '''
        self.window.setProperty(propName, data)


    def getRawProperty(self, propName):
        '''
        Retrieves a simple window property by name.
        '''
        return self.window.getProperty(propName)


    def clearRawProperty(self, propName):
        '''
        Retrieves a simple window property by name.
        '''
        return self.window.clearProperty(propName)


    def saveCacheIfDirty(self):
        if self.testFlag(self.FLAG_CACHE_FILE_FLUSH): # Flag set by setCacheProperty().
            if self.cacheNames or self._loadMemoryCache():
                self._saveCache()
                self.clearFlag(self.FLAG_CACHE_FILE_FLUSH)
                self.flushFlags()


    def _saveCache(self):
        '''
        Internal.
        Assumes the destination folder already exists.
        Assumes 'self.cacheNames' has already been refreshed \ updated.
        '''
        def __makeSaveData():
            '''
            :returns: A generator of dicts, one dict for each window memory
            property that has 'saveToDisk=True'.
            Note that the cache version is prepended to each property entry.
            '''
            for propName in self.cacheNames:
                propRaw = self.window.getProperty(propName)
                if propRaw:
                    # Same structure as in setCacheProperty().
                    data, saveToDisk, lifetime, epoch = json.loads(propRaw)
                    if saveToDisk:
                        yield {
                            'version': self.CACHE_VERSION,
                            'propName': propName,                            
                            'data': data,
                            'lifetime': lifetime,
                            'epoch': epoch
                        }
        fullPath = self.CACHE_PATH_DIR + self.CACHE_FILENAME    
        file = xbmcvfs.File(fullPath, 'w')
        file.write(json.dumps(tuple(__makeSaveData())))
        file.close()


    def _setToString(self, setObject):
        return (','.join(element for element in setObject))


    def _stringToSet(self, text):
        return set(text.split(','))


    def _getEpochHours(self):
        '''
        Internal. Gets the current UNIX epoch time in hours.
        '''
        return int(time() // 3600.0)


cache = SimpleCache()
