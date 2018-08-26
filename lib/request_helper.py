# -*- coding: utf-8 -*-
import requests
from datetime import datetime

import xbmc
from xbmc import sleep

from lib.common import setRawWindowProperty, getRawWindowProperty


# A requests helper class just for the Animetoon and Animeplus APIs.

class RequestHelper():

    # The larger the item pages, the more Kodi thumbnail requests will be done at once to the websites.
    # Something to keep in mind.
    # There's also this hardcoded delay here:
    API_REQUEST_DELAY = 200 # In millseconds, between each request done to the websites or the JSON api.

    URL_API_ANIMETOON = 'http://api.animetoon.tv'
    URL_ANIMETOON_IMAGES = 'http://www.animetoon.tv/images/series/small/' # Replace 'small' with 'big' to get larger thumbs.
    URL_ANIMETOON_SEARCH = 'http://www.animetoon.org/toon/search?key=%s'

    URL_API_ANIMEPLUS = 'http://api.animeplus.tv'
    URL_ANIMEPLUS_IMAGES = 'http://www.animeplus.tv/images/series/small/'
    URL_ANIMEPLUS_SEARCH = 'http://www.animeplus.tv/anime/search?key=%s'
    
    # API sources, used with the setAPISource() function.
    API_ANIMETOON = '0'
    API_ANIMEPLUS = '1'

    # Persistent window property holding the app version obtained from
    # the '/GetVersion' API route.
    PROPERTY_VERSION = 'requesthelper.version'
    
    # Stores a persistent random user-agent string, or empty if not used yet.
    # Used when searching with the regular websites.    
    PROPERTY_RANDOM_USERAGENT = 'requesthelper.randomUA'
    

    def __init__(self):
        self.animetoonHeaders = {
            'User-Agent': 'okhttp/2.3.0',
            'App-LandingPage': 'http://www.mobi24.net/toon.html',
            'App-Name': '#Toonmania',
            'App-Version': '8.0',
            'Accept': '*/*'            
        }
        self.animeplusHeaders = {
            'User-Agent': 'okhttp/2.3.0',
            'App-LandingPage': 'http://www.mobi24.net/anime.html',
            'App-Name': '#Animania',
            'App-Version': '8.0',
            'Accept': '*/*'
        }
        self.session = requests.Session()
        self.setAPISource(self.API_ANIMETOON) 
        
        latestVersion = getRawWindowProperty(self.PROPERTY_VERSION)
        if not latestVersion:
            jsonData = self.routeGET('/GetVersion')
            latestVersion = jsonData.get('version', '8.0')
            setRawWindowProperty(self.PROPERTY_VERSION, latestVersion)
        self.animetoonHeaders.update({'App-Version': latestVersion})
        self.animeplusHeaders.update({'App-Version': latestVersion})
            

    # Set the API to which the route requests will go:
    # RequestHelper.ANIMETOON = Cartoons and dubbed anime (api.animetoon.tv),
    # RequestHelper.ANIMEPLUS = Subbed anime (api.animeplus.tv)
    def setAPISource(self, api):
        if api == self.API_ANIMETOON:
            self.apiURL = self.URL_API_ANIMETOON
            self.imageURL = self.URL_ANIMETOON_IMAGES
            self.searchURL = self.URL_ANIMETOON_SEARCH
            self.session.headers.update(self.animetoonHeaders)
        else:
            self.apiURL = self.URL_API_ANIMEPLUS
            self.imageURL = self.URL_ANIMEPLUS_IMAGES
            self.searchURL = self.URL_ANIMEPLUS_SEARCH
            self.session.headers.update(self.animeplusHeaders)


    # Used with show\movie name search.            
    def setDesktopHeader(self):
        del self.session.headers['App-LandingPage'] # Delete these app header items, just for safety.
        del self.session.headers['App-Name']
        del self.session.headers['App-Version']
        self.session.headers.update(self.getRandomHeader())
        
        
    def GET(self, url):
        return self.session.get(url, timeout = 8)

        
    def POST(self, url, data):
        return self.session.post(url, data = data, timeout = 8) # Unused function so far.
        

    # Convenience function to GET from a route path.
    # Assumes 'routeURL' starts with a forward slash.
    def routeGET(self, routeURL):
        r = self.GET(self.apiURL + routeURL)
        if r.ok:
            return r.json()
        else:
            return None

            
    def searchGET(self, query):
        return self.GET(self.searchURL % query)

    
    def makeThumbURL(self, id):
        return self.imageURL + str(id) + '.jpg' # 'imageURL' changes depending on the API set in setAPISource().
        
        
    def apiDelay(self, startTime, delayOverride = 0):
        elapsed = int((datetime.now() - startTime).total_seconds() * 1000)
        actualDelay = self.API_REQUEST_DELAY if not delayOverride else delayOverride
        if elapsed < actualDelay:
            sleep(max(actualDelay - elapsed, 100))
            
        
    def getRandomHeader(self):
        randomUA = getRawWindowProperty(self.PROPERTY_RANDOM_USERAGENT)
        if not randomUA:
            # Random user-agent logic. Thanks to http://edmundmartin.com/random-user-agent-requests-python/
            from random import choice
            randomUA = choice(self._desktopUserAgents())
            setRawWindowProperty(self.PROPERTY_RANDOM_USERAGENT, randomUA)
        return {
            'User-Agent': randomUA,
            'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8'
        }
        
        
    def _desktopUserAgents(self):
        desktop_agents = (
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML, like Gecko) Version/10.0.1 Safari/602.2.14',
            'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
            'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0'
        )
        return desktop_agents

            
requestHelper = RequestHelper()
