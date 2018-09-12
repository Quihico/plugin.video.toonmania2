# -*- coding: utf-8 -*-
import os

import xbmc
import xbmcvfs
import xbmcaddon
from xbmcgui import Dialog


'''
Temporary service to TRY to delete the old single 'cache.json' from previous Toonmania2 versions (< 0.4.3), as now
Toonmania2 uses a '/cache/' subfolder with separate files which is more efficient.

First this service does some file housekeeping, then deletes itself and rewrites Toonmania2's 'addon.xml'
so it doesn't run again.
'''

ADDON = xbmcaddon.Addon()
tasksComplete = False

# 1) Try to delete the old 'cache.json' single file, it if exists.
# Use the same path as in older versions of Toonmania2.
addonProfileFolder = xbmc.translatePath(ADDON.getAddonInfo('profile')).decode('utf-8')
try:
    oldFilePath = os.path.join(addonProfileFolder, 'cache.json')
    if xbmcvfs.exists(oldFilePath):
        xbmcvfs.delete(oldFilePath)
    # etc.
    tasksComplete = True
except:
    pass

# 2) Remove itself from the add-on folder, and overwrite 'addon.xml' to remove the extension point
# that ran this service.

addonRootFolder = xbmc.translatePath(ADDON.getAddonInfo('path')).decode('utf-8')
SERVICE_FILENAME = 'CleanupService.py'

try:
    serviceScriptPath = os.path.join(addonRootFolder, SERVICE_FILENAME)
    xbmcvfs.delete(serviceScriptPath)
    
    addonXMLPath = os.path.join(addonRootFolder, 'addon.xml')
    with open(addonXMLPath, 'r+') as xmlFile:
        originalLines = xmlFile.readlines()
        xmlFile.seek(0)
        for line in originalLines:
            if SERVICE_FILENAME not in line: # Ignore the line with your service entry.
                xmlFile.write(line)
        xmlFile.truncate()
    # Now 'addon.xml' doesn't have the service extension point anymore.    
    if tasksComplete:
        Dialog().notification('Toonmania2', 'Post-update cleanup successful', xbmcgui.NOTIFICATION_INFO, 4000, False)
except:
    pass