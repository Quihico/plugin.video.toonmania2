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

from Lib.Common import (
    setWindowProperty,
    getWindowProperty,
    setRawWindowProperty,
    getRawWindowProperty
)
#from Lib.SimpleTVDB import tvdb # Unused. Potentially get per-episode thumbnails and descriptions in the future.
#from Lib.SimpleCache import cache # Unused for now. A cache helper to spare the website from excessive requests...
from Lib.RequestHelper import requestHelper
from Lib.CatalogHelper import catalogHelper

# Addon user settings. See also the viewSettings() function.
ADDON = xbmcaddon.Addon()
ADDON_SETTINGS = dict()

# Dict to help translate 'layout_type_[name]' settings values into 'Container.SetViewMode()' values.
# These constants were taken from the Estuary skin XML names:
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

# Dictionary of "mostly" supported providers, each key is a provider name, each value is a
# set of variant names for each provider. All these variants come up in the URLs...
SUPPORTED_PROVIDERS = {
    'VIDEOZOO.ME': set(('videozoo.me', 'videozoome', 'videozoo')),
    'PLAY44.NET': set(('play44.net', 'play44net', 'play44')),
    'EASYVIDEO.ME': set(('easyvideo.me', 'easyvideome', 'easyvideo')),
    'PLAYBB.ME': set(('playbb.me', 'playbbme', 'playbb')),
    'PLAYPANDA.NET': set(('playpanda.net', 'playpandanet', 'playpanda')),
    'VIDEOWING.ME': set(('videowing.me', 'videowingme', 'videowing'))
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
    ADDON.openSettings() # Modal dialog, so the program won't continue from this point until user closes\confirms it.
    # So it's a good time to update the globals.
    reloadAddonSettings()


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


def _viewSearchResults(params, catalog):
    '''
    Sub directory as an intermediary step before showing the search results catalog.
    This lets you favourite your search results so you can come back to them later.
    '''
    # After the search in viewSearchMenu() the catalog should have some items.
    hasItems = next((True for sectionItems in catalog.itervalues() if len(sectionItems) > 0), False)
    if hasItems:
        # Store the search results in the URL, to enable favouriting.
        # It might become a long URL probably, if it has many items.
        # TODO: Use file caching for this? (Like storing the search results in a file.)
        # I have no clue if there's an URL-size-limit on Kodi.
        params.update(
            {
                'view': 'CATALOG_SECTION', # Go straight to the 'ALL' catalog section instead
                'section': 'ALL',          # instead of the catalog main menu.
                'page': '0',
                'route': '_searchResults',
                'searchData': catalogHelper.dumpCatalogJSON(catalog) # This might be a huge string.
            }
        )
        item = xbmcgui.ListItem(params['query'].strip().capitalize() + ' Search Results')
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), buildURL(params), item, isFolder=True)
    else:
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), '', xbmcgui.ListItem('No Results'), False)
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

    if params.get('route', None) == '_inputSearch':
        text = _modalKeyboard('Search by Name')
        if text:
            params.update({'route': '_executeSearch', 'query': text})
            catalog = catalogHelper.getCatalog(params) # Does the actual web search with the 'query' in params.
            _viewSearchResults(params, catalog) # Sub directory, only available from this directory.
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
    xbmcplugin.setContent(int(sys.argv[1]), 'tvshows') # Optional, influences the skin layout.

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

    def _catalogSectionItems(iterable):
        api = params['api']

        if ADDON_SETTINGS['showThumbs']:
            requestHelper.setAPISource(api) # Sets the right base thumb URL for the makeThumbURL() below.

        for entry in iterable:
            # entry = (id, name, description, genres, dateReleased), see CatalogHelper.makeCatalogEntry() for more info.
            item = xbmcgui.ListItem(entry[1])
            thumb = requestHelper.makeThumbURL(entry[0]) if ADDON_SETTINGS['showThumbs'] else ''
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

    if ADDON_SETTINGS['showThumbs']:
        # Display items in pages so the thumbs are loaded in chunks to not overburden the source website.

        page = int(params['page']) # Zero-based index.
        pageSize = ADDON_SETTINGS['pageSize']
        start = page * pageSize
        stop = start + pageSize

        if sectionName == 'ALL':
            # Create pages for the pseudo-section "ALL":
            # Flatten all sections into an iterable, which is then islice'd to get the current directory page.
            flatSections = chain.from_iterable(catalog[sName] for sName in sorted(catalog.iterkeys()))
            itemsIterable = (entry for entry in islice(flatSections, start, stop))
            totalSectionPages = sum(len(section) for section in catalog.itervalues()) // pageSize
        else:
            # Do an islice of a specific section.
            itemsIterable = (entry for entry in islice(catalog[sectionName], start, stop))
            totalSectionPages = len(catalog[sectionName]) // pageSize

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

    useShowsLayout, layoutType = ADDON_SETTINGS['layoutShows']
    if useShowsLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def getEpisodeProviders(api, episodeID):
    '''
    Helper function to retrieve a dictionary of the un-resolved provider URLs
    and to filter out unsupported \ repeated providers from a specific video ID.
    :returns: Dictionary with pairs of key = str of providerName : value = list of unresolved provider URLs.
    '''
    requestHelper.setAPISource(api)
    requestHelper.delayBegin()
    jsonData = requestHelper.routeGET('/GetVideos/' + episodeID)
    requestHelper.delayEnd(500)

    if not jsonData:
        return None

    if isinstance(jsonData[0], dict):
        # Special-case for animeplus, URLs might come inside one dictionary each provider.
        providerURLs = (providerURL['url'] for providerURL in jsonData)
    elif isinstance(jsonData[0], list):
        # Or the JSON data is a list of lists (sometimes w/ mixed providers in the same list...).
        providerURLs = (url for urlList in jsonData for url in urlList)
    else:
        providerURLs = jsonData # A list of single providers?

    # Assume the video parts of the same provider will be in order (eg. easyvideo part 1, easyvideo part 2 , 3 etc.).
    providers = { }
    for url in providerURLs:
        # Try to get the provider name from the URL to see if we support resolving it.
        if url.startswith('http://'):
            tempURL = url.replace('http://', '')
        elif url.startswith('https://'):
            tempURL = url.replace('https://', '')
        # Use the key name of the provider, not the actual variant.
        providerName = next(
            (
                key
                for word in tempURL.split('.')
                for key in SUPPORTED_PROVIDERS.iterkeys() if word in SUPPORTED_PROVIDERS[key]
            ),
            None
        )
        if not providerName:
            continue # It's not a supported provider (or we failed finding its name).

        # Initialise the unresolved list of URLs for this provider if there's none yet.
        if providerName not in providers:
            providers[providerName] = [url]
        elif url and url not in providers[providerName]: # Add the URL that's not empty or (on some occasions) duplicate.
            providers[providerName].append(url)

    return providers


