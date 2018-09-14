# -*- coding: utf-8 -*-
'''
Temporary service to TRY to delete the old single 'cache.json' from previous Toonmania2 versions, as now
Toonmania2 uses a '/cache/' subfolder with separate files, which is more efficient.
'''
from os import path

import xbmc
import xbmcvfs
import xbmcaddon


ADDON = xbmcaddon.Addon()

def finishTasks():
    try:
        addonProfileFolder = xbmc.translatePath(ADDON.getAddonInfo('profile')).decode('utf-8')
        oldFilePath = path.join(addonProfileFolder, 'cache.json')
        if xbmcvfs.exists(oldFilePath):
            xbmcvfs.delete(oldFilePath)
        # etc.
        return True
    except:
        return False

    
def deleteItself():
    try:
        addonRootFolder = xbmc.translatePath(ADDON.getAddonInfo('path')).decode('utf-8')
        SERVICE_FILENAME = 'CleanupService.py'
        PATTERN = 'library="' + SERVICE_FILENAME + '"'

        serviceScriptPath = path.join(addonRootFolder, SERVICE_FILENAME)
        xbmcvfs.delete(serviceScriptPath)
        
        addonXMLPath = path.join(addonRootFolder, 'addon.xml')
        with open(addonXMLPath, 'r+') as xmlFile:
            originalLines = xmlFile.readlines()
            xmlFile.seek(0)            
            for line in originalLines:
                if PATTERN not in line: # Ignore the line with your service entry.
                    xmlFile.write(line)
            xmlFile.truncate()
        # Now 'addon.xml' doesn't have the service extension point anymore.    
        return True
    except:
        return False

        
xbmc.log('Toonmania2 | Cleanup Service: starting...', xbmc.LOGNOTICE)    
    
# 1) Try to delete the old 'cache.json' single file, it if exists.
if finishTasks():
    xbmc.log('Toonmania2 | Cleanup Service: tasks complete.', xbmc.LOGNOTICE)

# 2) Remove itself from the add-on folder and overwrite 'addon.xml' to remove the service extension point.
if deleteItself():
    xbmc.log('Toonmania2 | Cleanup Service: successfully deleted itself, will never run again.', xbmc.LOGNOTICE)