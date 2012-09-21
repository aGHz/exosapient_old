import cookielib
import os
import pickle
import urllib
import urllib2
import urlparse

UA_STRINGS = {
    'chrome21': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/537.1',
    }



class Session(object):
    def __init__(self, load_jar=None, ua_string='chrome21'):
        # Prepare cookie jar
        self.jar = cookielib.CookieJar()
        if isinstance(load_jar, basestring):
            if os.path.isfile(load_jar):
                with open(load_jar, 'r') as f:
                    cookies = pickle.load(f)
            else:
                cookies = pickle.loads(load_jar)
            for cookie in cookies:
                self.jar.set_cookie(cookie)

        # Prepare urllib2 opener
        ua_string = UA_STRINGS.get(ua_string, None)
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.jar))
        if ua_string is not None:
            self.opener.addheaders = [('User-agent', ua_string)]

    def submit_form(self, action, data, clear_next=True):
        self.prev_url = action
        self.prev_data = data

        resp = self.opener.open(action, urllib.urlencode(data))
        if clear_next: self.clear_next()
        return (resp, resp.read())

    def get_page(self, url, clear_next=True):
        self.prev_url = url
        self.prev_data = None

        resp = self.opener.open(url)
        if clear_next: self.clear_next()
        return (resp, resp.read())

    def parse_form(self, form):
        if form.name != 'form':
            raise Exception('Session.parse_form did not receive a BeautifulSoup form')

        inputs = {}
        for inp in form.find_all('input'):
            inputs[inp['name']] = dict(inp.attrs)

        data = dict(zip(inputs.keys(), [attrs.get('value', '').encode('ascii', 'ignore') for attrs in inputs.values()]))
        self.next_data = data

        if self.prev_url is not None:
            self.next_url = urlparse.urljoin(self.prev_url, form['action'])
        else:
            # TODO what if it's not a full URL?
            self.next_url = form['action']

        return (form['action'], form['method'], inputs, data)

    def submit_next(self, data={}):
        if self.next_url is None:
            raise Exception('Session.submit called with nowhere to go')
        if self.next_data is None:
            self.next_data = {}

        self.next_data.update(data)
        return self.submit_form(self.next_url, self.next_data)

    def data(self):
        return self.next_data
    def set_data(self, k, v):
        self.next_data[k] = v

    def cookies(self, name=None):
        cookies = [c for c in self.jar]
        if name is not None:
            if not isinstance(name, list):
                name = [name]
            cookies = [c for c in cookies if c.name in name]
        return cookies
    def print_jar(self):
        print '--- jar ---'
        for cookie in self.jar: print cookie
        print '-----------'

    def clear_prev(self):
        self.prev_url = None
        self.prev_data = None
    def clear_next(self):
        self.next_url = None
        self.next_data = None
    def clear_all(self):
        self.clear_prev()
        self.clear_next()
