# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from string import ascii_uppercase
from datetime import datetime
from itertools import chain

import xbmc

from lib.common import (
    setRawWindowProperty,
    getRawWindowProperty,
    setWindowProperty,
    getWindowProperty
)
from lib.request_helper import requestHelper


class CatalogHelper():

    # Persistent memory properties used to hold the route (the website "area" being displayed) and
    # the catalog of items itself, with sections and items. See catalogFromIterable() for more info.
    PROPERTY_CATALOG_API = 'toonmania2.catalogAPI'
    PROPERTY_CATALOG_ROUTE = 'toonmania2.catalogRoute'
    PROPERTY_CATALOG = 'toonmania2.catalog'

    # Below are properties used to (lazily) cache items ONLY from the '/GetAll(...)' routes, as these properties
    # are needed in the name and genre searches and in the Latest Updates view.
    # See more in the ensureMainRouteLoaded() function.
    '''
    { 1. Main dictionary.
        '/GetAllCartoon': 2. Category key. Its value is a list of tuples.
            (
                (id, name, description, genres) 3. Item tuple, with the cartoon\movie\anime details.
                (id, name, description, genres)
                (id, name, description, genres)
                ...
            )
        }
        '/GetAllMovies': ( (id, name, description, genres), (id, name, description, genres), ... )
        '/GetAllDubbed': ( (id, name, description, genres), (id, name, description, genres), ... )
    }'''
    PROPERTY_ANIMETOON_LOADED_ROUTES = 'toonmania2.animetoonRoutes' # List of the main routes already loaded.

    # Dictionary w/ keys mapping to lists of items.
    # The _LOADED_ROUTES property can be used to tell which of these routes are already loaded in this dict.
    PROPERTY_ANIMETOON_DATA = 'toonmania2.animetoon'

    PROPERTY_ANIMEPLUS_LOADED_ROUTES = 'toonmania2.animeplusRoutes' # List of the main routes already loaded.
    PROPERTY_ANIMEPLUS_DATA = 'toonmania2.animeplus' # Same as _ANIMETOON_DATA, but for animeplus.

    LETTERS_SET = set(ascii_uppercase) # Used in the catalogFromIterable() function.

    '''
    The catalog is a dictionary of lists of lists, used to store data between add-on states to make xbmcgui.ListItems:
    {
        (1. Sections, as in alphabet sections for list items: #, A, B, C, D, E, F etc., each section holds a tuple of items.)
        A: (
            item, item, item, ...    (2. Items, each item is a tuple: (id, name, description, genres).)
        )
        B: (...)
        C: (...)
    }
    '''


    def __init__(self):
        # Dictionary to map routes to catalog iterable creation functions.
        self.catalogFunctions = {
            '/GetUpdates/': self.latestUpdatesCatalog,
            '_executeSearch': self.executeSearchCatalog,
            '/GetGenres/': self.genreCatalog
            # Otherwise defaults to 'genericCatalog' in self.getCatalog().
        }


    # Retrieves the catalog from a persistent window property between different add-on
    # states, or recreates the catalog if needed.
    def getCatalog(self, params):
        def _buildCatalog():
            catalog = self.catalogFunctions.get(params['route'], self.genericCatalog)(params)
            setWindowProperty(self.PROPERTY_CATALOG, catalog)
            return catalog

        # If these properties are empty (like when coming in from a favourites menu), or if a different
        # catalog (website area) or a different API was stored in this property, then reload it.
        currentAPI = getRawWindowProperty(self.PROPERTY_CATALOG_API)
        currentRoute = getRawWindowProperty(self.PROPERTY_CATALOG_ROUTE)
        if (
            currentAPI != params['api']
            or currentRoute != params['route']
            or 'genreName' in params # Special-case for genre search, the api\route stays the same and 'genreName' changes.
            or 'query' in params    # Special-case for the name search, same api\route but 'query' changes.
        ):
            setRawWindowProperty(self.PROPERTY_CATALOG_API, params['api'])
            setRawWindowProperty(self.PROPERTY_CATALOG_ROUTE, params['route'])
            catalog = _buildCatalog()
        else:
            catalog = getWindowProperty(self.PROPERTY_CATALOG)
            if not catalog:
                catalog = _buildCatalog()
        return catalog


    def getEmptyCatalog(self):
        return {key: [ ] for key in ascii_uppercase + '#'}


    # Splits items from an iterable into an alphabetised catalog.
    def catalogFromIterable(self, iterable):
        catalog = self.getEmptyCatalog()
        for item in iterable:
            # item = tuple(id, name, description, genres) -> all str values. Description might be empty.
            itemKey = item[1][0].upper()
            catalog[itemKey if itemKey in self.LETTERS_SET else '#'].append(item)
        return catalog


    def genericCatalog(self, params):
        route = params['route']
        if '/GetAll' in route:
            # Try to use the cached data first, if available, to spare the web request.
            allData = self.getMainRoutesData(params['api'], (route,))
            jsonData = allData[route]
            if jsonData:
                # Produce a tuple out of memory items.
                return self.catalogFromIterable(entry for entry in jsonData)
        else:
            # The route is one of the '/GetNew(...)' or '/GetPopular(...)' routes.
            requestHelper.setAPISource(params['api'])
            jsonData = requestHelper.routeGET(route)
            if jsonData:
                # Produce a tuple of (id, name, description, genres) out of JSON items.
                return self.catalogFromIterable(
                    (
                        entry['id'],
                        entry['name'].strip(),
                        entry['description'].strip() if entry['description'] else '',
                        entry['genres']
                    )
                    for entry in jsonData
                )
        # Fall-through.
        return self.getEmptyCatalog()


    def latestUpdatesCatalog(self, params):
        api = params['api']

        requestHelper.setAPISource(api)
        startTime = datetime.now()
        jsonData = requestHelper.routeGET(params['route'])
        requestHelper.apiDelay(startTime, 1000)

        if jsonData:
            # Latest Updates needs all of items of the current API loaded, to compare IDs with.
            # Make a dictionary to map the item IDs to the items themselves.
            allData = self.getMainRoutesData(api, self.allMainRouteNames(api))
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())} # item[0] = id

            # Find the entry representing the item in the latest updates list.
            return self.catalogFromIterable(
                idDict[entry['id']] for entry in jsonData.get('updates', [ ]) if entry['id'] in idDict
            )
        else:
            return self.getEmptyCatalog()


    def executeSearchCatalog(self, params):
        requestHelper.setAPISource(params['api'])
        requestHelper.setDesktopHeader() # For requesting the desktop website.

        # We search with their website search, then get results.
        startTime = datetime.now()
        r = requestHelper.searchGET(params['query'])
        requestHelper.apiDelay(startTime, 1500)

        if r.ok:
            soup1 = BeautifulSoup(r.text, 'html.parser')
            mainUL = soup1.find('div', {'class': 'series_list'}).ul

            # A name search needs all of the items of the current API loaded, to compare IDs with.
            allData = self.getMainRoutesData(params['api'], self.allMainRouteNames(params['api']))
            idDict = {item[0]: item for item in chain.from_iterable(allData.itervalues())}

            # Helper function to find the entry with the same ID as the one from the search results.
            def _executeSearchItems(mainULs):
                for ul in mainULs:
                    for li in ul.find_all('li'):
                        src = li.img['src']
                        # Assuming the thumbs of the search results always end with '.jpg' (4 characters long),
                        # the IDs of the items found can be obtained from these thumb URLs.
                        thumbID = src[src.rfind('/')+1 : -4] # Grab the 'xxx' from "..../small/xxx.jpg".
                        if thumbID in idDict:
                            yield idDict[thumbID]

            # When there's more than one page there's buttons for pagination.
            # Scrape the other pages.
            paginationDIV = soup1.find('ul', {'class': 'pagination'})
            if paginationDIV:
                otherULs = [mainUL]
                for button in paginationDIV.find_all('button'):
                    nextURL = button.get('href', None)
                    if nextURL:                    
                        startTime = datetime.now()
                        
                        r2 = requestHelper.GET(nextURL)
                        soup2 = BeautifulSoup(r2.text, 'html.parser')
                        otherUL = soup2.find('div', {'class': 'series_list'}).ul
                        if otherUL:
                            otherULs.append(otherUL)
                            
                        requestHelper.apiDelay(startTime, 3000)
                return self.catalogFromIterable(entry for entry in _executeSearchItems(otherULs))
            else:
                return self.catalogFromIterable(entry for entry in _executeSearchItems((mainUL,)))
        else:
            return self.getEmptyCatalog()


    def genreCatalog(self, params):
        # A genre search needs all of the items of the current API loaded, to compare genres with.
        allData = self.getMainRoutesData(params['api'], self.allMainRouteNames(params['api']))
        genreName = params['genreName']

        # Collect the entries with 'genreName' in its genres list.
        return self.catalogFromIterable(
            entry for entry in chain.from_iterable(allData.itervalues()) if genreName in entry[3] # item[3] = genres
        )


    def _getRouteData(self, route):
        # Assumes the appropriate API has already been set.
        jsonData = requestHelper.routeGET(route)
        if jsonData:
            startTime = datetime.now()
            routeData = tuple(
                (   # (id, name, description, genres)
                    entry['id'],
                    entry['name'].strip(),
                    entry['description'].strip() if entry['description'] else '',# Might be empty or None.
                    entry['genres'] # Might be an empty list.
                )
                for entry in jsonData
            )
            requestHelper.apiDelay(startTime, 500) # Always delay between requests so we don't abuse the source.
            return routeData
        else:
            return None


    # The 'routes' parameter is a list with one or more of the main routes ('/GetAll(...)') for a specific API.
    # Returns a dictionary with these routes as keys mapping to lists of catalog items.
    def getMainRoutesData(self, api, routes=()):
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


    # Convenience function to get all the names of the main routes for a given API.
    def allMainRouteNames(self, api):
        return (
            ('/GetAllCartoon', '/GetAllMovies', '/GetAllDubbed') # Animetoon 'All' routes.
            if api == requestHelper.API_ANIMETOON
            else ('/GetAllMovies', '/GetAllShows') # Animeplus 'All' routes.
        )


catalogHelper = CatalogHelper()
