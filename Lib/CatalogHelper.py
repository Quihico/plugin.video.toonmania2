# -*- coding: utf-8 -*-
import json
from bs4 import BeautifulSoup
from string import ascii_uppercase
from datetime import datetime
from itertools import chain

from Lib.Common import (
    setRawWindowProperty,
    getRawWindowProperty,
    setWindowProperty,
    getWindowProperty
)
from Lib.RequestHelper import requestHelper


class CatalogHelper():

    # Persistent memory properties used to hold the current API, the current route (the website "area"
    # being displayed) and the catalog of items itself, with sections and items.
    # See catalogFromIterable() for more.
    PROPERTY_CATALOG_API = 'toonmania2.catalogAPI'
    PROPERTY_CATALOG_ROUTE = 'toonmania2.catalogRoute'
    PROPERTY_CATALOG = 'toonmania2.catalog'

    # The next properties are used to (lazily) cache items ONLY from the '/GetAll(...)' routes, as these properties
    # are needed in the name and genre searches and in the Latest Updates view. These operations require
    # all items from an API to be loaded first.
    # See more in the getMainRoutesData() for more.
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
            '/GetUpdates/': self.latestUpdatesCatalog,
            '_executeSearch': self.executeSearchCatalog,
            '_searchResults': self.searchResultsCatalog,
            '/GetGenres/': self.genreSearchCatalog            
            # Otherwise defaults to the 'genericCatalog' function.
        }


    '''
    The catalog is a dictionary of lists of lists, used to store data between add-on states to make xbmcgui.ListItems:
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
            setWindowProperty(self.PROPERTY_CATALOG, catalog)
            return catalog

        # If these properties are empty (like when coming in from a favourites menu), or if a different
        # route (website area) or a different API was stored in this property, then reload it.
        currentAPI = getRawWindowProperty(self.PROPERTY_CATALOG_API)
        currentRoute = getRawWindowProperty(self.PROPERTY_CATALOG_ROUTE)
        if (
            currentAPI != params['api']
            or currentRoute != params['route']
            or 'genreName' in params # Special-case for the genre search, same api\route but 'genreName' changes.
            or 'query' in params    # Special-case for the name search, same api\route but 'query' changes.
            or 'searchData' in params
        ):
            setRawWindowProperty(self.PROPERTY_CATALOG_API, params['api'])
            setRawWindowProperty(self.PROPERTY_CATALOG_ROUTE, params['route'])
            catalog = _buildCatalog()
        else:
            catalog = getWindowProperty(self.PROPERTY_CATALOG)
            if not catalog:
                catalog = _buildCatalog()
        return catalog

    
    def makeCatalogEntry(self, entry):
        '''
        Grabs the relevant data we care from a parent entry (show\movie).
        :returns: Returns a tuple of the format (id, name, description, genres, released)
        '''
        return (
            entry['id'],
            entry['name'].strip(),
            entry['description'].strip() if entry['description'] else '',# Might be empty or None.
            entry['genres'], # Might be an empty list.
            entry.get('released', '')
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
        route = params['route']
        if '/GetAll' in route:
            # Get from the getMainRoutesData() function because it caches results, so
            # it can spare the web request.
            allData = self.getMainRoutesData(params['api'], (route,))
            itemList = allData[route]
            if itemList:
                return self.catalogFromIterable(entry for entry in itemList)
        else:
            # The route is one of the '/GetNew(...)' or '/GetPopular(...)' routes.
            requestHelper.setAPISource(params['api'])
            requestHelper.delayBegin()
            jsonData = requestHelper.routeGET(route)
            requestHelper.delayEnd(500)
            if jsonData:
                return self.catalogFromIterable(self.makeCatalogEntry(entry) for entry in jsonData)
        # Fall-through.
        return self.getEmptyCatalog()


    def latestUpdatesCatalog(self, params):
        '''
        Returns a catalog for the Latest Updates category.
        '''
        api = params['api']
        requestHelper.setAPISource(api)
        requestHelper.delayBegin()
        jsonData = requestHelper.routeGET(params['route'])
        requestHelper.delayEnd(500)

        if jsonData:
            # Latest Updates needs all of items of the current API loaded, to compare IDs with.
            # Make a dictionary to map item IDs to the items themselves.
            allData = self.getMainRoutesData(api, self.allMainRouteNames(api))
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())} # item[0] = id

            # Find the entry representing the item in the latest updates list.
            return self.catalogFromIterable(
                idDict[entry['id']] for entry in jsonData.get('updates', [ ]) if entry['id'] in idDict
            )
        else:
            return self.getEmptyCatalog()


    def executeSearchCatalog(self, params):
        '''
        Returns a catalog from a name search, uses the standard website for searching.
        Searches query in params['query'].
        '''
        # We search with their website search, then get results.
        requestHelper.setAPISource(params['api']) # Updates the internal search URL.
        requestHelper.setDesktopHeader() # Desktop user agent spoofing.

        requestHelper.delayBegin()
        r = requestHelper.searchGET(params['query'])
        requestHelper.delayEnd(1500)

        if r.ok:
            soup1 = BeautifulSoup(r.text, 'html.parser')
            mainUL = soup1.find('div', {'class': 'series_list'}).ul
            
            # Early exit test. No point in loading everything if there's no search results.
            if not mainUL.find('li'):
                return self.getEmptyCatalog()
                
            # A name search needs all of the items of the current API loaded, to compare IDs with.
            allData = self.getMainRoutesData(params['api'], self.allMainRouteNames(params['api']))
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())}

            # Helper function to find the entry with the same ID as the one from the search results.
            def _executeSearchItems(mainULs):
                for ul in mainULs:
                    for li in ul.find_all('li'):
                        img  = li.find('img')
                        if img:
                            src = li.img['src']
                            # Assuming the thumb images of search results always end with
                            # '.jpg' (4 characters long), the IDs of items found can be
                            # obtained from these thumb URLs.
                            thumbID = src[src.rfind('/')+1 : -4] # Grab the 'xxxx' from '..../small/xxxx.jpg'.
                            if thumbID in idDict:
                                yield idDict[thumbID]

            # When there's more than one page of results there'll be buttons for pagination.
            # Request and scrape these other pages.
            paginationDIV = soup1.find('ul', {'class': 'pagination'})
            if paginationDIV:
                allULs = [mainUL]
                for button in paginationDIV.find_all('button'):
                    nextURL = button.get('href', None)
                    if nextURL:

                        requestHelper.delayBegin()
                        r2 = requestHelper.GET(nextURL)
                        soup2 = BeautifulSoup(r2.text, 'html.parser')
                        otherUL = soup2.find('div', {'class': 'series_list'}).ul
                        if otherUL:
                            allULs.append(otherUL)
                        requestHelper.delayEnd(1500)

                return self.catalogFromIterable(entry for entry in _executeSearchItems(allULs))
            else:
                return self.catalogFromIterable(entry for entry in _executeSearchItems((mainUL,)))
        else:
            return self.getEmptyCatalog()


    def searchResultsCatalog(self, params):
        '''
        Gerates a catalog from search results data in 'params'.
        This data was created in dumpCatalogJSON().
        '''
        if 'searchData' in params:            
            return self.catalogFromIterable(json.loads(params['searchData']))
        else:
            return self.getEmptyCatalog()
        
            
    def genreSearchCatalog(self, params):
        '''
        Gerates a catalog from a genre search, the genre query in params['genreName'].
        '''
        genreName = params['genreName']
        # A genre search needs all of the items of the current API loaded, to compare genres with.
        allData = self.getMainRoutesData(params['api'], self.allMainRouteNames(params['api']))
        # Inclusion test for 'genreName'. Item[3] = list of genres.
        return self.catalogFromIterable(
            entry for entry in chain.from_iterable(allData.itervalues()) if genreName in entry[3]
        )


    def _getRouteData(self, route):
        '''
        Assumes the appropriate API has already been set.
        Not called by external code.
        '''
        requestHelper.delayBegin()
        jsonData = requestHelper.routeGET(route)
        requestHelper.delayEnd(1000) # Always delay between requests so we don't abuse the source.
        return tuple(self.makeCatalogEntry(entry) for entry in jsonData) if jsonData else None


    def getMainRoutesData(self, api, routes=()):
        '''
        The 'routes' parameter is a list with one or more of the main routes ('/GetAll(...)')
        for a specific API.

        :returns: A dictionary with these routes as keys mapping to lists of catalog items.
        '''
        requestHelper.setAPISource(api)

        if api == requestHelper.API_ANIMETOON:
            routesPropName = self.PROPERTY_ANIMETOON_LOADED_ROUTES
            dataPropName = self.PROPERTY_ANIMETOON_DATA
        else:
            routesPropName = self.PROPERTY_ANIMEPLUS_LOADED_ROUTES
            dataPropName = self.PROPERTY_ANIMEPLUS_DATA

        loadedRoutes = getWindowProperty(routesPropName)
        if not loadedRoutes:
            loadedRoutes = [ ]

        addedNew = False
        routeData = { }
        for route in routes:
            if route not in loadedRoutes:
                addedNew = True
                loadedRoutes.append(route)
                routeData[route] = self._getRouteData(route)

        allData = getWindowProperty(dataPropName)
        if addedNew:
            setWindowProperty(routesPropName, loadedRoutes)
            if not allData:
                allData = routeData
            else:
                allData.update(routeData)
            setWindowProperty(dataPropName, allData)
        return allData


    def allMainRouteNames(self, api):
        '''
        Convenience function to get all the names of the main routes for a given API.
        '''
        return (
            ('/GetAllCartoon', '/GetAllMovies', '/GetAllDubbed') # Animetoon 'All' routes.
            if api == requestHelper.API_ANIMETOON
            else ('/GetAllMovies', '/GetAllShows') # Animeplus 'All' routes.
        )

        
    def dumpCatalogJSON(self, catalog):
        '''
        Creates a JSON string dump from catalog items.
        This is used in Client.py to store search results in the URL.
        '''
        return json.dumps(tuple(entry for section in catalog.itervalues() for entry in section))

        
catalogHelper = CatalogHelper()
