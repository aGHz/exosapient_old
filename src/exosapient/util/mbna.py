from bs4 import BeautifulSoup, Comment
import cookielib
import datetime
from pprint import pprint
import re
import urllib
import urllib2
import urlparse

from exosapient.model.local import mbna_user, mbna_security, mbna_pass
from exosapient.util import scraping

re_question = re.compile('label [^>]*?question_id', re.I | re.M | re.S | re.U)

def login(cookie_jar=None, debug=False):
    session = scraping.Session(jar=cookie_jar)

    mbnahome = MBNAHomePage(session=session).request().parse()
    security = mbnahome.next(user=mbna_user).parse() # already requested in MBNAHomePage
    password = security.next(answer=mbna_security[security.question]).request().parse()
    overview = password.next(password=mbna_pass).request().parse()
    snapshot = overview.next(account=overview.__dict__.keys()[0]).request().parse()

    pprint(overview.__dict__)
    pprint(snapshot.__dict__)

    return (session, overview, snapshot)


class SnapshotPage(scraping.Page):
    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        # Extract last 4 digits from page header
        header = soup.find('form', action='HeaderController')
        account = header.find('td', class_='accountIdContainer').stripped_strings.next()
        account = re.match('^.* ending in (?P<cc>\d+)$', account).group('cc')
        self.account = account

        # Extract last_updated from overview table header
        overview = header.find_next_sibling('table')
        overview_t = overview.find('table').find('table')
        updated = overview_t.stripped_strings.next()
        m = re.match('^As of (?P<month>\w+) (?P<D>\d+), (?P<Y>\d+) (?P<h>\d+):(?P<m>\d+) ET$',
                     updated).groupdict()
        months = dict(zip(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                           'September', 'October', 'November', 'December'
                          ], range(1, 13)))
        updated = datetime.datetime(int(m['Y']),
                                    months.get(m['month'], None),
                                    int(m['D']),
                                    int(m['h']),
                                    int(m['m']))
        self.updated = updated

        # Extract overview data
        overview_t = overview_t.find('table') # We must go deeper!
        # Pull all the rows into a nice dictionary
        overview_trs = [tr for tr in overview_t.find_all('tr') if len(list(tr.children)) > 3]
        overview_tds = [[td.text.strip() for td in tr.find_all('td')] for tr in overview_trs]
        overview_data = dict([(td[0], td[1]) for td in overview_tds]) # only the first 2 matter: key and value
        # Synthesize the data into object fields
        pay = re.split('\s+', overview_data['Total Minimum Payment Due:'])
        last_balance = re.split('\s+', overview_data['Last Statement Balance:'])
        last_pay = re.split('\s+', overview_data['Last Payment Posted:'])
        self.available = dollar_to_float(overview_data['Credit Available:'])
        self.balance = dollar_to_float(overview_data['Current Balance:'])
        self.temp = dollar_to_float(overview_data['Temporary Authorizations:'])
        self.limit = dollar_to_float(overview_data['Credit Limit:'])
        self.pay_amount = dollar_to_float(pay[0])
        self.pay_date = str_to_date(pay[-1])
        self.last_stmt_balance = dollar_to_float(last_balance[0])
        self.last_stmt_date = str_to_date(last_balance[-1])
        self.last_stmt_due = dollar_to_float(overview_data['Past Due Amount:'])
        self.last_pay_amount = dollar_to_float(last_pay[0])
        self.last_pay_date = str_to_date(last_pay[-1])

        # Extract activity data
        (activity_hdr, activity_t) = overview.find_next_sibling('table').find_all('table')

        next_date = activity_hdr.find('th', class_='rightmodheader').text.strip().split(' ')[-1]
        self.next_stmt_date = str_to_date(next_date)

        activity_trs = activity_t.find_all('tr')[1:]
        activity_data = [[td.text.strip() for td in tr.find_all('td')] for tr in activity_trs]
        activity = []
        for row in activity_data:
            (trans_date, post_date, desc, offer_id, ref_num, amt) = row
            if not trans_date:
                continue
            activity.append({
                'trans_date': str_to_date(trans_date),
                'post_date': str_to_date(post_date),
                'desc': re.sub('\s+', ' ', desc),
                'ref_num': ref_num,
                'amount': dollar_to_float(amt),
                })

        self.activity = activity
        return self

    @property
    def __dict__(self):
        return {
            'account': self.account,
            'updated': self.updated,
            'available': self.available,
            'balance': self.balance,
            'temp': self.temp,
            'limit': self.limit,
            'pay_amount': self.pay_amount,
            'pay_date': self.pay_date,
            'last_stmt_balance': self.last_stmt_balance,
            'last_stmt_date': self.last_stmt_date,
            'last_stmt_due': self.last_stmt_due,
            'last_pay_amount': self.last_pay_amount,
            'last_pay_date': self.last_pay_date,
            'next_stmt_date': self.next_stmt_date,
            'activity': self.activity,
            }