def resolveEpisodeProviders(supportedProviders):
    '''
    Helper function that requests the supported provider URLs and scrapes
    their pages for any streams.
    :returns: A generator for a tuple of (providerName, resolvedStreams) with at least 1 stream each.
    '''
    for providerName, providerURLs in supportedProviders.iteritems():
        resolvedStreams = [ ]
        for url in providerURLs:
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
                        # Try variants (found sometimes for Playpanda etc.):
                        temp = re.findall(r'''{\s*?url\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                        if not temp:
                            temp = re.findall(r'''file\s*?:\s*?['"](.*?)['"]''', html, re.DOTALL)
                    if temp:
                        stream = temp[0].replace(r'\/', r'/') # Unescape the found URL in case there's escaped JS slashes.
                        resolvedStreams.append(stream)
                requestHelper.delayEnd(500) # Sleep this thread a little before the next request, if necessary.
            except:
                pass
        # Yield only if there's anything playable for this provider.
        if resolvedStreams:
            yield providerName, resolvedStreams
        else:
            # Uncomment these next lines to debug failed provider resolves:
            #xbmc.log(
            #    'Toonmania2 | No streams for '+str(providerName)+' ('+str(supportedProviders[providerName])+')', xbmc.LOGWARNING
            #)
            pass


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


def _makeEpisodePartItems(episodeEntry, providers, showTitle, showGenres, showThumb, showPlot, showDate):
    '''
    Similar logic to _makeEpisodeItems(), but it works on just one item with multiple streams.
    This will make one (repeated) xbmc.ListItem for the several parts, each part is a stream.
    Then these items will be resolved in viewResolve() (view set to 'RESOLVE').
    '''
    episodeName = episodeEntry['name']
    season, episode = getTitleInfo(episodeName)
    episodeDate = episodeEntry['date'][ : 10] if 'date' in episodeEntry else showDate
    for providerName, providerURLs in providers.iteritems():
        providerUpper = providerName.upper()
        for index, unresolvedURL in enumerate(providerURLs, 1):
            partName = '[B]%s[/B] | %s' % (providerUpper, episodeName + ' | PART ' + str(index))
            item = xbmcgui.ListItem(partName)
            setupListItem(item, showTitle, partName, True, season, episode, showGenres, showThumb, showPlot, episodeDate)
            yield (
                buildURL(
                    {
                        'view': 'RESOLVE',
                        'showTitle': showTitle,
                        'name': partName,
                        'season': str(season),
                        'episode': str(episode),
                        'genres': ','.join(showGenres),
                        'thumb': showThumb,
                        'plot': showPlot,
                        'date': episodeDate,
                        'u0': providerName + '_' + unresolvedURL,
                        'multipart': '1'
                    }
                ),
                item,
                False
            )


def viewListEpisodes(params):
    '''
    Directory for the list of episodes from a show.
    This is the last directory before playing a video.
    Pages aren't necessary in here even if the thumbnails setting is on because
    for now all episodes use the same thumb and plot, inherited from the show.
    '''
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')

    # Optional, sort episode list by labels.
    #xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    api = params['api']
    showID = params['id']

    # TODO: Cleanup and make this a class that handles these tiny memory caches.
    # Internal properties to cache the last episode list view, otherwise
    # Kodi requests it again after you stop watching a video.
    _PROPERTY_LAST_ID_API = 'toonmania2.lastID_API'
    _PROPERTY_EPISODE_DETAILS = 'toonmania2.lastEpDetails'

    jsonData = None
    lastShowID_API = getRawWindowProperty(_PROPERTY_LAST_ID_API)
    if lastShowID_API == showID + api:
        jsonData = getWindowProperty(_PROPERTY_EPISODE_DETAILS)

    if not jsonData:
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        jsonData = requestHelper.routeGET('/GetDetails/' + showID)
        requestHelper.delayEnd()
        setRawWindowProperty(_PROPERTY_LAST_ID_API, showID + api)
        setWindowProperty(_PROPERTY_EPISODE_DETAILS, jsonData)

    # Genres, thumb and plot are taken from the parent show \ movie.
    # But the date of the parent show \ movie will only be used if the individual episode doesn't have a date itself.
    showTitle = jsonData.get('name', '')
    showGenres = params['genres'].split(',')
    showThumb = params.get('thumb', '') # Might be empty in case ADDON_SETTINGS['showThumbs'] is off.
    showPlot = params['plot']
    showDate = params['date']

    # If the episode details have more than one episode, list the episodes as usual.
    if len(jsonData['episode']) > 1:
        xbmcplugin.addDirectoryItems(
            int(sys.argv[1]),
            tuple(_makeEpisodeItems(api, jsonData['episode'], showTitle, showGenres, showThumb, showPlot, showDate))
        )
    else:
        # This is probably a movie, OVA or special (considered as "1 episode shows").
        # Try to get the providers first and see if it's a multi-part video (= movie).
        episodeEntry = jsonData['episode'][0]

        # TODO: Improve this with a specialised class for handling these tiny memory caches.
        _PROPERTY_EPISODE_PROVIDERS = 'toonmania2.lastEpProviders'
        supportedProviders = None
        lastEpisodeProviders = getWindowProperty(_PROPERTY_EPISODE_PROVIDERS)
        key = episodeEntry['id'] + api
        if lastEpisodeProviders and key in lastEpisodeProviders:
            supportedProviders = lastEpisodeProviders[key]
        else:
            supportedProviders = getEpisodeProviders(api, episodeEntry['id'])
            setWindowProperty(_PROPERTY_EPISODE_PROVIDERS, {key: supportedProviders})

        if supportedProviders:
            # Get a positive value if any provider has more than one URL, otherwise 0 if all are single URLs.
            hasMultipleParts = sum(
                0 if len(providerURLs) == 1 else 1 for providerURLs in supportedProviders.itervalues()
            )
            if hasMultipleParts:
                xbmcplugin.addDirectoryItems(
                    int(sys.argv[1]),
                    tuple(
                        _makeEpisodePartItems(
                            episodeEntry, supportedProviders, showTitle, showGenres, showThumb, showPlot, showDate
                        )
                    )
                )
            else:
                # The item doesn't have multiple video parts.
                # List the single item as usual, but send the supported providers
                # in the URL parameters so they don't have to be tested for support again.
                dirItem = next(_makeEpisodeItems(api, (episodeEntry,), showTitle, showGenres, showThumb, showPlot, showDate))
                providersDict = {
                    'u'+str(index) : p[0]+'_'+p[1][0] for index, p in enumerate(supportedProviders.iteritems())
                }
                newUrl = dirItem[0] + '&' + urlencode(providersDict) # Inject these parameters into the directory item URL.
                xbmcplugin.addDirectoryItem(int(sys.argv[1]), newUrl, dirItem[1], False)
        else:
            dialog = xbmcgui.Dialog()
            dialog.notification('Toonmania2', 'No providers found', xbmcgui.NOTIFICATION_INFO, 3000, False)
            xbmc.log('Toonmania2 ('+api+') | No providers for episode ID: '+episodeEntry['id'], xbmc.LOGWARNING)

    xbmcplugin.endOfDirectory(int(sys.argv[1]))

    useEpisodeLayout, layoutType = ADDON_SETTINGS['layoutEpisodes']
    if useEpisodeLayout:
        xbmc.executebuiltin('Container.SetViewMode(' + layoutType + ')')


def viewResolve(params):
    '''
    Resolves and plays the chosen episode, based on the API and ID supplied in 'params'.
    '''

    # Helper for reading provider data from the input parameters.
    # Each 'uN' key leads to a 'providerName_providerURL' value. Split at the first underscore.
    def _readProviders():
        index = 0; key = 'u0'
        while key in params:
            temp = params[key]
            uIndex = temp.find('_')
            yield temp[:uIndex], [temp[uIndex+1:]] # Yield name and single stream URL inside a list.
            index += 1
            key = 'u'+str(index)

    isMultiPart = False
    if 'u0' in params:
        # Providers for a show with a single episode OR a multi-video-part movie were filtered based
        # on if they're supported or not, but not yet resolved. Resolve these providers now.
        validProviders = dict(resolveEpisodeProviders(dict(_readProviders())))
        # Identify multipart movies that come from _makeEpisodePartItems() using a 'multipart' parameter.
        isMultiPart = 'multipart' in params
    else:
        # This is a normal episode from a show with several episodes.
        # Get its providers and resolve them all in here.
        # The 'api' and 'episodeID' keys are guaranteed to be in the 'params' dict.
        episodeProviders = getEpisodeProviders(params['api'], params['episodeID'])
        validProviders = dict(resolveEpisodeProviders(episodeProviders))

    if validProviders:
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

        resolvedURL = None

        if ADDON_SETTINGS['autoplay'] or isMultiPart:
            from random import choice
            providerNames = tuple(providerName for providerName in validProviders.iterkeys())
            resolvedURL = validProviders[choice(providerNames)][0]
        else:
            providerNames = tuple(providerName for providerName in validProviders.iterkeys())
            selectedIndex = xbmcgui.Dialog().select('Select Provider', providerNames)
            if selectedIndex != -1:
                resolvedURL = validProviders[providerNames[selectedIndex]][0]

        if resolvedURL:
            item.setPath(resolvedURL)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
        else:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem('None'))
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification('Toonmania2', 'No streams found', xbmcgui.NOTIFICATION_INFO, 3000, False)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem('None'))

    # Failed attempt at trying to autoplay all multi-part videos using a XBMC video playlist.
    # Using directory items for each part (as it is now) seems safer.
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

            
def reloadAddonSettings():
    global ADDON_SETTINGS
    ADDON_SETTINGS['showThumbs'] = ADDON.getSetting('show_thumbnails') == 'true'
    ADDON_SETTINGS['pageSize'] = int(ADDON.getSetting('page_size')) # Page size = number of items per catalog section page.
    ADDON_SETTINGS['autoplay'] = ADDON.getSetting('use_autoplay') == 'true'
    # Create keys to a (bool, layoutType) value, eg: 'layoutCatalog': (True, '0')
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
    
    reloadAddonSettings() # Initialises ADDON_SETTINGS on Kodi < 17.6
    
    params = {key: value[0] for key, value in parse_qs(sys.argv[2][1:]).iteritems()}
    VIEW_FUNCS[params.get('view', 'MENU')](params)