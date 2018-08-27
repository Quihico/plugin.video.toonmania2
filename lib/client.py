# -*- coding: utf-8 -*-
import re
import sys
from itertools import chain, islice
try:
    # Python 2.7
    from urlparse import parse_qs
    from urllib import urlencode
except ImportError:
    # Python 3
    from urllib.parse import parse_qs, urlencode

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from lib.common import (
    setWindowProperty,
    getWindowProperty,
    setRawWindowProperty,
    getRawWindowProperty
)
#from lib.simple_tvdb import tvdb # Unused. Potentially get per-episode thumbnails and descriptions in the future.
#from lib.simple_cache import cache # Unused for now. A cache helper to spare the website from excessive requests...
from lib.request_helper import requestHelper
from lib.catalog_helper import catalogHelper

# Addon user settings.
addon = xbmcaddon.Addon()
ADDON_SHOW_THUMBS = addon.getSetting('show_thumbnails') == 'true'
ADDON_PAGE_SIZE = int(addon.getSetting('page_size')) # Page size = number of items per catalog section page.
ADDON_USE_GRID = addon.getSetting('use_grid') == 'true'

# Used to help organise provider streams.
class Provider:
    def __init__(self, newName = '', newStreams = [ ]):
        self.name = newName
        self.streams = newStreams

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
    '''
    Directory for the main add-on menu.
    '''
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
    '''
    View that pops-up the add-on settings dialog, for convenience.
    '''
    addon.openSettings() # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    # So it's a good time to update the globals.
    ADDON_SHOW_THUMBS = addon.getSetting('show_thumbnails') == 'true'
    ADDON_PAGE_SIZE = int(addon.getSetting('page_size'))
    ADDON_USE_GRID = addon.getSetting('use_grid') == 'true'


