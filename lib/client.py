# -*- coding: utf-8 -*-
import re
import sys
import json
import requests
from datetime import datetime
from urllib import urlencode
from itertools import chain, islice
try:
    # Python 2.7
    from urlparse import parse_qs, urlparse
except ImportError:
    # Python 3
    from urllib.parse import parse_qs

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from lib.common import getRawWindowProperty, setRawWindowProperty
#from lib.simple_tvdb import tvdb # Unused. Potentially get per-episode thumbnails and descriptions in the future.
#from lib.simple_cache import cache # Unused for now. Cache to spare the website from excessive requests...
from lib.request_helper import requestHelper
from lib.catalog_helper import catalogHelper

# Addon user settings.
addon = xbmcaddon.Addon()
ADDON_SHOW_THUMBS = addon.getSetting('show_thumbnails') == 'true'
ADDON_PAGE_SIZE = int(addon.getSetting('page_size')) # Page size = number of items per catalog section page.
ADDON_USE_GRID = addon.getSetting('use_grid') == 'true'

# Used to help organise provider streams.
class Provider:
    def __init__(self):
        self.name = ''
        self.streams = [ ]

# Set of "mostly" supported providers.
SUPPORTED_PROVIDERS = {
    'videozoo.me', 'videozoome', 'videozoo', # All of these variants come up in the URLs...
    'play44.net', 'play44net', 'play44',
    'easyvideo.me', 'easyvideome', 'easyvideo',
    'playbb.me', 'playbbme', 'playbb',
    'playpanda.net', 'playpandanet', 'playpanda'
    'videowing'
}
# Resolving not available for these right now, they need to be researched on how to solve:
# 'cheesestream.com','4vid.me','video66.org','videobug.net', 'videofun.me', 'vidzur.com'.


