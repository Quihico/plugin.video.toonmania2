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

    '''
    Cache version log:
    1: Toonmania2 0.4.0
    
    2: Toonmania2 0.4.1
        I realized '/GetNew(...)' and '/GetPopular(...)' routes just need the IDs, not the whole JSON data.
        If something is in a '/GetPopular(...)' it will definitely be in the corresponding '/GetAll(...)'.
        So we keep only the IDs and retrieve the full entry from the 'All' routes.
        This change helps use less disk-space and memory.
    '''
    # Cache version, for future extension. Used with properties saved to disk.
    CACHE_VERSION = '2'

    LIFETIME_THREE_DAYS = 72 # 3 days, in hours.
    LIFETIME_ONE_WEEK = 168 # 7 days.
    LIFETIME_FOREVER = 0 # Never expires (see _loadFileCacheHelper())
    
    CACHE_PATH_DIR = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')).decode('utf-8')
    CACHE_FILENAME = 'cache.json'

    # Property name pointing to a Python 'set()' of property names.
    # This is used to quickly tell if a property exists or not by checking its name in the set, 
    # rather than retrieving a property that could be a huge JSON blob just to see that it exists.
    PROPERTY_DISK_CACHE_NAMES = 'scache.prop.names'

    # Property name pointing to a comma-separated list of flags.
    # This list is converted to a set when read and used for quick boolean-style testing.
    # Testing a flag means seeing if it's present in the set or not.
    PROPERTY_FLAGS = 'scache.prop.memory'

    # Flag name for testing if items were added to the memory cache so it should be saved to disk.
    # Otherwise clear.
    FLAG_CACHE_FILE_FLUSH = 'scache.flag.fileFlush'
    
    # Flag name for testing if there was a problem loading the cache file for this Kodi session.
    # Otherwise it means everything's fine.
    # This is used to just show the file reading failure notification once.
    FLAG_CACHE_FILE_FAILED = 'scache.flag.fileFailed'


    def __init__(self):
        # Initialised at every directory change in Kodi <= 17.6
        self.diskCacheNames = None
        self.flags = None
        self.window = Window(getCurrentWindowId())


    def _ensureCacheLoaded(self):
        if not self.diskCacheNames:
            # Try to load the cache names from memory first, then from file.
            if not self._loadMemoryCache() and not self._loadFileCache():
                self.diskCacheNames = set()
                

    def _loadMemoryCache(self):
        diskCacheNamesRaw = self.window.getProperty(self.PROPERTY_DISK_CACHE_NAMES)
        if diskCacheNamesRaw:
            self.diskCacheNames = self._stringToSet(diskCacheNamesRaw)
            return True
        else:
            return False


    def _loadFileCacheHelper(self, fileData):
        '''
        Internal.
        Helper function that loads window properties from data in the cache file.
        '''
        self.diskCacheNames = set()        
        hasExpiredProps = False
        currentTime = self._getEpochHours()

        allData = json.loads(fileData) # 'allData' is a JSON list of SimpleCache property data.
        for propEntry in allData:
            # Interpret the property based on the cache version used to write it, allowing
            # for branching like expecting a certain format depending on version etc.
            
            version = propEntry['version']
            if version < self.CACHE_VERSION:
                hasExpiredProps = True
                continue # Ignore this property.
            
            epoch = propEntry['epoch']
            lifetime = propEntry['lifetime']

            # Enact property lifetime.
            elapsedHours = currentTime - epoch
            if lifetime == 0 or abs(elapsedHours) <= lifetime:
                # Load the entry as a window memory property, similar to setCacheProperty().
                # We don't use setCacheProperty() or the 'epoch' would be changed to "right now".
                # No need to store the original property cache version, as it became the latest version now.
                propName = propEntry['propName']
                self.diskCacheNames.add(propName)
                self.window.setProperty(propName, json.dumps((propEntry['data'], True, lifetime, epoch)))
            else:
                # Ignore it.
                hasExpiredProps = True                
        self._flushDiskCacheNames()

        # Any expired properties were ignored. Request an overwrite of the cache file so they can be erased.
        if hasExpiredProps:
            self.setFlag(self.FLAG_CACHE_FILE_FLUSH)
            self.flushFlags()


    def _loadFileCache(self):
        '''
        Tries to load the cache file if it exists, or creates a blank cache file if it there isn't one.
        '''
        fullPath = self.CACHE_PATH_DIR + self.CACHE_FILENAME
        if not self.testFlag(self.FLAG_CACHE_FILE_FAILED) and xbmcvfs.exists(fullPath):
            file = xbmcvfs.File(fullPath)
            try:
                # Try to load the iist of disk-saved properties.
                self._loadFileCacheHelper(file.read())
            except:
                # Error. Notification with no sound.
                from xbmcgui import Dialog, NOTIFICATION_INFO
                dialog = Dialog()
                dialog.notification('Cache', 'Could not read cache file', NOTIFICATION_INFO, 3000, False)
                self.diskCacheNames = None
                # Set a flag to forget about using the cache file during this Kodi session.
                self.setFlag(self.FLAG_CACHE_FILE_FAILED)
                self.flushFlags()
            finally:
                file.close()
                return self.diskCacheNames
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
            self.diskCacheNames.add(propName)
            self._flushDiskCacheNames()
            self.setFlag(self.FLAG_CACHE_FILE_FLUSH) # Used by saveCacheIfDirty().
            self.flushFlags()
            
            
    def setCacheProperties(self, properties):
        '''
        Convenience function to create several properties at once.
        :param properties: An iterable, each entry in 'properties' should be a tuple, list or other
        indexable object of this format:
        ((str)PROPERTY_NAME, (anything)PROPERTY_DATA, (bool)SAVE_TO_DISK, (int)LIFETIME_HOURS)
        
        The 'PROPERTY_DATA' field should be JSON-serializable.
        '''
        anySaveToDisk = True
        for pEntry in properties:
            # Same as in setCacheProperty().
            name, data, saveToDisk, lifetime = pEntry
            self.window.setProperty(name, json.dumps((data, saveToDisk, lifetime, self._getEpochHours())))
            if saveToDisk:
                if not self.diskCacheNames:
                    self._ensureCacheLoaded()
                self.diskCacheNames.add(name)
                anySaveToDisk = True
            
        if anySaveToDisk:
            self._flushDiskCacheNames()
            self.setFlag(self.FLAG_CACHE_FILE_FLUSH) # Used by saveCacheIfDirty().
            self.flushFlags()            
        

    def _flushDiskCacheNames(self):
        '''
        Internal. This needs to be used **every time** after setting one or more properties, to make sure
        the latest disk cache names set is stored in its window memory property.
        '''
        self.window.setProperty(self.PROPERTY_DISK_CACHE_NAMES, self._setToString(self.diskCacheNames))


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
            if propName in self.diskCacheNames:
                propRaw = self.window.getProperty(propName)
                return json.loads(propRaw)[0] if propRaw else None # Return from index [0], data.
            else:
                return None
        else:
            # Use JSON on this memory-only property.
            # If the caller wants the pure string from the window property they could use
            # the setRaw(...)\getRaw(...) functions instead.
            data = self.window.getProperty(propName)
            return json.loads(data)[0] if data else None # Index [0], data.
            
            
    def clearCacheProperty(self, propName, readFromDisk):
        '''
        Removes a property from memory. The next time the cache is saved this property
        won't be included and therefore forgotten.
        '''
        self.window.clearProperty(propName)
        if readFromDisk:
            self._ensureCacheLoaded()
            self.diskCacheNames.discard(propName)
            self._flushDiskCacheNames()
            

    def setRawProperty(self, propName, data):
        '''
        Convenience function to set a window memory property that doesn't
        need JSON serialization or saving to disk.
        Used for unimportant memory-only properties that should persist between add-on
        directories.
        :param propName: The name of the property used to identify the data, later used
        to retrieve it.
        :param rawData: String data, stored as it is.
        '''
        self.window.setProperty(propName, data)


    def getRawProperty(self, propName):
        '''
        Retrieves a direct window property by name.
        '''
        return self.window.getProperty(propName)


    def clearRawProperty(self, propName):
        '''
        Clears a direct window property by name.
        To clear a property that was created with setCacheProperty()
        use clearCacheProperty() instead.
        '''
        return self.window.clearProperty(propName)


    def saveCacheIfDirty(self):
        if self.testFlag(self.FLAG_CACHE_FILE_FLUSH): # Flag set by setCacheProperty().
            if self.diskCacheNames or self._loadMemoryCache():
                self._saveCache()
                self.clearFlag(self.FLAG_CACHE_FILE_FLUSH)
                self.flushFlags()


    def _saveCache(self):
        '''
        Internal.
        Assumes the destination folder already exists.
        Assumes 'self.diskCacheNames' has already been refreshed \ updated.
        '''
        def __makeSaveData():
            '''
            :returns: A generator of dicts, one dict for each window memory
            property that has 'saveToDisk=True'.
            Note that the cache version is prepended to each property entry.
            '''
            for propName in self.diskCacheNames:
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
