import cookielib
import os
import pickle
import urllib
import urllib2

from xo.scraping.ua import user_agent


class Session(object):
    def __init__(self, jar=None, ua_string='chrome21'):
        # Prepare cookie jar
        # The jar parameter can be either a string containing a pickled list of cookies
        # or a path to a file containing such a string
        self.jar = cookielib.CookieJar()
        if isinstance(jar, basestring):
            if os.path.isfile(jar):
                with open(jar, 'r') as f:
                    cookies = pickle.load(f)
            else:
                cookies = pickle.loads(jar)
            for cookie in cookies:
                self.jar.set_cookie(cookie)

        # Prepare urllib2 opener
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.jar))
        self._headers = {'User-agent': user_agent(ua_string)}

    def get(self, url):
        self.opener.addheaders = self.headers
        resp = self.opener.open(url)
        del self.referrer
        return (resp, resp.read())

    def post(self, url, data):
        self.opener.addheaders = self.headers
        resp = self.opener.open(url, urllib.urlencode(data))
        del self.referrer
        return (resp, resp.read())

    def cookies(self, name=None):
        cookies = [c for c in self.jar]
        if name is not None:
            if not isinstance(name, list):
                name = [name]
            cookies = [c for c in cookies if c.name in name]
        return cookies

    def print_cookies(self):
        print '--- [cookie jar] ' + '-' * 62
        for cookie in self.jar: print cookie
        print '-' * 79

    @property
    def headers(self):
        return [(k, v) for k, v in self._headers.iteritems() if v is not None]

    @property
    def referrer(self):
        return self._headers.get('Referer', None)

    @referrer.setter
    def referrer(self, referrer):
        self._headers['Referer'] = referrer

    @referrer.deleter
    def referrer(self):
        self._headers.pop('Referer', None)