def viewMenu(params):
    listItems = (
        (
            buildURL({'view': 'ANIMETOON_MENU'}),
            xbmcgui.ListItem('[B][COLOR orange]Cartoons & Dubbed Anime[/COLOR][/B]'),
            True
        ),
        (
            buildURL({'view': 'ANIMEPLUS_MENU'}),
            xbmcgui.ListItem('[B][COLOR orange]Subbed Anime[/COLOR][/B]'),
            True
        ),
        (
            buildURL({'view': 'SETTINGS'}),
            xbmcgui.ListItem('[B][COLOR lavender]Settings[/COLOR][/B]'),
            False
        )
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def viewSettings(params):
    # Open the settings dialog.
    addon.openSettings() # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    # So it's a good time to update the globals.
    ADDON_SHOW_THUMBS = addon.getSetting('show_thumbnails') == 'true'
    ADDON_PAGE_SIZE = int(addon.getSetting('page_size'))
    ADDON_USE_GRID = addon.getSetting('use_grid') == 'true'


def viewAnimetoonMenu(params):
    # API value:
    # 0 = Animetoon (cartoons & dubbed anime).
    # 1 = Animeplus (subbed anime).
    def _animetoonItem(view, color, title, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        item.setInfo( 'video', {'title': title, 'plot': title})
        return (buildURL({'view': view, 'api': requestHelper.API_ANIMETOON, 'route': route}), item, True)

    listItems = (
        # Needs different treatment as it doesn't have a
        # description field for the shows, only id, name, section and 'episodes' (list of episodes added).
        _animetoonItem('CATALOG_MENU', 'lavender', 'Latest Updates', '/GetUpdates/'),
        _animetoonItem('CATALOG_MENU', 'darkorange', 'New Movies', '/GetNewMovies'),
        _animetoonItem('CATALOG_MENU', 'darkorange', 'All Movies', '/GetAllMovies'),
        _animetoonItem('CATALOG_MENU', 'darkorange', 'Popular Movies', '/GetPopularMovies'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'New Cartoons', '/GetNewCartoon'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'All Cartoons', '/GetAllCartoon'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'Popular Cartoons', '/GetPopularCartoon'),
        _animetoonItem('CATALOG_MENU', 'orange', 'New Dubbed Anime', '/GetNewDubbed'),
        _animetoonItem('CATALOG_MENU', 'orange', 'All Dubbed Anime', '/GetAllDubbed'),
        _animetoonItem('CATALOG_MENU', 'orange', 'Popular Dubbed Anime', '/GetPopularDubbed'),
        _animetoonItem('SEARCH_MENU', 'lavender', 'Search', '')
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def viewAnimeplusMenu(params):
    def _animeplusItem(view, color, title, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        item.setInfo( 'video', {'title': title, 'plot': title})
        return (buildURL({'view': view, 'api': requestHelper.API_ANIMEPLUS, 'route': route}), item, True)

    listItems = (
        _animeplusItem('CATALOG_MENU', 'lavender', 'Latest Updates', '/GetUpdates/'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'New Anime Movies', '/GetNewMovies'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'All Anime Movies', '/GetAllMovies'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'Popular Anime Movies', '/GetPopularMovies'),
        _animeplusItem('CATALOG_MENU', 'orange', 'New Subbed Anime', '/GetNewShows'),
        _animeplusItem('CATALOG_MENU', 'orange', 'All Subbed Anime', '/GetAllShows'),
        _animeplusItem('CATALOG_MENU', 'orange', 'Popular Subbed Anime', '/GetPopularShows'),
        _animeplusItem('SEARCH_MENU', 'lavender', 'Search', '')
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


# A sub menu, lists search options.
def viewSearchMenu(params):
    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if params.get('route', '') == '_inputSearch':
        text = _modalKeyboard('Search by Name')
        if text:
            # Send the search query for the catalog functions to use.
            params.update({'view': 'CATALOG_MENU', 'route': '_executeSearch', 'query': text})
            viewCatalogMenu(params)
            #xbmc.executebuiltin('Container.Update(%s,replace)' % buildURL(params) )
            return
        else:
            # User typed nothing or cancelled the keyboard.
            return # Returning like this w/o finishing the directory causes a log error, but it's the best UX in my opinion.

    listItems = (
        (
            buildURL({'view': 'SEARCH_MENU', 'api': params['api'], 'route': '_inputSearch'}),
            xbmcgui.ListItem('[COLOR lavender][B]Search by Name[/B][/COLOR]'),
            True
        ),
        (
            buildURL({'view': 'SEARCH_GENRE', 'api': params['api'], 'route': '/GetGenres/'}),
            xbmcgui.ListItem('[COLOR lavender][B]Search by Genre[/B][/COLOR]'),
            True
        )
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


# A sub menu, lists the genre categories in the genre search.
def viewSearchGenre(params):
    api = params['api']
    route = params['route']
    
    # Cache the genre names. This property is only used within this function.
    if api == requestHelper.API_ANIMETOON:
        _PROPERTY_GENRE_NAMES = 'toonmania2.genreNamesToon'
    else:
        _PROPERTY_GENRE_NAMES = 'toonmania2.genreNamesPlus'
    
    genreList = getRawWindowProperty(_PROPERTY_GENRE_NAMES)
    if genreList:
        genreList = genreList.decode('utf-8').split(',')
    else:
        # The data from the '/GetGenres/' route is a dict with a list of genre names like "Action",
        # "Comedy" etc., but it also has some weird things in the list, probably from data-entry errors.
        requestHelper.setAPISource(api)
        startTime = datetime.now()
        genreList = requestHelper.routeGET(route).get('genres', [ ])
        requestHelper.apiDelay(startTime)
        setRawWindowProperty(_PROPERTY_GENRE_NAMES, ','.join(genreList))
    
    listItems = (
        (   # Send the genre name for the catalog functions to use.
            buildURL({'view': 'CATALOG_MENU', 'api': api, 'route': route, 'genreName': genreName}),
            xbmcgui.ListItem(genreName),
            True
        )
        for genreName in genreList
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(listItems))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    
    
# Tries to extract season and episode values based on the title string.
def getTitleInfo(unescapedTitle):
    season = episode = 0
    titleWords = unescapedTitle.split()
    for index, word in enumerate(titleWords):
        if word == 'Season':
            try:
                season = int(titleWords[index+1])
            except ValueError:
                pass
        elif word == 'Episode':
            try:
                episode = int(titleWords[index+1])
                if not season:
                    season = 1 # Season may be omitted in the title.
                break # The word 'Episode' is always put after the season and show title in the link strings.
            except ValueError:
                season = episode = 0 # Malformed \ typo'ed strings caused this?
    return (season, episode)


# item -> xbmcgui.ListItem, showTitle\thumb\plot -> strings, season\episode -> int.
def setupListItem(item, showTitle, title, isPlayable, season, episode, genres, thumb = '', plot = ''):
    if isPlayable:
        item.setProperty('IsPlayable', 'true') # Allows the checkmark to be placed on watched episodes.

    if thumb:
        item.setArt({'icon': thumb, 'thumb': thumb, 'poster': thumb})

    # All items are set with 'episode' mediatype even if they aren't, as it looks better in the skin layout.
    itemInfo = {
        'mediatype': 'episode' if isPlayable else 'tvshow',
        'tvshowtitle': showTitle,
        'title': title,
        'plot': plot,
        'genre': genres if genres else ''
    }
    if episode:
        itemInfo.update({'season': season, 'episode': episode})
    item.setInfo('video', itemInfo)


def viewCatalogMenu(params):
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')    
    
    catalog = catalogHelper.getCatalog(params)    
    api = params['api']
    route = params['route']
    
    listItems = tuple(
        (
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': sectionName, 'page': 0}),
            xbmcgui.ListItem(sectionName),
            True
        )
        for sectionName in sorted(catalog.iterkeys()) if len(catalog[sectionName]) > 0
    )
    if len(listItems):
        sectionAll = (
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': 'ALL', 'page': 0}),
            xbmcgui.ListItem('All'),
            True
        )
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), (sectionAll,) + listItems)
    else:
        # Empty directory for an empty catalog (no search results, for example).
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem('No Items Found'), False)
        
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    # Always use InfoWall mode (assuming it's Estuary skin, the default skin), in this directory
    # as it makes it easier to pick a catalog section.
    xbmc.executebuiltin('Container.SetViewMode(54)')


def viewCatalogSection(params):
    if ADDON_USE_GRID:
        xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
        
    catalog = catalogHelper.getCatalog(params)

    def _catalogSectionItems(iterable):
        api = params['api']        
        if ADDON_SHOW_THUMBS:
            requestHelper.setAPISource(api) # Set the API base URL to retrieve the thumb URLs.
            for entry in iterable:
                # entry = (id, name, description, genres)
                thumb = requestHelper.makeThumbURL(entry[0])
                item = xbmcgui.ListItem(entry[1])
                setupListItem(item, entry[1], entry[1], False, 0, 0, entry[3], thumb = thumb, plot = entry[2])
                yield (
                    buildURL(
                        {
                            'view': 'LIST_EPISODES',
                            'api': api,
                            'id': entry[0],
                            'genres': entry[3] if entry[3] else '',
                            'thumbURL': thumb,
                            'plot': entry[2]
                        }
                    ),
                    item,
                    True
                )
        else:
            for entry in iterable:
                item = xbmcgui.ListItem(entry[1])
                setupListItem(item, entry[1], entry[1], False, 0, 0, entry[3], thumb = '', plot = entry[2])
                yield (
                    buildURL(
                        {
                            'view': 'LIST_EPISODES',
                            'api': api,
                            'id': entry[0],
                            'genres': entry[3] if entry[3] else '',
                            'plot': entry[2]
                        }
                    ),
                    item,
                    True
                )

    sectionName = params['section']

    if ADDON_SHOW_THUMBS:
        # Display items in pages so the thumbs are loaded in chunks to not overburden the source website.

        page = int(params['page']) # Zero-based index.
        start = page * ADDON_PAGE_SIZE
        stop = start + ADDON_PAGE_SIZE

        if sectionName == 'ALL':
            # Create pages for the pseudo-section "ALL":
            # Flatten all sections into a list, which is then isliced to get the current directory page.
            flatSections = chain.from_iterable(catalog[sName] for sName in sorted(catalog.iterkeys()))
            itemsIterable = (entry for entry in islice(flatSections, start, stop))
            totalSectionPages = sum(len(section) for section in catalog.itervalues()) // ADDON_PAGE_SIZE
        else:
            # Use one of the premade pages.
            itemsIterable = (entry for entry in islice(catalog[sectionName], start, stop))
            totalSectionPages = len(catalog[sectionName]) // ADDON_PAGE_SIZE

        page += 1
        if totalSectionPages > 1 and page < totalSectionPages:
            params.update({'page':page})
            nextPage = (buildURL(params), xbmcgui.ListItem('Next Page ('+str(page+1)+'/'+str(totalSectionPages)+')'), True)
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)) + (nextPage,))
        else:
            xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))
    else:
        if sectionName == 'ALL':
            itemsIterable = (entry for entry in chain.from_iterable(catalog[s] for s in sorted(catalog.iterkeys())))
        else:
            itemsIterable = (entry for entry in catalog[sectionName])
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    if ADDON_USE_GRID:
        xbmc.executebuiltin('Container.SetViewMode(54)') # InfoWall.
    else:
        xbmc.executebuiltin('Container.SetViewMode(55)') # WideList.


