# -*- coding: utf-8 -*-
import json
from bs4 import BeautifulSoup
from string import ascii_uppercase
from datetime import datetime
from itertools import chain

from Lib.SimpleCache import cache
from Lib.RequestHelper import requestHelper


class CatalogHelper():

    # Persistent memory properties used to hold the last API and the last route (the website "area" being
    # displayed) used to build the catalog of items. Used to tell if a new catalog needs to be built.
    PROPERTY_CATALOG_API = 'toonmania2.catalogAPI'
    PROPERTY_CATALOG_ROUTE = 'toonmania2.catalogRoute'
    # Property name for the catalog of items itself. See catalogFromIterable() for more info.
    PROPERTY_CATALOG = 'toonmania2.catalog'

    # The only routes not stored in disk-persistent properties are the '/GetUpdates/' ones, which are always
    # requested fresh.
    '''
    { 1. Main dictionary.
        '/GetAllCartoon': 2. Category key. Its value is a list of tuples.
            (
                item, 3. Item, it's a tuple with the cartoon\movie\anime details. See makeCatalogEntry() for details.
                item,
                item,
                ...
            )
        }
        '/GetAllMovies': ( item, item, item, ... )
        '/GetAllDubbed': ( item, item, item, ... )
        '/GetNewMovies': (...)
    }'''
    PROPERTY_ANIMETOON_LOADED_ROUTES = 'toonmania2.animetoonRoutes' # List of the main routes already loaded.

    # Dictionary w/ keys mapping to lists of items.
    # The _LOADED_ROUTES property can be used to tell which of these routes are already loaded in this dict.
    PROPERTY_ANIMETOON_DATA = 'toonmania2.animetoon'

    PROPERTY_ANIMEPLUS_LOADED_ROUTES = 'toonmania2.animeplusRoutes' # List of the main routes already loaded.
    PROPERTY_ANIMEPLUS_DATA = 'toonmania2.animeplus' # Same as _ANIMETOON_DATA, but for animeplus.

    LETTERS_SET = set(ascii_uppercase) # Used in the catalogFromIterable() function.


    def __init__(self):
        '''
        Initialises a dict member to map API routes to catalog iterable creation functions.
        This dict is used in self.getCatalog().
        '''
        self.catalogFunctions = {
            '/GetAllMovies': self.allRouteCatalog, # Dubbed movies from animetoon / subbed movies from animeplus.
            '/GetAllCartoon': self.allRouteCatalog, # Cartoons from animetoon.
            '/GetAllDubbed': self.allRouteCatalog, # Dubbed anime from animetoon.
            '/GetAllShows': self.allRouteCatalog, # Subbed anime from animeplus.
            '/GetUpdates/': self.latestUpdatesCatalog,
            '/GetGenres/': self.genreSearchCatalog,
            '_searchResults': self.searchResultsCatalog,
            # Otherwise defaults to the 'genericCatalog' function.
        }


    '''
    The catalog is a dictionary of lists of entries, used to store data between add-on states to make xbmcgui.ListItems:
    {
        (1. Sections, as in alphabet sections for list items: #, A, B, C, D, E, F etc., each section holds a tuple of items.)
        A: (
            item, item, item, ...    (2. Items, each item is a tuple with the format seen in makeCatalogEntry().)
        )
        B: (...)
        C: (...)
    }
    '''
    def getCatalog(self, params):
        '''
        Retrieves the catalog from a persistent window property between different add-on
        states, or recreates the catalog if needed.
        '''
        def _buildCatalog():
            catalog = self.catalogFunctions.get(params['route'], self.genericCatalog)(params)
            cache.setCacheProperty(self.PROPERTY_CATALOG, catalog, saveToDisk = False)
            return catalog

        # If these properties are empty (like when coming in from a favourites menu), or if a different
        # route (website area) or a different API was stored in this property, then reload it.
        lastAPI = cache.getRawProperty(self.PROPERTY_CATALOG_API)
        lastRoute = cache.getRawProperty(self.PROPERTY_CATALOG_ROUTE)
        if (
            params['api'] != lastAPI
            or params['route'] != lastRoute
            or 'genreName' in params # Special-case for the genre search, same api\route but 'genreName' changes.
            or 'query' in params    # Special-case for the name search, same api\route but 'query' changes.
            or 'searchIDs' in params # Special-case for search results, we might be coming in from Kodi Favourites.
        ):
            cache.setRawProperty(self.PROPERTY_CATALOG_API, params['api'])
            cache.setRawProperty(self.PROPERTY_CATALOG_ROUTE, params['route'])
            catalog = _buildCatalog()
        else:
            catalog = cache.getCacheProperty(self.PROPERTY_CATALOG, readFromDisk = False)
            if not catalog:
                catalog = _buildCatalog()
        return catalog


    def makeCatalogEntry(self, entry):
        '''
        Grabs the relevant data we care from a parent JSON entry (show\movie).
        :returns: A tuple of the format (id, name, description, [genres], released)
        '''
        return (
            entry['id'],
            entry['name'].strip(),
            entry['description'].strip() if entry['description'] else '',# Might be empty or None.
            entry['genres'], # Might be an empty list.
            entry.get('released', None)
        )


    def getEmptyCatalog(self):
        return {key: [ ] for key in ascii_uppercase + '#'}


    def catalogFromIterable(self, iterable):
        '''
        Splits items from an iterable into an alphabetised catalog.
        Each item in the iterable is a tuple: (id, name, description, genres, released)
        ID, name and description are str, genres is a str list.
        Description and genres list might be empty.
        '''
        catalog = self.getEmptyCatalog()
        for item in iterable:
            itemKey = item[1][0].upper()
            catalog[itemKey if itemKey in self.LETTERS_SET else '#'].append(item)
        return catalog
        
        
    def genericCatalog(self, params):
        '''
        Returns a catalog for either the '/GetNew(...)' or '/GetPopular(...)' routes.
        These routes are cached memory-only, so they last one Kodi session. Closing and
        reopening Kodi will make a new web request for fresh data.
        '''
        api = params['api']
        route = params['route']

        genericIDs = cache.getCacheProperty(api+route, readFromDisk = False)
        if not genericIDs:
            requestHelper.setAPISource(api)
            requestHelper.delayBegin()
            jsonData = requestHelper.routeGET(route)
            if jsonData:
                genericIDs = tuple(entry['id'] for entry in jsonData)
                cache.setCacheProperty(api+route, genericIDs, saveToDisk = False)
            requestHelper.delayEnd(500)
            
        if genericIDs:
            # Load all the main routes of the API (they are disk-cached), to compare IDs with.
            allData = self._getMainRoutesData(api)
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())}
            return self.catalogFromIterable(idDict[entryID] for entryID in genericIDs if entryID in idDict)
        else:
            return self.getEmptyCatalog()


    def allRouteCatalog(self, params):
        '''
        Returns a catalog for one of the main '/GetAll(...)' routes.
        '''
        api = params['api']
        route = params['route']

        jsonData = cache.getCacheProperty(api+route, readFromDisk = True)
        if not jsonData:
            requestHelper.setAPISource(api)
            requestHelper.delayBegin()
            jsonData = requestHelper.routeGET(route)
            if jsonData:
                cache.setCacheProperty(api+route, jsonData, saveToDisk = True) # Default to 3 days cache lifetime.
            requestHelper.delayEnd(500)
            
        if jsonData:
            return self.catalogFromIterable(self.makeCatalogEntry(entry) for entry in jsonData)
        else:
            return self.getEmptyCatalog()


    def latestUpdatesCatalog(self, params):
        '''
        Returns a catalog for the Latest Updates category.
        This route is cached memory-only to make sure it's always fresh.
        This memory cache lasts one Kodi session. Closing Kodi and reopening it
        will do a new web request.
        '''
        api = params['api']

        if api == requestHelper.API_ANIMETOON:
            _PROPERTY_LAST_UPDATES = 'tmania2.prop.toonUpdates'
        else:
            _PROPERTY_LAST_UPDATES = 'tmania2.prop.plusUpdates'

        # Memory-only cache of the latest updates IDs.
        latestIDs = cache.getCacheProperty(_PROPERTY_LAST_UPDATES, readFromDisk = False)
        if not latestIDs:
            requestHelper.setAPISource(api)
            requestHelper.delayBegin()
            jsonData = requestHelper.routeGET(params['route'])
            if jsonData:
                latestIDs = tuple(entry['id'] for entry in jsonData.get('updates', [ ]))
                cache.setCacheProperty(_PROPERTY_LAST_UPDATES, latestIDs, saveToDisk = False)
            requestHelper.delayEnd(1000)

        if latestIDs:
            # Latest Updates needs all items of the current API loaded, to compare IDs with.
            # Make a dictionary to map item IDs to the items themselves.
            allData = self._getMainRoutesData(api)
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())}
            # Find the entries based on their IDs from the latest updates list.
            return self.catalogFromIterable(idDict[entryID] for entryID in latestIDs if entryID in idDict)
        else:
            return self.getEmptyCatalog()


    def searchResultsCatalog(self, params):
        '''
        Gerates a catalog from show\movie IDs from a name search.
        '''
        searchIDs = params.get('searchIDs', '').split(',')
        if searchIDs:
            # A search result filtering needs all of the items of the searched API loaded to compare IDs with.
            allData = self._getMainRoutesData(params['api'])
            idDict = {entry[0]: entry for entry in chain.from_iterable(allData.itervalues())}
            return self.catalogFromIterable(idDict[resultID] for resultID in searchIDs if resultID in idDict)
        else:
            return self.getEmptyCatalog()


    def genreSearchCatalog(self, params):
        '''
        Gerates a catalog from a genre search, the genre query in params['genreName'].
        '''
        genreName = params['genreName']
        # A genre search needs all of the items of the current API loaded, to compare genres with.
        allData = self._getMainRoutesData(params['api'])
        # Inclusion test for 'genreName'.
        return self.catalogFromIterable(
            entry for entry in chain.from_iterable(allData.itervalues()) if genreName in entry[3]
        )


    def _getMainRoutesData(self, api):
        '''
        Loads all the main routes from one of the APIs to be used in the "filtering" catalog functions, like
        the latestUpdatesCatalog, genreSearchCatalog etc. that need all items loaded at once.
        :returns: A dict of the '/GetAll(...)' routes of the API, each route key holds a list of catalog entries.
        '''
        requestHelper.setAPISource(api)
        if api == requestHelper.API_ANIMETOON:
            routeAlls = ('/GetAllCartoon', '/GetAllMovies', '/GetAllDubbed') # Animetoon 'All' routes.
        else:
            routeAlls = ('/GetAllMovies', '/GetAllShows') # Animeplus 'All' routes.

        routesData = { }
        newProperties = [ ]        
        isNewProperty = False
        for route in routeAlls:
            jsonData = cache.getCacheProperty(api+route, readFromDisk = True) # Try to get the cached property first.
            if not jsonData:
                requestHelper.delayBegin()
                jsonData = requestHelper.routeGET(route)
                if jsonData:
                    newProperties.append((api+route, jsonData, True, cache.LIFETIME_THREE_DAYS))
                    isNewProperty = True
                requestHelper.delayEnd(1000) # Always delay between requests so we don't abuse the source.            
            routesData[route] = tuple(self.makeCatalogEntry(entry) for entry in jsonData)
        
        if newProperties:
            cache.setCacheProperties(newProperties)

        return routesData
        
        
    def nameSearchEntries(self, api, text):
        '''
        This name search is done with their own website search.
        :returns: A list of entry IDs found in the search. 
        '''
        requestHelper.setAPISource(api) # Updates the internal search URL.
        requestHelper.setDesktopHeader() # Desktop user agent spoofing.

        requestHelper.delayBegin()
        r = requestHelper.searchGET(text)
        requestHelper.delayEnd(1500)
        if not r.ok:
            return ( )
            
        soup1 = BeautifulSoup(r.text, 'html.parser')
        mainUL = soup1.find('div', {'class': 'series_list'}).ul

        # Early exit test. No point in going further if there's no search results.
        if not mainUL.find('li'):
            return ( )
        allULs = [mainUL]        

        # A name search needs all of the items of the current API loaded, to compare IDs with.
        # Make a dictionary to map entry IDs to the entries themselves.
        allData = self._getMainRoutesData(api)
        idDict = {entry[0]: entry for entry in chain.from_iterable(allData.itervalues())}

        # Helper function to find the entry with the same ID as the one from the search results.
        def _nameSearchEntriesHelper(mainULs):
            for ul in mainULs:
                for li in ul.find_all('li'):
                    img  = li.find('img')
                    if img:
                        src = img['src']
                        # Assuming the thumb images of search results always end with
                        # '.jpg' (4 characters long), the IDs of search results can be
                        # obtained from these thumb URLs.
                        thumbID = src[src.rfind('/')+1 : -4] # Grab the 'xxxx' from '..../small/xxxx.jpg'.
                        if thumbID in idDict: # Only yield entries we know about.
                            yield thumbID

        # When there's more than one page of results there'll be buttons for pagination.
        # Request and scrape these other pages.
        paginationDIV = soup1.find('ul', {'class': 'pagination'})
        if paginationDIV:
            for button in paginationDIV.find_all('button'):
                nextURL = button.get('href', None)
                if nextURL:

                    requestHelper.delayBegin()
                    r2 = requestHelper.GET(nextURL)
                    if r2.ok:
                        soup2 = BeautifulSoup(r2.text, 'html.parser')
                        otherUL = soup2.find('div', {'class': 'series_list'}).ul
                        allULs.append(otherUL)
                    requestHelper.delayEnd(1500)

        return (entryID for entryID in _nameSearchEntriesHelper(allULs))


catalogHelper = CatalogHelper()
