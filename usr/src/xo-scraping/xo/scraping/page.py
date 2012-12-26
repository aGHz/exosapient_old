from bs4 import BeautifulSoup, Comment
from functools import wraps
import urlparse

from xo.scraping.exc import ParseError, RequestError
from xo.scraping.session import Session

_DEBUG = False


class Page(object):
    def __init__(self, body=None, session=None, url=None, data=None, _parse=True, *args, **kwargs):
        if session is None:
            session = Session()
        self.session = session
        self.url = url
        self.data = data
        self.body = body
        if _parse:
            self.parse()

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
            if _DEBUG:
                from pprint import pprint
                print "POST"
                print self.url
                pprint(self.data)
                self.session.print_cookies()
            (self.response, self.body) = self.session.post(self.url, self.data)
        self.url = self.response.url
        return self

    def parse(self, *args, **kwargs):
        return self

    @classmethod
    def parser(cls, parser):
        @wraps(parser)
        def wrapper_parser(self, *args, **kwargs):
            if self.body is None:
                if '_body' in kwargs:
                    self.body = kwargs['_body']
                else:
                    self.request(**kwargs.get('_data', {}))
            self.soup = body_to_soup(self.body)
            save = kwargs.get('_save', False)
            if save or _DEBUG:
                from datetime import datetime
                f = open('/tmp/{cls}_{now}.html'.format(
                    cls=self.__class__.__name__,
                    now=datetime.now().strftime('%Y%m%d_%H%M')), 'w')
                f.write(BeautifulSoup(self.body).prettify().encode('utf8')) # want comments, don't use body_to_soup
                f.close()
            try:
                if '_body' in kwargs: del kwargs['_body']
                if '_data' in kwargs: del kwargs['_data']
                if '_save' in kwargs: del kwargs['_save']
                return parser(self, *args, **kwargs)
            except Exception:
                # Save the response on exception, but only if not called with _save=True
                if not save and not _DEBUG:
                    from datetime import datetime
                    f = open('/tmp/{cls}_{now}.html'.format(
                        cls=self.__class__.__name__,
                        now=datetime.now().strftime('%Y%m%d_%H%M')), 'w')
                    f.write(self.soup.prettify().encode('utf8'))
                    f.close()
                raise
        return wrapper_parser

    @classmethod
    def self_referrer(cls, next_func):
        @wraps(next_func)
        def wrapper_next(self, *args, **kwargs):
            self.session.referrer = self.url
            return next_func(self, *args, **kwargs)
        return wrapper_next

class FormPage(Page):
    def parse_form(self, *args, **kwargs):
        (self.form_action,
         self.form_method,
         self.form_inputs,
         self.form_data) = parse_bs4_form(self.form, self.url)
        return self

class DummyPage(object):
    """Encapsulates another page and returns it when next() is called.

    This is useful if you already got a hold of a page but upon inspection
    it turns out to be a page further down the chain. Simply create the
    proper Page object with your current response body, and wrap it in
    one or more DummyPages so that your call sequence can keep asking for
    .next() without conditional logic.

    Example:

        page = NextPage(url=..., data=..., session=..., _parse=False)
        try:
            page.parse()
        except ParseError:
            # NextPage couldn't parse it so response must've been ActualPage
            page = ActualPage(url=page.url, body=page.body, session=...)
            return DummyPage(page)
        else:
            return page

    This way in your call chain you can just:

        this_page = FirstPage(...)
        next_page = this_page.next(...) # executes the code above
        actual_page = next_page.next(...) # NextPage.next or DummyPage.next

    """

    def __init__(self, other_page, **kwargs):
        self.__other_page = other_page
        # Dummy attrs that this page would've normally had
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def next(self, *args, **kwargs):
        return self.__other_page


def parse_bs4_form(form, base_url=None):
    if getattr(form, 'name', None) != 'form':
        raise ParseError('Form not a BeautifulSoup4 form')

    inputs = {}
    for inp in form.find_all('input'):
        name = inp.get('name')
        if name:
            inputs[name] = dict(inp.attrs)

    data = dict(zip(inputs.keys(), [attrs.get('value', '').encode('ascii', 'ignore') for attrs in inputs.values()]))

    action = form['action']
    if base_url is not None:
        action = urlparse.urljoin(base_url, action)
    elif '://' not in action:
        print 'WARNING: parse_bs4_form: action "%s" relative but no base URL set' % action

    return (action, form['method'], inputs, data)

def body_to_soup(body):
    soup = BeautifulSoup(body)
    comments = soup.find_all(text=lambda e: isinstance(e, Comment))
    map(lambda e: e.extract(), comments) # they pose problems, just get them out
    return soup


