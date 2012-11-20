from bs4 import BeautifulSoup, Comment
from functools import wraps
import urlparse

from xo.scraping.exc import ParseError, RequestError
from xo.scraping.session import Session


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
            if kwargs.get('_save', False):
                from datetime import datetime
                f = open('/tmp/{cls}_{now}.html'.format(
                    cls=self.__class__.__name__,
                    now=datetime.now().strftime('%Y%m%d_%H%M')), 'w')
                f.write(BeautifulSoup(self.body).prettify().encode('utf8')) # want comments, don't use body_to_soup
                f.close()
            try:
                return parser(self, *args, **kwargs)
            except Exception:
                if not kwargs.get('_save', False):
                    from datetime import datetime
                    f = open('/tmp/{cls}_{now}.html'.format(
                        cls=self.__class__.__name__,
                        now=datetime.now().strftime('%Y%m%d_%H%M')), 'w')
                    f.write(self.soup.prettify().encode('utf8'))
                    f.close()
                raise
        return wrapper_parser

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

def body_to_soup(body):
    soup = BeautifulSoup(body)
    comments = soup.find_all(text=lambda e: isinstance(e, Comment))
    map(lambda e: e.extract(), comments) # they pose problems, just get them out
    return soup


