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
        ua_string = UA_STRINGS.get(ua_string, None)
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.jar))
        if ua_string is not None:
            self.opener.addheaders = [('User-agent', ua_string)]

    def get(self, url):
        resp = self.opener.open(url)
        return (resp, resp.read())

    def post(self, url, data):
        resp = self.opener.open(url, urllib.urlencode(data))
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

    # --- deprecated ---

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

    def clear_prev(self):
        self.prev_url = None
        self.prev_data = None
    def clear_next(self):
        self.next_url = None
        self.next_data = None
    def clear_all(self):
        self.clear_prev()
        self.clear_next()


class Scraper(object):
    def __init__(self, body=None, session=None, **kwargs):
        self.session = session
        if body is not None:
            self.parse(body=body, **kwargs)

    def parse(*args, **kwargs):
        pass

    def parse_form(self, form=None, base_url=None):
        if form is not None:
            self.form = form

        if getattr(self.form, 'name', None) != 'form':
            raise Exception('Scraper.parse_form did not receive a BeautifulSoup form')

        inputs = {}
        for inp in self.form.find_all('input'):
            inputs[inp['name']] = dict(inp.attrs)

        data = dict(zip(inputs.keys(), [attrs.get('value', '').encode('ascii', 'ignore') for attrs in inputs.values()]))

        action = self.form['action']
        if base_url is not None:
            action = urlparse.urljoin(base_url, action)
        elif '://' not in action:
            print 'WARNING: Scraper.parse_form: action "%s" relative but no base_url provided' % action

        self.action = action
        self.method = self.form['method']
        self.inputs = inputs
        self.data = data
        return self

    def set_data(self, k, v):
        self.data[k] = v
        return self

    def next(self, data=None, url=None, page_class=None):
        if url is None:
            url = self.action
        if url is None:
            raise Exception('Action not set')
        if page_class is None:
            page_class = self._next_scraper_class

        if getattr(self, 'data', None) is None:
            (resp, body) = self.session.get(url)
        else:
            self.data.update(data)
            (resp, body) = self.session.post(url, self.data)
        return page_class(body=body, session=self.session, url=url)



class ParseError(Exception):
    pass
