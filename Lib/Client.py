# -*- coding: utf-8 -*-
import re
import sys
from math import ceil
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

#from Lib.SimpleTVDB import tvdb # Unused. Potentially get per-episode thumbnails and descriptions in the future.
from Lib.SimpleCache import cache
from Lib.RequestHelper import requestHelper
from Lib.CatalogHelper import catalogHelper

# Addon user settings. See also viewSettings() and reloadSettings().
ADDON = xbmcaddon.Addon()
ADDON_SETTINGS = dict()

# Dict to help translate 'layout_type_[name]' settings values into 'Container.SetViewMode()' values.
# These names and numbers were taken from the Estuary skin XML files:
# https://github.com/xbmc/xbmc/tree/master/addons/skin.estuary/xml
ADDON_VIEW_MODES = {
    'Wall' : '500',
    'Banner': '501',
    'List' : '50',
    'Poster' : '51',
    'Shift' : '53',
    'InfoWall' : '54',
    'WideList' : '55'
}


def viewMenu(params):
    '''
    Directory for the main add-on menu.
    '''
    cache.saveCacheIfDirty()

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
    ADDON.openSettings() # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    reloadSettings() # So right after it is a good time to update the globals.


def viewClearCache(params):
    if cache.clearCacheFile():
        dialog = xbmcgui.Dialog()
        dialog.notification('Toonmania2', 'Cache file cleared', xbmcgui.NOTIFICATION_INFO, 4000, True)

    # Close the settings dialog when it was opened from within this add-on.        
    if 'toonmania2' in xbmc.getInfoLabel('Container.PluginName'):
        xbmc.executebuiltin('Dialog.Close(all)')
    
    
def viewAnimetoonMenu(params):
    '''
    Directory for the Animetoon website.
    Represents http://www.animetoon.org
    '''
    def _animetoonItem(view, color, title, route):
        item = xbmcgui.ListItem('[B][COLOR %s]%s[/COLOR][/B]' % (color, title))
        item.setInfo( 'video', {'title': title, 'plot': title})
        return (buildURL({'view': view, 'api': requestHelper.API_ANIMETOON, 'route': route}), item, True)

    cache.saveCacheIfDirty()

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

    cache.saveCacheIfDirty()

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