def viewAnimetoonMenu(params):
    '''
    Directory for the Animetoon website.
    Represents http://www.animetoon.org
    '''
    def _animetoonItem(view, color, title, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        item.setInfo( 'video', {'title': title, 'plot': title})
        return (buildURL({'view': view, 'api': requestHelper.API_ANIMETOON, 'route': route}), item, True)

    listItems = (
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
    '''
    Directory for the Animeplus website.
    Represents http://www.animeplus.tv
    '''
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


def viewSearchMenu(params):
    '''
    Directory for a sub menu that lists search options.
    Used by both APIs.
    '''
    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if params.get('route', '') == '_inputSearch':
        text = _modalKeyboard('Search by Name')
        if text:
            params.update({'view': 'CATALOG_MENU', 'route': '_executeSearch', 'query': text})
            viewCatalogMenu(params) # Send the search query for the catalog functions to use.
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


def viewSearchGenre(params):
    '''
    Directory for a sub menu that lists the available genres to filter items by.
    '''
    api = params['api']
    route = params['route']

    # Cache the genre names, because if you hit "Back" Kodi will reload this directory
    # and do a redundant website request... This property is only used within this function.
    if api == requestHelper.API_ANIMETOON:
        _PROPERTY_GENRE_NAMES = 'toonmania2.toonGenres'
    else:
        _PROPERTY_GENRE_NAMES = 'toonmania2.plusGenres'

    genreList = getRawWindowProperty(_PROPERTY_GENRE_NAMES)
    if genreList:
        genreList = genreList.split(',')
    else:
        # The data from the '/GetGenres/' route is a dict with a list of genre names like "Action",
        # "Comedy" etc., but it also has some weird texts in the list probably from data-entry errors.
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        genreList = requestHelper.routeGET(route).get('genres', [ ])
        requestHelper.delayEnd()
        setRawWindowProperty(_PROPERTY_GENRE_NAMES, ','.join(genreList))

    listItems = (
        (
            buildURL({'view': 'CATALOG_MENU', 'api': api, 'route': route, 'genreName': genreName}),
            xbmcgui.ListItem(genreName),
            True
        )
        for genreName in genreList
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(listItems))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def getTitleInfo(title):
    '''
    Helper function to extract season and episode values based on the title string.
    It looks for patterns such as "[Show name] Season 2 Episode 5".
    '''
    season = episode = 0
    titleWords = title.lower().split()
    for index, word in enumerate(titleWords):
        if word == 'season':
            try:
                season = int(titleWords[index+1])
            except ValueError:
                pass
        elif word == 'episode':
            try:
                episode = int(titleWords[index+1])
                if not season:
                    season = 1 # Season may be omitted in the title.
                break # The word 'Episode' is always put after the season and show title in the link strings.
            except ValueError:
                season = episode = 0 # Malformed \ typo'ed strings caused this?
    return (season, episode)


def setupListItem(item, showTitle, title, isPlayable, season, episode, genres, thumb = '', plot = '', date = ''):
    '''
    Helper function to fill in an xbmcgui.ListItem item with metadata info, supplied in the parameters.
    'genres' might be empty or None.
    '''
    if isPlayable:
        # Allows the checkmark to be placed on watched episodes, as well as some context menu options.
        item.setProperty('IsPlayable', 'true')

    if thumb:
        item.setArt({'icon': thumb, 'thumb': thumb, 'poster': thumb})

    # All items are set with 'episode' mediatype even if they aren't, as it looks better w/ the skin layout.
    itemInfo = {
        'mediatype': 'episode' if isPlayable else 'tvshow',
        'tvshowtitle': showTitle,
        'title': title,
        'plot': plot,
        'genre': genres if genres else '',
        'premiered': date, # According to the docs, 'premiered' is what makes Kodi display a date.
        'aired': date,
        'year': date.split('-')[0]
    }
    if episode:
        itemInfo.update({'season': season, 'episode': episode})
    item.setInfo('video', itemInfo)


def viewCatalogMenu(params):
    '''
    Directory for the catalog main menu, showing sections #, A, B, C, D, E... etc.
    The content of the catalog varies depending on the API and route the user chose.
    Empty sections are hidden.
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')

    catalog = catalogHelper.getCatalog(params)
    api = params['api']
    route = params['route']

    listItems = tuple(
        (
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': sectionName, 'page': '0'}),
            xbmcgui.ListItem(sectionName),
            True
        )
        for sectionName in sorted(catalog.iterkeys()) if len(catalog[sectionName]) > 0
    )
    if len(listItems):
        # If the catalog has any items at all, add an "ALL" pseudo-section.
        sectionAll = (
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': 'ALL', 'page': '0'}),
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
    '''
    Directory for listing items from a specific section of the catalog
    (section "C" for example, for C-titled entries).
    '''
    if ADDON_USE_GRID:
        xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')

    catalog = catalogHelper.getCatalog(params)

    def _catalogSectionItems(iterable):
        api = params['api']
        
        if ADDON_SHOW_THUMBS:
            requestHelper.setAPISource(api) # Sets the right base thumb URL for the makeThumbURL() below.

        for entry in iterable:
            # entry = (id, name, description, genres, dateReleased), see CatalogHelper.makeCatalogEntry() for more info.
            item = xbmcgui.ListItem(entry[1])
            thumb = requestHelper.makeThumbURL(entry[0]) if ADDON_SHOW_THUMBS else ''
            date = entry[4]
            setupListItem(item, entry[1], entry[1], False, 0, 0, entry[3], thumb = thumb, plot = entry[2], date = date)
            yield (
                buildURL(
                    {
                        'view': 'LIST_EPISODES',
                        'api': api,
                        'id': entry[0],
                        'genres': ','.join(entry[3]) if entry[3] else '',
                        'thumb': thumb,
                        'plot': entry[2],
                        'date': date
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
            # Flatten all sections into an iterable, which is then islice'd to get the current directory page.
            flatSections = chain.from_iterable(catalog[sName] for sName in sorted(catalog.iterkeys()))
            itemsIterable = (entry for entry in islice(flatSections, start, stop))
            totalSectionPages = sum(len(section) for section in catalog.itervalues()) // ADDON_PAGE_SIZE
        else:
            # Do an islice of a specific section.
            itemsIterable = (entry for entry in islice(catalog[sectionName], start, stop))
            totalSectionPages = len(catalog[sectionName]) // ADDON_PAGE_SIZE

        page += 1
        if totalSectionPages > 1 and page < totalSectionPages:
            params.update({'page':str(page)})
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


def resolveEpisodeStreams(api, episodeID):
    '''
    Helper function that requests the video host URLs for an episode ID and
    resolves these to playable media URLs for Kodi.
    :returns: An iterable of 'Provider' objects with at least 1 stream each.
    '''
    requestHelper.setAPISource(api)
    requestHelper.delayBegin()
    jsonData = requestHelper.routeGET('/GetVideos/' + episodeID)
    requestHelper.delayEnd(500)

    if not jsonData:
        return

    if isinstance(jsonData[0], dict):
        # Special-case for animeplus, URLs might come inside one dictionary each provider.
        providerURLs = (providerURL['url'] for providerURL in jsonData)
    elif isinstance(jsonData[0], list):
        # Or the JSON data is a list of lists (sometimes w/ mixed providers in the same list...).
        providerURLs = (url for urlList in jsonData for url in urlList)
    else:
        providerURLs = jsonData # A list of single providers?

    # Assume the providers listed in the for the show\movie will all have the same host name variant.
    # Assume the video parts of the same provider will be in order (eg. easyvideo part 1, easyvideo part 2 etc.).
    resolvedProviders = { }
    for url in providerURLs:
        # Try to get the provider name from the URL (to see if we support resolving it).
        if url.startswith('http://'):
            tempURL = url.replace('http://', '')
        elif url.startswith('https://'):
            tempURL = url.replace('https://', '')

        for word in tempURL.split('.'):
            if word in SUPPORTED_PROVIDERS:
                providerName = word
                break # We found the provider name in its URL.
        else:
            # This wasn't a supported provider.
            continue

        if providerName not in resolvedProviders:
            resolvedProviders[providerName] = [ ] # Initialise a media list for this specific provider.

        try:
            temp = None

            requestHelper.delayBegin()
            r = requestHelper.GET(url)
            if r.ok:
                html = r.text
                if 'var video_links' in html:
                    # Try the generic videozoo \ play44 resolve first:
                    temp = re.findall(r'''var video_links.*?['"]link['"]\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                else:
                    # Try variants:
                    temp = re.findall(r'''{\s*?url\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                    if not temp:
                        temp = re.findall(r'''file\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                if temp:
                    stream = temp[0].replace(r'\/', r'/') # Unescape the found URL in case there's escaped JS slashes.
                    # Only append stream if not already in the list (sometimes there's duplicate streams...)
                    if stream not in resolvedProviders[providerName]:
                        resolvedProviders[providerName].append(stream)
            requestHelper.delayEnd(500) # Sleep this thread a little before the next request, if necessary.

        except:
            pass

    # Final filtering.
    for providerName, urls in resolvedProviders.iteritems():
        if urls:
            yield Provider(providerName, urls) # Only yield identified providers that have at least one stream.
        else:
            # Uncomment the next line to debug failed providers.
            #xbmc.log('Toonmania2 --- Failed resolving provider: '+providerName+' '+str(jsonData), xbmc.LOGWARNING)
            pass


def _makeEpisodeItems(api, episodes, showTitle, showGenres, showThumb, showPlot, showDate):
    '''
    Converts a list of JSON episode entries into a list of playable xbmcgui.ListItem
    with their 'view' url parameter set to 'RESOLVE'.
    This function is used only by viewListEpisodes() and _tryListItemParts().

    :param episodes: List of JSON episodes from the APIs '/GetDetails/' routes.
    :param p(...): Generic parameters from the parent show \ movie, inherited by the episodes.
    '''
    for episodeEntry in episodes:
        #episode = dict( id=str, name=str, date=str='yyyy-MM-dd (...)' )
        name = episodeEntry['name']
        item = xbmcgui.ListItem(name)
        # While the parent show\movie data uses 'released' as key for date value (value is 'yyyy-MM-dd'),
        # episode data uses 'date' as key for date value (value is 'yyyy-MM-dd hh:mm:ss').
        # The slice [:10] gets the length of 'yyyy-MM-dd'.
        episodeDate = episodeEntry['date'][ : 10] if 'date' in episodeEntry else showDate
        season, episode = getTitleInfo(name)
        tempShowTitle = showTitle if showTitle else name # Try the show title first, fallback to episode name if empty.
        setupListItem(item, tempShowTitle, name, True, season, episode, showGenres, showThumb, showPlot, episodeDate)
        yield (
            buildURL(
                {
                    'view': 'RESOLVE',
                    'api': api,
                    'episodeID': episodeEntry['id'],
                    'showTitle': showTitle,
                    'name': name,
                    'season': str(season),
                    'episode': str(episode),
                    'genres': ','.join(showGenres),
                    'thumb': showThumb,
                    'plot': showPlot,
                    'date': episodeDate
                }
            ),
            item,
            False
        )


def viewListEpisodes(params):
    '''
    Directory for the list of episodes from a show.
    This is the last directory before playing a video.
    Pages aren't necessary in here if the thumbnails setting is on because
    for now all episodes use the same thumb and plot, inherited from the show.
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes') # Changes the skin layout.

    # Optional, sort episode list by labels.
    #xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    api = params['api']
    showID = params['id']
    # Internal properties to cache the last episode list view.
    # Otherwise Kodi requests it again after you stop watching a video.
    _PROPERTY_LAST_API_ID = 'toonmania2.lastAPI_ID'
    _PROPERTY_EPISODE_DETAILS = 'toonmania2.lastEpDetails'
    
    jsonData = None
    lastShowAPI_ID = getRawWindowProperty(_PROPERTY_LAST_API_ID)
    if lastShowAPI_ID == api + showID:
        jsonData = getWindowProperty(_PROPERTY_EPISODE_DETAILS)
    
    if not jsonData:
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        jsonData = requestHelper.routeGET('/GetDetails/' + showID)
        requestHelper.delayEnd()
        setRawWindowProperty(_PROPERTY_LAST_API_ID, api + showID)
        setWindowProperty(_PROPERTY_EPISODE_DETAILS, jsonData)

    # Genres, thumb and plot are taken from the parent show \ movie.
    # But the date of the parent show \ movie will only be used if the individual episode doesn't have a date itself.
    showTitle = jsonData.get('name', '')
    showGenres = params['genres'].split(',')
    showThumb = params.get('thumb', '') # Might be empty in case ADDON_SHOW_THUMBS is off.
    showPlot = params['plot']
    showDate = params['date']

    if len(jsonData['episode']) > 1:
        xbmcplugin.addDirectoryItems(
            int(sys.argv[1]),
            tuple(_makeEpisodeItems(api, jsonData['episode'], showTitle, showGenres, showThumb, showPlot, showDate))
        )
    else:
        # This is probably a movie, OVA or special.
        # Try to resolve the providers and their streams in here and list them as video part items.
        episodeEntry = jsonData['episode'][0]
        validProviders = tuple(resolveEpisodeStreams(api, episodeEntry['id']))
        if validProviders:
            # Sum 1 for every provider that has more than one stream, otherwise 0 if all are single stream.
            hasMultipleParts = sum(0 if len(provider.streams) == 1 else 1 for provider in validProviders)
            if hasMultipleParts:
                def _listParts(): # Similar logic to _makeEpisodeItems(), but for the same item and multiple streams.
                    name = episodeEntry['name']
                    season, episode = getTitleInfo(name)
                    date = episodeEntry['date'][:10] if 'date' in episodeEntry else showDate
                    for provider in validProviders:
                        for index, stream in enumerate(provider.streams, 1):
                            partName = name + ' | PART ' + str(index)
                            li = xbmcgui.ListItem(
                                '[COLOR lavender][B]%s[/B][/COLOR] | %s' % (provider.name.upper(), partName)
                            )
                            li.setPath(stream)
                            setupListItem(li, showTitle, partName, True, season, episode, showGenres, showThumb, showPlot, date)
                            yield (stream, li, False)
                xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_listParts()))
            else:
                # The item doesn't have multiple video parts.
                # List the single item as usual, but send the already resolved
                # providers in the URL parameters (so they don't have to be resolved again).
                dirItem = next(_makeEpisodeItems(api, (episodeEntry,), showTitle, showGenres, showThumb, showPlot, showDate))
                providersDict = {'p'+str(index) : '%s_%s' % (p.name, p.streams[0]) for index, p in enumerate(validProviders)}
                newUrl = dirItem[0] + '&' + urlencode(providersDict) # Inject the resolved providers into the directory item URL.
                xbmcplugin.addDirectoryItem(int(sys.argv[1]), newUrl, dirItem[1], False)
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification('Toonmania2', 'Could not find any stream URLs', xbmcgui.NOTIFICATION_INFO, 2500, False)

    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def viewResolve(params):
    '''
    Resolves and plays the chosen episode, based on the API and ID supplied in 'params'.
    '''
    if 'p0' in params:
        # This was a multi-video-part item, and it was already resolved by viewListEpisodes().
        # Each 'pn' key leads to a 'providerName_providerURL' value. Split at the first underscore.
        def _readProviders():
            index = 0; key = 'p0'
            while key in params:
                temp = params[key]
                uIndex = temp.find('_')
                provider = Provider(temp[:uIndex], [temp[uIndex+1:]]) # Name and single stream.
                index += 1
                key = 'p'+str(index)
                yield provider
        validProviders = tuple(_readProviders())
    else:
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
            params.get('genres', '').split(','),
            params.get('thumb', ''),
            params['plot'],
            params['date']
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
    '''
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted URL string.
    '''
    return (sys.argv[0] + '?' + urlencode({k: v.encode('utf-8') if isinstance(v, unicode)
                                           else unicode(v, errors='replace').encode('utf-8')
                                           for k, v in query.iteritems()}))


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
    'RESOLVE': viewResolve
}


def main():
    '''
    Main add-on routing function, it selects and shows an add-on directory.
    Uses the global VIEW_FUNCS dictionary.
    '''
    params = {key: value[0] for key, value in parse_qs(sys.argv[2][1:]).iteritems()}
    VIEW_FUNCS[params.get('view', 'MENU')](params)