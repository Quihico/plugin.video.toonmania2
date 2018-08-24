# -*- coding: utf-8 -*-
import re
import sys
import json
import requests
from time import time
from bs4 import BeautifulSoup
from urllib import urlencode
from base64 import b64decode
from string import ascii_uppercase
from itertools import chain, islice
try:
    # Python 2.7
    from urlparse import parse_qs
    from HTMLParser import HTMLParser
except ImportError:
    # Python 3
    from urllib.parse import parse_qs
    from html.parser import HTMLParser

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from lib.common import (
    getWindowProperty,
    setWindowProperty
)
#from lib.simpletvdb import tvdb # Unused. Potentially get per-episode thumbnails and descriptions in the future.
#from lib.simplecache import cache # Unused for now. Cache to spare the website from excessive requests...
from lib.requesthelper import requestHelper

# Persistent memory properties used to hold the catalog path (the website "area" being displayed) and
# the catalog of items itself, with sections and items. See catalogFromIterable() for more info.
PROPERTY_CATALOG_PATH = 'toonmania2.catalogPath'
PROPERTY_CATALOG = 'toonmania2.catalog'

HTML_PARSER = HTMLParser()

addon = xbmcaddon.Addon()
#ADDON_ICON_PATH = addon.getAddonInfo('icon')
ADDON_SHOW_THUMBS = addon.getSetting('show_thumbnails') == 'true'
ADDON_USE_GRID = addon.getSetting('use_grid') == 'true'

# Page size = number of items per catalog section page.
# CAREFUL not to be greedy. The larger the pages, the more thumbnail requests will be done at once to the websites.
CATALOG_PAGE_SIZE = 30 # Default: 30 items per page, with 1 request per item (for Kodi thumbnail).
API_REQUEST_DELAY = 200 # In milliseconds, waited between each add-on request (used for resolving stream URLs).


# Resolving not available for these right now, they need to be researched on how to solve.
UNSUPPORTED_PROVIDERS = {'cheesestream.com','4vid.me','video66.org','videobug.net', 'videofun.me', 'vidzur.com'}
# Separating supported providers in groups according to their url resolving method.
SUPPORTED_PROVIDERS = {
    'videozoo.me', 'videozoome', 'videozoo', # All of these variants exist...
    'play44.net', 'play44net', 'play44',
    'easyvideo.me', 'easyvideome', 'easyvideo',
    'playbb.me', 'playbbme', 'playbb',
    'playpanda.net', 'playpandanet', 'playpanda'
}


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
    addon.openSettings()