# Pages aren't necessary in the episode lists because they all use the same thumb and plot.
def viewListEpisodes(params):
    if ADDON_USE_GRID:
        xbmcplugin.setContent(int(sys.argv[1]), 'episodes') # Changes the skin layout.
    # Optional, sort episode list by labels.
    #xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    requestHelper.setAPISource(params['api'])
    jsonData = requestHelper.routeGET('/GetDetails/' + params['id'])

    def _listEpisodesItems():
        episodes = jsonData['episode']
        api = params['api']
        plot = params['plot']
        thumb = params.get('thumbURL', '')
        genres = params.get('genres', '').split(',')

        for episodeEntry in episodes:
            #episode = dict( id=str, name=str, date='yyyy-MM-dd (...)' )
            name = episodeEntry['name']
            item = xbmcgui.ListItem(name)
            season, episode = getTitleInfo(name)
            showTitle = jsonData.get('name', name) # Try the entry title first, then episode name if it fails.
            setupListItem(item, showTitle, name, True, season, episode, genres, thumb, plot)
            yield (
                buildURL(
                    {
                        'view': 'RESOLVE',
                        'api': api,
                        'episodeID': episodeEntry['id'],
                        'showTitle': showTitle,
                        'name': name,
                        'season': season,
                        'episode': episode,
                        'genres': ','.join(genres),
                        'thumb': thumb,
                        'plot': plot.decode('utf-8')
                    }
                ),
                item,
                False
            )

    if len(jsonData['episode']) == 1:
        # This is probably a movie, OVA or special.
        # Change the view type to resolve this item into separate parts, for safety.
        # Might get single episode seasons by mistake, but there's no easy way to tell the difference.
        item = tuple(_listEpisodesItems())[0]
        item[1].setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), item[0].replace('view=RESOLVE', 'view=LIST_PARTS'), item[1], True)
    else:
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_listEpisodesItems()))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def resolveEpisodeStreams(api, episodeID):
    def _processProvider(providerURLs):
        # This function will get a list of stream URLs, one list per provider.
        # Try to get the provider name (to see if we support resolving it).
        newProvider = Provider()

        firstURL = providerURLs[0]
        if firstURL.startswith('http://'):
            firstURL = firstURL.replace('http://', '')
        elif firstURL.startswith('https://'):
            firstURL = firstURL.replace('https://', '')

        for word in firstURL.split('.'):
            if word in SUPPORTED_PROVIDERS:
                newProvider.name = word
                break
        else:
            return newProvider # Return it empty. It's not a supported provider.

        # It's usually a single provider url, but there might be more urls for
        # the same provider for entries like movies, which are split in parts.
        for url in providerURLs:
            try:
                startTime = datetime.now()

                temp = None
                r = requestHelper.GET(url)
                if r.ok:
                    html = r.text
                    if 'var video_links' in html:
                        # Try the generic videozoo \ play44 solve first:
                        temp = re.findall(r'''var video_links.*?['"]link['"]\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                    else:
                        # Try variants:
                        temp = re.findall(r'''{\s*?url\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                        if not temp:
                            temp = re.findall(r'''file\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                if temp:
                    newProvider.streams.append(temp[0].replace(r'\/', r'/')) # In case there's escaped JS slashes.

                requestHelper.apiDelay(startTime) # Sleep this thread a little before the next request, if necessary.
            except:
                pass

        # Uncomment the next two lines for debugging failed providers.
        #if not streamURLs:
        #    xbmc.log('Toonmania2 --- Failed resolving provider: '+providerName+' '+str(providerURLs), xbmc.LOGWARNING)
        return newProvider

    requestHelper.setAPISource(api)
    jsonData = requestHelper.routeGET('/GetVideos/' + episodeID)
    if jsonData:
        if isinstance(jsonData[0], dict): # Animeplus special case, URLs might come inside one dictionary each provider.
            processedProviders = (_processProvider( (provider['url'],) ) for provider in jsonData)
        else:
            processedProviders = (_processProvider(providerURLs) for providerURLs in jsonData)

        # Each provider is a tuple, with index 0 = providerName, index 1 = list of
        # provider URL(s) (video parts, even if it's one).
        return (provider for provider in processedProviders if len(provider.streams))
    else:
        return


def viewListParts(params):
    validProviders = tuple(resolveEpisodeStreams(params['api'], params['episodeID']))
    
    def _listPartsItems():
        for provider in validProviders:
            for index, stream in enumerate(provider.streams):
                partName = params['name'] + ' | PART ' + str(index+1)
                item = xbmcgui.ListItem('[COLOR lavender][B]%s[/B][/COLOR] | %s' % (provider.name.upper(), partName))
                setupListItem(
                    item,
                    params['showTitle'],
                    partName,
                    True,
                    int(params['season']),
                    int(params['episode']),
                    params.get('genres', '').split(','),
                    params.get('thumb', ''),
                    params['plot']
                )
                item.setPath(stream)
                yield (stream, item, False)

    itemsList = tuple(_listPartsItems())
    if itemsList:
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), itemsList)
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification('Toonmania2', 'Could not find any stream URLs', xbmcgui.NOTIFICATION_INFO, 2500, False)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def viewResolve(params):
    validProviders = tuple(resolveEpisodeStreams(params['api'], params['episodeID']))
    
    if len(validProviders):
        item = xbmcgui.ListItem(params['name'])
        setupListItem(
            item,
            params['showTitle'],
            params['name'],
            True,
            int(params['season']),
            int(params['episode']),
            params.get('genres', None),
            params.get('thumb', ''),
            params['plot']
        )
        selectedIndex = xbmcgui.Dialog().select('Select Provider', tuple(provider.name for provider in validProviders))
        if selectedIndex != -1:
            item.setPath(validProviders[selectedIndex].streams[0])
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
    
            # Failed attempt at trying to autoplay all multi-part videos
            # using a XBMC video playlist. Using directories seems safer.
            '''if len(streamURLs) > 1:
                player = xbmc.Player()
                for wait in range(60): # Wait at most 60 seconds for the video to start playing.
                    if player.isPlayingVideo():
                        break
                    xbmc.sleep(1000)
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                streams = iter(streamURLs)
                next(streams) # Skip the first one, already being played.
                for index, stream in enumerate(streams):
                    playlist.add(stream, index = index)'''
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification('Toonmania2', 'Could not find any stream URLs', xbmcgui.NOTIFICATION_INFO, 2500, False)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem('None'))
        
def buildURL(query):
    return sys.argv[0] + '?' + urlencode( {k: unicode(v).encode('utf-8') for k, v in query.iteritems()})


# Main dictionary of add-on directories (aka views or screens).
VIEW_FUNCS = {
    'MENU': viewMenu,
    'SETTINGS': viewSettings,
    'ANIMETOON_MENU': viewAnimetoonMenu,
    'ANIMEPLUS_MENU': viewAnimeplusMenu,

    'CATALOG_MENU': viewCatalogMenu,
    'CATALOG_SECTION': viewCatalogSection,
    'SEARCH_MENU': viewSearchMenu,
    'SEARCH_GENRE': viewSearchGenre,

    'LIST_EPISODES': viewListEpisodes,
    'LIST_PARTS': viewListParts,
    'RESOLVE': viewResolve
}


def main():
    params = {key: value[0] for key, value in parse_qs(sys.argv[2][1:]).iteritems()}
    VIEW_FUNCS[params.get('view', 'MENU')](params)