def _viewSearchResults(params, text):
    '''
    Sub directory as an intermediary step before showing the search results catalog.
    This lets you favourite your search results so you can come back to them later.
    '''
    searchResults = tuple(catalogHelper.nameSearchEntries(params['api'], text)) # Does the actual web requests.
    if searchResults:
        # Use a comma-separated list of the result show\movie IDs as parameter.
        # See CatalogHelper.makeCatalogEntry() for info on catalog entry structure.
        searchIDs = ','.join(entryID for entryID in searchResults)
        
        # Go straight to the 'ALL' catalog section instead of the main catalog menu, because the name search
        # results are usually fewer so it's more convenient.
        # *** The API should be kept the same as the one used in the search. ***
        params.update(
            {'view': 'CATALOG_SECTION', 'section': 'ALL', 'page': '0', 'route': '_searchResults', 'searchIDs': searchIDs}
        )
        from string import capwords
        item = xbmcgui.ListItem('[COLOR orange][B]' + capwords(text) + '[/COLOR][/B] Search Results')
        item.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), buildURL(params), item, True)
    else:
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem('No Items Found'), False)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
    
    # Use the same layout settings as the main catalog menu.    
    useCatalogLayout, layoutType = ADDON_SETTINGS['layoutCatalog']
    if useCatalogLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def viewSearchMenu(params):
    '''
    Directory for a menu that lists search options.
    Used by both APIs.
    '''
    def _modalKeyboard(heading):
        kb = xbmc.Keyboard('', heading)
        kb.doModal()
        return kb.getText() if kb.isConfirmed() else ''

    if params.get('route', None) == '_inputSearch':
        text = _modalKeyboard('Search by Name')
        if text:
            _viewSearchResults(params, text) # Sub directory that executes the search and shows results.
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
    The genre list is cached memory-only to last a Kodi session. This is done because
    if you hit "Back" Kodi will reload this directory and do a redundant web
    request...
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows') # Optional, influences the skin layout.

    api = params['api']
    route = params['route']

    if api == requestHelper.API_ANIMETOON:
        _PROPERTY_GENRE_NAMES = 'tmania2.prop.toonGenres'
    else:
        _PROPERTY_GENRE_NAMES = 'tmania2.prop.plusGenres'
        
    genreList = cache.getCacheProperty(_PROPERTY_GENRE_NAMES, readFromDisk = True)
    if not genreList:
        # The data from the '/GetGenres/' route is a dict with a list of genre names like "Action",
        # "Comedy" etc., but it also has some weird texts in the list probably from data entry errors.
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        genreList = requestHelper.routeGET(route).get('genres', [ ])
        requestHelper.delayEnd()
        # Store the current API genres in a disk-persistent property with the default lifetime of 1 week.
        cache.setCacheProperty(_PROPERTY_GENRE_NAMES, genreList, saveToDisk = True, lifetime = cache.LIFETIME_ONE_WEEK)

    listItems = (
        (
            buildURL({'view': 'CATALOG_MENU', 'api': api, 'route': route, 'genreName': genreName}),
            xbmcgui.ListItem(genreName),
            True
        )
        for genreName in genreList
    )
    xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(listItems))
    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc = False)

    useCatalogLayout, layoutType = ADDON_SETTINGS['layoutCatalog']
    if useCatalogLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


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
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': sectionKey, 'page': '0'}),
            xbmcgui.ListItem(sectionKey),
            True
        )
        for sectionKey in sorted(catalog.iterkeys()) if len(catalog[sectionKey]) > 0
    )

    if len(listItems):
        sectionAll = ( # If the catalog has any items at all, add an "ALL" pseudo-section.
            buildURL({'view': 'CATALOG_SECTION', 'api': api, 'route': route, 'section': 'ALL', 'page': '0'}),
            xbmcgui.ListItem('All'),
            True
        )
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), (sectionAll,) + listItems)
    else:
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem('No Items Found'), False)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

    # Custom layout settings.
    useCatalogLayout, layoutType = ADDON_SETTINGS['layoutCatalog']
    if useCatalogLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def viewCatalogSection(params):
    '''
    Directory for listing items from a specific section of the catalog
    (section "C" for example, for C-titled entries).
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows')

    catalog = catalogHelper.getCatalog(params)
    
    # Special-case when coming in from a search results folder (usually from a Favourite),
    # it's a nice moment to save the cache, if necessary.
    if 'searchIDs' in params:
        cache.saveCacheIfDirty()        

    def _catalogSectionItems(iterable):
        api = params['api']

        if ADDON_SETTINGS['showThumbs']:
            requestHelper.setAPISource(api) # Sets the right base thumb URL for the makeThumbURL() below.

        for entry in iterable:
            # entry = (id, name, description, genres, dateReleased), see CatalogHelper.makeCatalogEntry() for more info.
            item = xbmcgui.ListItem(entry[1])
            thumb = requestHelper.makeThumbURL(entry[0]) if ADDON_SETTINGS['showThumbs'] else ''
            date = entry[4] if entry[4] else ''
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

    sectionKey = params['section']

    if ADDON_SETTINGS['showThumbs']:
        # Display items in pages so the thumbs are loaded in chunks to not overburden the source website.

        page = int(params['page']) # Zero-based index.
        pageSize = ADDON_SETTINGS['pageSize']
        start = page * pageSize
        stop = start + pageSize

        if sectionKey == 'ALL':
            # Create pages for the pseudo-section "ALL":
            # Flatten all sections into an iterable, which is then islice'd to get the current directory page.
            flatSections = chain.from_iterable(catalog[sectionKey] for sectionKey in sorted(catalog.iterkeys()))
            itemsIterable = (entry for entry in islice(flatSections, start, stop))
            totalSectionPages = int(ceil(sum(len(section) for section in catalog.itervalues()) / float(pageSize)))
        else:
            # Do an islice of a specific section.
            itemsIterable = (entry for entry in islice(catalog[sectionKey], start, stop))
            totalSectionPages = int(ceil(len(catalog[sectionKey]) / float(pageSize))) # The 'float' is for Python 2.

        page += 1
        if totalSectionPages > 1 and page < totalSectionPages:
            params.update({'page':str(page)})
            nextPage = (buildURL(params), xbmcgui.ListItem('Next Page ('+str(page+1)+'/'+str(totalSectionPages)+')'), True)
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)) + (nextPage,))
        else:
            xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
            xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))
    else:
        if sectionKey == 'ALL':
            itemsIterable = (
                entry for entry in chain.from_iterable(catalog[sectionKey] for sectionKey in sorted(catalog.iterkeys()))
            )
        else:
            itemsIterable = (entry for entry in catalog[sectionKey])
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        xbmcplugin.addDirectoryItems(int(sys.argv[1]), tuple(_catalogSectionItems(itemsIterable)))

    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc = False)

    # Custom layout.
    useShowsLayout, layoutType = ADDON_SETTINGS['layoutShows']
    if useShowsLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def getEpisodeStreams(api, episodeID):
    '''
    Helper function to retrieve a list of direct streams from an episode \ movie ID.
    Streams from the '?direct' route are a list of lists of sources (dicts):
    streams = [
        [ {source for part1}, {alternative source for part1} ], [ {source for part2}, {...} ]
    ]
    The sublist is for different sources of the same part (the source might be from 'storage'
    or 'picasa' for example).
    '''
    requestHelper.setAPISource(api)
    requestHelper.delayBegin()
    jsonData = requestHelper.routeGET('/GetVideos/' + episodeID + '?direct')
    requestHelper.delayEnd(1000)

    if jsonData:
        episodeStreams = [ ]
        for part in jsonData:
            for source in part:
                if source['source'] == 'storage':
                    episodeStreams.append(source['link'])
                    break
            else:
                episodeStreams.append(part[0]['link']) # If there's no 'storage' type source, use any other source.
        return episodeStreams
    else:
        # Return any list of streams, no matter the provider.
        # They usually resolve to the same host, "gateway.play44.net".
        from Lib.Providers import resolveEpisodeProviders
        resolvedProviders = resolveEpisodeProviders(api, episodeID)
        return resolvedProviders[0] if resolvedProviders else None


def _makeEpisodeItems(api, episodes, showTitle, showGenres, showThumb, showPlot, showDate):
    '''
    Converts a list of JSON episode entries into a list of playable xbmcgui.ListItem
    with their 'view' url parameter set to 'RESOLVE'.
    This function is used only by viewListEpisodes().

    :param episodes: List of JSON episodes from the '/GetDetails/' routes of the APIs.
    :param p(...): Generic parameters from the parent show \ movie, inherited by the episodes.
    '''
    for episodeEntry in episodes:
        #episode = dict( id=str, name=str, date=str='yyyy-MM-dd (...)' )
        name = episodeEntry['name']
        item = xbmcgui.ListItem(name)
        season, episode = getTitleInfo(name)
        # While the parent show\movie data uses 'released' as key for date value (value is 'yyyy-MM-dd'),
        # episode data uses 'date' as key for date value (value is 'yyyy-MM-dd hh:mm:ss').
        # The slice [:10] gets the length of 'yyyy-MM-dd'.
        episodeDate = episodeEntry['date'][ : 10] if 'date' in episodeEntry else showDate
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


def _makeEpisodePartItems(episodeEntry, streams, showTitle, showGenres, showThumb, showPlot, showDate):
    '''
    Similar logic to _makeEpisodeItems(), but it works on just one item with multiple streams.
    This will make one (repeated) xbmc.ListItem for the several parts, each part points to a stream.
    '''
    episodeName = episodeEntry['name']
    season, episode = getTitleInfo(episodeName)
    episodeDate = episodeEntry['date'][ : 10] if 'date' in episodeEntry else showDate
    for index, stream in enumerate(streams, 1):
        partName = episodeName + ' | [B]PART ' + str(index) + '[/B]'
        item = xbmcgui.ListItem(partName)
        setupListItem(item, showTitle, partName, True, season, episode, showGenres, showThumb, showPlot, episodeDate)
        yield (
            buildURL(
                {
                    'view': 'RESOLVE',
                    'showTitle': showTitle,
                    'name': partName, # The part name is set as the item label used to play it.
                    'season': str(season),
                    'episode': str(episode),
                    'genres': ','.join(showGenres),
                    'thumb': showThumb,
                    'plot': showPlot,
                    'date': episodeDate,
                    'stream': stream,
                }
            ),
            item,
            False
        )


def viewListEpisodes(params):
    '''
    Directory for the list of episodes from a show.
    This is the last directory before playing a video.
    Pages aren't necessary in here even if the thumbnails setting is on, because
    for now all episodes use the same thumb and plot, inherited from the show.
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')

    # Optional, sort episode list by labels.
    #xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    api = params['api']
    jsonData = None

    # Cache (memory-only) the episode list of the show, as the user might watch more than one in sequence.
    _PROPERTY_LAST_SHOW_DETAILS = 'tmania2.prop.lastDetails'
    lastShowDetails = cache.getCacheProperty(_PROPERTY_LAST_SHOW_DETAILS, readFromDisk = False)
    showKey = params['id'] + api
    if lastShowDetails and showKey in lastShowDetails:
        jsonData = lastShowDetails[showKey] # Use the show ID + API name as the unique identifier.
    if not jsonData:
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        jsonData = requestHelper.routeGET('/GetDetails/' + params['id'])
        if jsonData:
            cache.setCacheProperty(_PROPERTY_LAST_SHOW_DETAILS, {showKey: jsonData}, saveToDisk = False)
        requestHelper.delayEnd()

    # Genres, thumb and plot are taken from the parent show \ movie.
    # But the date of the parent show \ movie will only be used if the individual episode doesn't have a date itself.
    showTitle = jsonData.get('name', '')
    showGenres = params['genres'].split(',')
    showThumb = params.get('thumb', '') # Might be empty in case ADDON_SETTINGS['showThumbs'] is off.
    showPlot = params['plot']
    showDate = params.get('date', '')

    # If the JSON data for this show has more than one episode, list all the episodes as usual.
    if len(jsonData['episode']) > 1:
        xbmcplugin.addDirectoryItems(
            int(sys.argv[1]),
            tuple(_makeEpisodeItems(api, jsonData['episode'], showTitle, showGenres, showThumb, showPlot, showDate))
        )
    else:
        # For a single episode, this is probably a movie, OVA or special (considered as a "1 episode show").
        # Try to get the direct stream links to see if it's a movie (which are always multi-part).
        episodeEntry = jsonData['episode'][0]
        episodeStreams = None

        # Cache (memory-only) this request, as it might be for a multi part video (a movie)
        # where the user would go back and forth a lot on this view to watch all the movie parts.
        _PROPERTY_LAST_EPISODE_STREAMS = 'tmania2.prop.lastStreams'
        lastEpisodeStreams = cache.getCacheProperty(_PROPERTY_LAST_EPISODE_STREAMS, readFromDisk = False)
        episodeKey = episodeEntry['id'] + api
        if lastEpisodeStreams and episodeKey in lastEpisodeStreams:
            episodeStreams = lastEpisodeStreams[episodeKey]
        else:
            episodeStreams = getEpisodeStreams(api, episodeEntry['id'])
            if episodeStreams:
                cache.setCacheProperty(_PROPERTY_LAST_EPISODE_STREAMS, {episodeKey: episodeStreams}, saveToDisk = False)

        if episodeStreams:
            if len(episodeStreams) > 1:
                xbmcplugin.addDirectoryItems(
                    int(sys.argv[1]),
                    tuple(
                        _makeEpisodePartItems(
                            episodeEntry, episodeStreams, showTitle, showGenres, showThumb, showPlot, showDate
                        )
                    )
                )
            else:
                # The item doesn't have multiple video parts. List the single item as usual and send its stream
                # as a URL parameter so it doesn't have to be retrieved again in viewResolve().
                dirItem = next(_makeEpisodeItems(api, (episodeEntry,), showTitle, showGenres, showThumb, showPlot, showDate))
                newUrl = dirItem[0] + '&stream=' + urlencode(episodeStreams[0])
                xbmcplugin.addDirectoryItem(int(sys.argv[1]), newUrl, dirItem[1], False)
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification('Toonmania2', 'No streams found', xbmcgui.NOTIFICATION_INFO, 3000, False)
            xbmc.log(
                'Toonmania2 | No streams for API:%s SHOW:%s EPISODE:%s' % (params['api'], params['id'], episodeEntry['id']),
                xbmc.LOGWARNING
            )

    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc = False)

    # Custom layout.
    useEpisodeLayout, layoutType = ADDON_SETTINGS['layoutEpisodes']
    if useEpisodeLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def viewResolve(params):
    '''
    Resolves and plays the chosen episode, based on the API and ID supplied in 'params'.
    '''
    cache.saveCacheIfDirty() # Save the cache, only if necessary, before watching a video.

    # If the stream is already included in the parameters, no need to retrieve it in here again.
    if 'stream' in params:
        stream = params['stream']
    else:
         streams = getEpisodeStreams(params['api'], params['episodeID'])
         stream = streams[0] if streams else None
         
    if stream:
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
            params.get('date', '')
        )
        item.setPath(stream)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification('Toonmania2', 'No streams found', xbmcgui.NOTIFICATION_INFO, 3000, False)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem('None'))


