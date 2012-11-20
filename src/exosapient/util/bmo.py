from xo.scraping import ParseError, RequestError, Page, FormPage, Session
from exosapient.model.local import bmo_user, bmo_pass


def run():
    bmo = BMO()
    return bmo


class BMO(object):
    session = None

    def __init__(self, login=True, cookie_jar=None):
        self.session = Session(jar=cookie_jar)
        if login:
            self.login()

    def login(self):
        self.bmohome = BMOHomePage(session=self.session)
        self.card = self.bmohome.next().parse(_save=True)


    def __ansistr__(self):
        out = []
        return "\n".join(out)


class BMOHomePage(Page):
    def __init__(self, url='http://www.bmo.com/home', *args, **kwargs):
        return super(BMOHomePage, self).__init__(url=url, *args, **kwargs)

    @Page.parser
    def parse(self):
        link = self.soup.find(lambda e: e.name == 'a' and e.string == 'Online Banking')
        if not link:
            raise ParseError('"Online Banking" link not found')

        self.link = link['href']
        return self

    def next(self):
        return LoginPage(url=self.link, session=self.session)

class LoginPage(Page):
    @Page.parser
    def parse(self):
        return self

