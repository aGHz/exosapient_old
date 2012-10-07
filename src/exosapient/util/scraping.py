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


class Page(object):
    def __init__(self, body=None, session=None, url=None, data=None, *args, **kwargs):
        if session is None:
            session = Session()
        self.session = session
        self.url = url
        self.data = data
        self.body = body

    def request(self, url=None, data=None, force=False, *args, **kwargs):
        if self.body is not None and not force:
            return self

        if url is not None:
            self.url = url
        if self.url is None:
            raise RequestError('Page URL not set')

        if self.data is None:
            self.data = data
        elif data is not None:
            self.data.update(data)

        if self.data is None:
            (self.response, self.body) = self.session.get(self.url)
        else:
            (self.response, self.body) = self.session.post(self.url, self.data)
        self.url = self.response.url
        return self

    def parse(self, *args, **kwargs):
        return self

class FormPage(Page):
    def parse_form(self, *args, **kwargs):
        (self.form_action,
         self.form_method,
         self.form_inputs,
         self.form_data) = parse_bs4_form(self.form, self.url)
        return self


def parse_bs4_form(form, base_url=None):
    if getattr(form, 'name', None) != 'form':
        raise ParseError('Form not a BeautifulSoup4 form')

    inputs = {}
    for inp in form.find_all('input'):
        inputs[inp['name']] = dict(inp.attrs)

    data = dict(zip(inputs.keys(), [attrs.get('value', '').encode('ascii', 'ignore') for attrs in inputs.values()]))

    action = form['action']
    if base_url is not None:
        action = urlparse.urljoin(base_url, action)
    elif '://' not in action:
        print 'WARNING: parse_bs4_form: action "%s" relative but no base URL set' % action

    return (action, form['method'], inputs, data)


class ParseError(Exception):
    pass

class RequestError(Exception):
    pass