class OverviewPage(scraping.Page):
    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        accounts = {}
        account_tds = soup.select('td.accountName')
        for account_td in account_tds:
            a = account_td.find('a')
            number = re.search('ending in (?P<cc>\d+)', a.text).group('cc')
            link = a.attrs['href']

            info_tr = account_td.find_parent('table').find_parent('tr').find_next_sibling('tr')
            data_trs = info_tr.find('table').find_all('tr')
            data_raw = dict([
                (data_tr.find('td', class_='bodyCopy').text.strip(),
                 data_tr.find('td', class_='bodyCopyBold').text.strip())
                for data_tr in data_trs
                if len(data_tr.find_all('td'))>1
                ])

            pay = re.match('^\$(?P<amt>[.0-9]+)\s+due\s+(?P<M>\d+)/(?P<D>\d+)/(?P<Y>\d+)$',
                           data_raw['Total Minimum Payment Due:']).groupdict()

            accounts[number] = {
                'link': urlparse.urljoin(self.url, link),
                'available': dollar_to_float(data_raw['Credit Available:']),
                'pay_min': dollar_to_float(pay['amt']),
                'pay_date': datetime.date(int(pay['Y']), int(pay['M']), int(pay['D'])),
                }

        self.accounts = accounts
        return self

    def next(self, account=None):
        if account is not None:
            return SnapshotPage(url=self.accounts[account]['link'], session=self.session)

    @property
    def __dict__(self):
        return self.accounts


class PasswordPage(scraping.FormPage):
    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        form = soup.find('form', id='pwd_form.id')
        if form is None:
            raise scraping.ParseError('form[id="pwd_form.id"] not found')

        self.form = form
        self.parse_form()
        if 'password' not in self.form_data:
            raise scraping.ParseError('input[name="password"] not found')
        return self

    def next(self, password):
        self.form_data.update({'password': password})
        return OverviewPage(url=self.form_action, data=self.form_data, session=self.session)

class SecurityQuestion(scraping.FormPage):
    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        try:
            q = soup.select('label#question_id')[0]
        except Exception:
            raise scraping.ParseError('label#question_id not found')

        self.question = q.text
        self.form = q.find_parent('form')
        self.parse_form()
        if 'answer' not in self.form_data:
            raise scraping.ParseError('input[name="answer"] not found')
        return self

    def next(self, answer):
        self.form_data.update({'answer': answer})
        return PasswordPage(url=self.form_action, data=self.form_data, session=self.session)


class ChallengeRedirect(scraping.Page):
    def parse(self, body=None):
        if body is not None:
            self.body = body

        re_goto = re.compile('goto\(\'(?P<url>.*?)\'\)', re.I | re.M | re.S | re.U)
        m = re_goto.search(self.body)
        if m is None:
            raise scraping.ParseError('goto(\'...\') not found')

        self.goto = m.group('url')
        return self

    def next(self):
        url = urlparse.urljoin(self.url, self.goto)
        return SecurityQuestion(url=url, session=self.session)


class MBNAHomePage(scraping.FormPage):
    def __init__(self, url='http://mbna.ca/index.html', *args, **kwargs):
        return super(MBNAHomePage, self).__init__(url=url, *args, **kwargs)

    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        form = soup.find('form')
        if not form.select('div.signinform'):
            raise scraping.ParseError('div.signinform not found in first form')

        self.form = form
        self.parse_form()
        if 'username' not in self.form_data:
            raise scraping.ParseError('input[name="username"] not found')
        return self

    def next(self, user):
        # NB! Don't do MBNAHomePage.next().request()
        # We must perform the request here to check if it's a challenge redirect page,
        # a maintenance page or a security question page, so you only need to parse() the result
        self.form_data.update({'username': user})
        (resp, body) = self.session.post(self.form_action, self.form_data)
        if 'Maintenance' in resp.url:
            raise MaintenanceError()
        try:
            redirect = ChallengeRedirect(url=resp.url, body=body, session=self.session).parse()
        except scraping.ParseError:
            return SecurityQuestion(url=resp.url, body=body, session=self.session)
        else:
            return redirect.next().request()


class MaintenanceError(Exception):
    def __init__(self):
        super(MaintenanceError, self).__init__('MBNA site currently under maintenance')

def dollar_to_float(s):
    # Remove anything that isn't a digit or a period and convert to float
    try:
        amount = float(re.sub('[^\d.+-]', '', s))
    except Exception:
        return None
    else:
        return amount

def str_to_date(s):
    try:
        (month, day, year) = [int(n) for n in s.split('/')]
        date = datetime.date(year, month, day)
    except Exception:
        return None
    else:
        return date

def body_to_soup(body):
    soup = BeautifulSoup(body)
    comments = soup.find_all(text=lambda e: isinstance(e, Comment))
    map(lambda e: e.extract(), comments) # they pose problems, just get them out
    return soup