def viewAnimetoonMenu(params):
    # API value:
    # 0 = Animetoon (cartoons & dubbed anime).
    # 1 = Animeplus (subbed anime).
    def _animetoonItem(view, color, title, api, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        return (buildURL({'view': view, 'api': api, 'route': route}), item, True)

    listItems = (
        #_animetoonItem('CATALOG_MENU', 'lavender', 'Latest Updates', 0, '/GetUpdates/'),
        # 'Latest Updates' section to be added later. Needs different treatment as it doesn't
        # have 'description' data for the shows, only id, name, section and 'episodes' (list of episodes added).

        _animetoonItem('CATALOG_MENU', 'darkorange', 'New Movies', 0, '/GetNewMovies'),
        _animetoonItem('CATALOG_MENU', 'darkorange', 'All Movies', 0, '/GetAllMovies'),
        _animetoonItem('CATALOG_MENU', 'darkorange', 'Popular Movies', 0, '/GetPopularMovies'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'New Cartoons', 0, '/GetNewCartoon'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'All Cartoons', 0, '/GetAllCartoon'),
        _animetoonItem('CATALOG_MENU', 'lightsalmon', 'Popular Cartoons', 0, '/GetPopularCartoon'),
        _animetoonItem('CATALOG_MENU', 'orange', 'New Dubbed Anime', 0, '/GetNewDubbed'),
        _animetoonItem('CATALOG_MENU', 'orange', 'All Dubbed Anime', 0, '/GetAllDubbed'),
        _animetoonItem('CATALOG_MENU', 'orange', 'Popular Dubbed Anime', 0, '/GetPopularDubbed'),
        #_animetoonItem('SEARCH_MENU', 'lavender', 'Search', 0, '') # Search not implemented yet.
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def viewAnimeplusMenu(params):
    def _animeplusItem(view, color, title, api, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        item.setInfo( 'video', {'title': title, 'plot': title})
        return (buildURL({'view': view, 'api': api, 'route': route}), item, True)

    listItems = (
        #_animeplusItem('CATALOG_MENU', 'lavender', 'Latest Updates', 1, '/GetUpdates/'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'New Anime Movies', 1, '/GetNewMovies'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'All Anime Movies', 1, '/GetAllMovies'),
        _animeplusItem('CATALOG_MENU', 'lightsalmon', 'Popular Anime Movies', 1, '/GetPopularMovies'),
        _animeplusItem('CATALOG_MENU', 'orange', 'New Subbed Anime', 1, '/GetNewShows'),
        _animeplusItem('CATALOG_MENU', 'orange', 'All Subbed Anime', 1, '/GetAllShows'),
        _animeplusItem('CATALOG_MENU', 'orange', 'Popular Subbed Anime', 1, '/GetPopularShows'),
        #_animeplusItem('SEARCH_MENU', 'lavender', 'Search', 1, '')
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


# NOT AVAILABLE YET. A sub menu, lists search options.
def viewSearchMenu(params):
    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if '_search' in params:
        text = _modalKeyboard('Search by Name')
        if text:
            params.update({'view': 'CATALOG_MENU', 'api': params['api'], 'text': text}) # Send the search query for the catalog functions to use.
            xbmc.executebuiltin('Container.Update(%s,replace)' % buildURL(params) )
            return
        else:
            return # User typed nothing or cancelled the keyboard.

    listItems = (
        (
            buildURL({'view': 'SEARCH_MENU', 'api': params['api'], 'route': '_search'}),
            xbmcgui.ListItem('Search by Name'),
            True
        ),
        (
            buildURL({'view': 'SEARCH_GENRE', 'api': params['api'], 'route': '_genres'}),
            xbmcgui.ListItem('Search by Genre'),
            True
        ),
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), listItems)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


# A sub menu, lists the genre categories in the genre search.
def viewSearchGenre(params):
    r = requestHelper(BASEURL + URL_PATHS['genre'])
    soup = BeautifulSoup(r.text, 'html.parser')
    mainDIV = soup.find('div', {'class': 'ddmcc'})
    listItems = (
        (
            buildURL( {'view': 'CATALOG_MENU', 'path': URL_PATHS['genre'] + a['href'][ a['href'].rfind('/') : ]} ),
            xbmcgui.ListItem(a.string),
            True
        )
        for a in mainDIV.find_all('a')
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
def setupListItem(item, showTitle, title, isPlayable, season, episode, thumb = '', plot = ''):
    if isPlayable:
        item.setProperty('IsPlayable', 'true') # Allows the checkmark to be placed on watched episodes.

    if thumb:
        item.setArt({'icon': thumb, 'thumb': thumb, 'poster': thumb})

    # All items are set with 'episode' mediatype even if they aren't, as it looks better in the skin layout.
    itemInfo = {'mediatype': 'episode' if isPlayable else 'tvshow', 'tvshowtitle': showTitle, 'title': title, 'plot': plot}
    if episode:
        itemInfo.update({'season': season, 'episode': episode})
    item.setInfo('video', itemInfo)


'''
The catalog is a dictionary of lists of lists, used to store data between add-on states to make xbmcgui.ListItems:
{
    (1. Sections, as in alphabet sections for list items: #, A, B, C, D, E, F etc., each section holds a tuple of pages.)
    A: (
        page1, (2. Each page is a tuple holding items, or empty.)
        page2, (item, item, item, ...)     (3. Items, each item is a tuple: (id, name, description).)
        page3
    )
    B: (...)
    C: (...)
}
'''

# Splits items from an iterable into an alphabetised catalog, w/ above format.
def catalogFromIterable(iterable):
    catalog = {key: [ [ ] ] for key in ascii_uppercase + '#'}
    for item in iterable:
        # item = tuple(id, name, description) -> all str values.
        itemKey = item[1][0].upper()
        section = catalog[itemKey] if itemKey in catalog else catalog['#']
        currentPage = section[-1]
        currentPage.append(item) if len(currentPage) < CATALOG_PAGE_SIZE else section.append( [item] )
    return catalog


def genericCatalog(params):
    requestHelper.setAPISource(int(params['api']))
    jsonData = requestHelper.routeGET(params['route'])
    if jsonData:
        # id, name, description.
        return catalogFromIterable((entry['id'], entry['name'].strip(), entry['description'].strip()) for entry in jsonData)
    else:
        return '{}'


# Retrieves the catalog from a persistent window property between different add-on
# directories, or recreates the catalog if the user changed paths.
def getCatalogProperty(params):
    def _buildCatalog():
        catalog = genericCatalog(params)
        setWindowProperty(PROPERTY_CATALOG, catalog)
        return catalog

    # If these properties are empty (like when coming in from a favourites menu), or if
    # a different catalog (a different website area) is stored in this property, then reload it.
    currentPath = getWindowProperty(PROPERTY_CATALOG_PATH)
    if currentPath != params['route']:
        setWindowProperty(PROPERTY_CATALOG_PATH, params['route'])
        catalog = _buildCatalog()
    else:
        catalog = getWindowProperty(PROPERTY_CATALOG)
        if not catalog:
            catalog = _buildCatalog()
    return catalog


def viewCatalogMenu(params):
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    catalog = getCatalogProperty(params)

    api = params['api']
    route = params['route']

    sectionAll = (
        buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': 'ALL', 'page': 0}),
        xbmcgui.ListItem('All'),
        True
    )
    listItems = (
        (
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': sectionName, 'page': 0}),
            xbmcgui.ListItem(sectionName),
            True
        )
        for sectionName in sorted(catalog.iterkeys()) if len(catalog[sectionName][0]) > 0
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), (sectionAll,) + tuple(listItems))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    # Always use InfoWall mode (assuming it's Estuary skin, the default skin), in this directory
    # as it makes it easier to pick a catalog section.
    xbmc.executebuiltin('Container.SetViewMode(54)')


def viewCatalogSection(params):
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')
    catalog = getCatalogProperty(params)

    def _catalogSectionItems(iterable):
        api = int(params['api'])
        if ADDON_SHOW_THUMBS:

            requestHelper.setAPISource(api) # Set the API base URL (and headers) to retrieve the thumb URLs.

            for entry in iterable:
                # entry = (id, name, description)
                thumb = requestHelper.makeThumbURL(entry[0])
                item = xbmcgui.ListItem(entry[1])
                setupListItem(
                    item, entry[1], entry[1], isPlayable = False, season = 0, episode = 0, thumb = thumb, plot = entry[2]
                )
                yield (
                    buildURL({'view': 'LIST_EPISODES', 'api': api, 'id': entry[0], 'thumbURL': thumb, 'plot': entry[2]}),
                    item,
                    True
                )
        else:
            for entry in iterable:
                item = xbmcgui.ListItem(entry[1])
                setupListItem(
                    item, entry[1], entry[1], isPlayable = False, season = 0, episode = 0, thumb = '', plot = entry[2]
                )
                yield (
                    buildURL({'view': 'LIST_EPISODES', 'api': api, 'id': entry[0], 'plot': entry[2]}),
                    item,
                    True
                )

    sectionName = params['section']

    if ADDON_SHOW_THUMBS:
        # Display items in pages so the thumbs are loaded in chunks to not overburden the source website.
        page = int(params['page']) # Zero-based index.
        if sectionName == 'ALL':
            # Create pages for the pseudo-section "ALL":
            # Flatten all sections into a list, then flatten all pages into
            # another list, which is then isliced to get the current directory page.
            start = page * CATALOG_PAGE_SIZE
            stop = start + CATALOG_PAGE_SIZE
            flatSections = chain.from_iterable(catalog[sName] for sName in sorted(catalog.iterkeys()))
            itemsIterable = (
                entry for entry in (pageEntry for pageEntry in islice(chain.from_iterable(flatSections), start, stop))
            )
            totalSectionPages = sum(len(page) for page in chain.from_iterable(catalog.itervalues())) // CATALOG_PAGE_SIZE
        else:
            # Use one of the premade pages.
            itemsIterable = (entry for entry in catalog[sectionName][page])
            totalSectionPages = len(catalog[sectionName])

        page += 1
        if totalSectionPages > 1 and page < totalSectionPages:
            params.update({'page':page})
            nextPage = (buildURL(params), xbmcgui.ListItem('Next Page ('+str(page+1)+'/'+str(totalSectionPages)+')'), True)
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)) + (nextPage,))
        else:
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))
    else:
        if sectionName == 'ALL':
            allSections = chain.from_iterable(catalog[sName] for sName in sorted(catalog.iterkeys()))
            itemsIterable = (entry for page in allSections for entry in page)
        else:
            allPages = chain.from_iterable(page for page in catalog[sectionName])
            itemsIterable = (entry for entry in allPages)
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    if ADDON_USE_GRID:
        xbmc.executebuiltin('Container.SetViewMode(54)')