def reloadSettings():
    global ADDON_SETTINGS
    ADDON_SETTINGS['showThumbs'] = ADDON.getSetting('show_thumbnails') == 'true'
    ADDON_SETTINGS['pageSize'] = int(ADDON.getSetting('page_size')) # Page size = number of items per catalog section page.
    # Layout settings, each category is a key to a (bool, layoutType) value, eg: 'layoutShows': (True, '55')
    for element in ('catalog', 'shows', 'episodes'):
        ADDON_SETTINGS['layout' + element.capitalize()] = (
            ADDON.getSetting('layout_use_' + element) == 'true',
            ADDON_VIEW_MODES.get(ADDON.getSetting('layout_type_' + element), '55')
        )


def getTitleInfo(title):
    '''
    Helper function to extract season and episode values based on the title string.
    It expects a pattern such as "[Show name] Season 2 Episode 5 [episode title]".
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
        #else:
            # Accumulate only the name words in here, if needed.
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
        'year': date.split('-')[0] if date else ''
    }
    if episode:
        itemInfo.update({'season': season, 'episode': episode})
    item.setInfo('video', itemInfo)


def buildURL(query):
    '''
    Helper function to build a Kodi xbmcgui.ListItem URL.
    :param query: Dictionary of url parameters to put in the URL.
    :returns: A formatted URL string.
    '''
    return (sys.argv[0] + '?' + urlencode({k: v.encode('utf-8') if isinstance(v, unicode)
                                           else unicode(v, errors='ignore').encode('utf-8')
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

    'CLEAR_CACHE': viewClearCache,
    'LIST_EPISODES': viewListEpisodes,
    'RESOLVE': viewResolve
}


# Global scope, initialises ADDON_SETTINGS.
reloadSettings()


def main():
    '''
    Main add-on routing function, it selects and shows an add-on directory.
    Uses the global VIEW_FUNCS dictionary.
    '''
    params = {key: value[0] for key, value in parse_qs(sys.argv[2][1:]).iteritems()}
    VIEW_FUNCS[params.get('view', 'MENU')](params)