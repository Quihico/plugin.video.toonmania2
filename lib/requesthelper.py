# -*- coding: utf-8 -*-
import requests

from lib.common import setRawWindowProperty, getRawWindowProperty


# A requests helper class just for the Animetoon and Animeplus APIs.

class RequestHelper():

    URL_API_ANIMETOON = 'http://api.animetoon.tv'
    URL_ANIMETOON_IMAGES = 'http://www.animetoon.tv/images/series/small/' # Replace 'small' with 'big' to get larger thumbs.
    URL_ANIMETOON_SEARCH = 'http://www.animetoon.org/toon/search?key=%s'

    URL_API_ANIMEPLUS = 'http://api.animeplus.tv'
    URL_ANIMEPLUS_IMAGES = 'http://www.animeplus.tv/images/series/small/'
    URL_ANIMEPLUS_SEARCH = 'http://www.animeplus.tv/anime/search?key=%s'

    # Persistent window property holding the app version obtained from
    # the '/GetVersion' API route.
    PROPERTY_VERSION = 'requesthelper.version'

    def __init__(self):
        self.animetoonHeaders = {
            'User-Agent': 'okhttp/2.3.0',
            'App-LandingPage': 'http://www.mobi24.net/toon.html',
            'App-Name': '#Toonmania',
            'App-Version': '8.0'
        }
        self.animeplusHeaders = {
            'User-Agent': 'okhttp/2.3.0',
            'App-LandingPage': 'http://www.mobi24.net/anime.html',
            'App-Name': '#Animania',
            'App-Version': '8.0'
        }
        self.session = requests.Session()
        self.setAPISource(0) 
        
        latestVersion = getRawWindowProperty(self.PROPERTY_VERSION)
        if not latestVersion:
            jsonData = self.routeGET('/GetVersion')
            version = jsonData.get('version', '8.0')
            self.animetoonHeaders.update({'App-Version': version})
            self.animeplusHeaders.update({'App-Version': version})
            setRawWindowProperty(self.PROPERTY_VERSION, version)
            

    # API source:
    # 0 = Cartoons and dubbed anime (api.animetoon.tv),
    # 1 = Subbed anime (api.animeplus.tv)
    def setAPISource(self, source):
        if source == 0:
            self.apiURL = self.URL_API_ANIMETOON
            self.imageURL = self.URL_ANIMETOON_IMAGES
            self.searchURL = self.URL_ANIMETOON_SEARCH
            self.session.headers.update(self.animetoonHeaders)
        else:
            self.apiURL = self.URL_API_ANIMEPLUS
            self.imageURL = self.URL_ANIMEPLUS_IMAGES
            self.searchURL = self.URL_ANIMEPLUS_SEARCH
            self.session.headers.update(self.animeplusHeaders)
        
            
    def GET(self, url):
        return self.session.get(url, timeout = 8)


    # Convenience function to GET from a route path. Assumes 'routeURL' starts with a forward slash.
    def routeGET(self, routeURL):
        r = self.GET(self.apiURL + routeURL)
        if r.ok:
            return r.json()
        else:
            return None


    def POST(self, url, data):
        return self.session.post(url, data = data, timeout = 8)

    
    def makeThumbURL(self, id):
        return self.imageURL + str(id) + '.jpg' # Changes depending on the API set in setAPISource().

        
    """
    def getCustomHeader()
        # Random user-agent logic. Thanks to http://edmundmartin.com/random-user-agent-requests-python/
        from random import choice
        desktop_agents = [
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
        ]
        randomHeader = {
            'User-Agent': choice(desktop_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,image/webp,*/*;q=0.8'}
        return randomHeader
    """

            
requestHelper = RequestHelper()