def viewListEpisodes(params):
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')

    requestHelper.setAPISource(int(params['api']))
    jsonData = requestHelper.routeGET('/GetDetails/' + params['id'])

    def _listEpisodesItems(data):
        episodes = data['episode'] if 'episode' in data else data['episodes']
        api = params['api']
        plot = params['plot']
        thumb = params.get('thumbURL', '')
        for episodeEntry in episodes:
            #episode = dict( id=str, name=str, date='yyyy-MM-dd (...)' )
            name = episodeEntry['name']
            item = xbmcgui.ListItem(name)
            season, episode = getTitleInfo(name)
            showTitle = data.get('name', name) # Try the entry title first, then episode name if it fails.
            setupListItem(item, showTitle, name, True, season, episode, thumb, plot)
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
                        'thumb': thumb,
                        'plot': plot
                    }
                ),
                item,
                False
            )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_listEpisodesItems(jsonData)))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def resolve(params):

    def _getStreamURLs(providerURLs):
        # This function will get a list of URLs, one list per provider.
        firstURL = providerURLs[0]
        if firstURL.startswith('http://'):
            providerName = firstURL.replace('http://','').split('.')[0]
        elif firstURL.startswith('https://'):
            providerName = firstURL.replace('https://','').split('.')[0]

        if providerName in UNSUPPORTED_PROVIDERS:
            return (providerName, [ ])

        # It's usually a single provider url, but there might be more urls for
        # the same provider for entries like movies, which are split in parts.
        streamURLs = [ ]
        for url in providerURLs:
            startTime = time()

            anyQualityURL = None
            if providerName in SUPPORTED_PROVIDERS:
                r = requestHelper.GET(url)
                if r.ok:
                    html = r.text
                    if 'var video_links =' in html:
                        # Try the videozoo \ play44 solve:
                        temp = re.findall(r'video_links\s*=\s*({.*?}\s*\s*}\s*);', r.text, re.DOTALL)
                        if temp:
                            sourceData = json.loads(temp[0])
                            anyQualityURL = sourceData[next(iter(sourceData))]['storage'][0]['link']
                    elif 'url: \'' in html:
                        # Try the playpanda.net solve:
                        temp = re.findall(r'{\s*?url\s*?:\s*?\'(.*?)\'', r.text, re.DOTALL)
                        if temp:
                            anyQualityURL = temp[0]
                    elif 'file: "' in html:
                        # Try a generic solve:
                        temp = re.findall(r'file:\s*?"(.*?)"', r.text, re.DOTALL)
                        if temp:
                            anyQualityURL = temp[0]
            if anyQualityURL:
                streamURLs.append(anyQualityURL)

            elapsed = time() - startTime
            if elapsed < API_REQUEST_DELAY:
                xbmc.sleep(int(max(API_REQUEST_DELAY - elapsed, 100))) # In milliseconds.

        # Uncomment the next two lines for debug.
        #if not streamURLs:
        #    xbmc.log('Toonmania2 --- Failed resolving provider: '+providerName+' '+str(providerURLs), xbmc.LOGWARNING)
        return (providerName, streamURLs)

    requestHelper.setAPISource(int(params['api']))

    jsonData = requestHelper.routeGET('/GetVideos/' + params['episodeID'])
    if jsonData:
        if isinstance(jsonData[0], dict): # Animeplus special case, providerURLs come as dictionaries.
            providers = (_getStreamURLs( (provider['url'],) ) for provider in jsonData)
        else:
            providers = (_getStreamURLs(providerURLs) for providerURLs in jsonData)
        validProviders = tuple(provider for provider in providers if len(provider[1]))
    else:
        return

    if len(validProviders):

        item = xbmcgui.ListItem(params['name'])
        setupListItem(
            item,
            params['showTitle'],
            params['name'],
            True,
            int(params['season']),
            int(params['episode']),
            params.get('thumb', ''),
            params['plot']
        )
        selectedIndex = xbmcgui.Dialog().select('Select Provider', tuple(provider[0] for provider in validProviders))
        if selectedIndex != -1:
            # See if the provider has more than one stream url so we need to set up a playlist.
            streamURLs = validProviders[selectedIndex][1] # [0] = providerName, [1] = provider URL(s).
            if len(streamURLs) > 1:
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                playlist.clear()
                for stream in streamURLs[1:]:
                    playlist.add(stream)
                xbmc.Player().play(playlist, listitem = item) # Does NOT work for some reason.
            else:
                item.setPath(streamURLs[0])
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)


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
    'RESOLVE': resolve
}


def main():
    params = {key: value[0] for key, value in parse_qs(sys.argv[2][1:]).iteritems()}
    VIEW_FUNCS[params.get('view', 'MENU')](params)