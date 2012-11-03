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
from exosapient.util.ansi import colors as ansi

MONTHS = dict(zip(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                   'September', 'October', 'November', 'December'
                  ], range(1, 13)))

def login(cookie_jar=None):
    session = scraping.Session(jar=cookie_jar)
    mbnahome = MBNAHomePage(session=session).request().parse()
    security = mbnahome.next(user=mbna_user).parse() # already requested in MBNAHomePage
    password = security.next(answer=mbna_security[security.question]).request().parse()
    overview = password.next(password=mbna_pass).request().parse()
    return overview

def test(cookie_jar=None):
    session = scraping.Session(jar=cookie_jar)

    mbnahome = MBNAHomePage(session=session).request().parse()
    security = mbnahome.next(user=mbna_user).parse()
    password = security.next(answer=mbna_security[security.question]).request().parse()
    overview = password.next(password=mbna_pass).request().parse()
    snapshot = overview.next(account=overview.__dict__.keys()[0]).request().parse()

    statement = snapshot.next(link='statements').request().parse()
    s1 = statement.next(statement_index=3).request().parse()

    pprint(overview.__dict__)
    pprint(snapshot.__dict__)
    pprint(statement.__dict__)
    pprint(s1.__dict__)

    return (session, overview, snapshot, statement, s1)


class MBNA(object):
    session = None
    overview = None
    snapshots = {}
    statements = {}

    def __init__(self, login=True, cookie_jar=None):
        self.session = scraping.Session(jar=cookie_jar)
        if login:
            self.get_overview()

    def get_overview(self):
        if self.overview is None:
            mbnahome = MBNAHomePage(session=self.session).request().parse()
            security = mbnahome.next(user=mbna_user).parse()
            password = security.next(answer=mbna_security[security.question]).request().parse()
            overview = password.next(password=mbna_pass).request().parse()

            self.overview = overview

    @property
    def accounts(self):
        if self.overview is None:
            self.get_overview()
        return self.overview.__dict__.keys()

    def get_snapshot(self, account, force=False):
        if self.overview is None:
            self.get_overview()
        if force or account not in self.snapshots:
            self.snapshots[account] = self.overview.next(account=account).request().parse()
        return self.snapshots[account]

    def load_snapshots(self, force=True):
        if self.overview is None:
            self.get_overview()
        for account in self.accounts:
            self.get_snapshot(account, force=force)
        return self.snapshots

    def get_latest_statement(self, account, force=False):
        if self.overview is None:
            self.get_overview()
        if force or account not in self.statements:
            self.statements[account] = {}
        snapshot = self.get_snapshot(account)
        if force or '_latest' not in self.statements[account]:
            statement = snapshot.next(link='statements').request().parse()
            self.statements[account]['_latest'] = statement
            self.statements[account][statement.date] = statement
            for s in statement.statements:
                self.statements[account][s['closing_date']] = s
        return self.statements[account]['_latest']

    def load_latest_statements(self, force=True):
        if self.overview is None:
            self.get_overview()
        for account in self.accounts:
            self.get_latest_statement(account, force=force)
        return self.statements


    def __ansistr__(self):
        out = []
        for account in self.accounts:
            # first line: account, numbers, gauge
            line = "{yellow}{account}{reset}  "
            if account not in self.snapshots:
                data = self.overview.accounts[account]
                line += "{green}" if data['available'] > 0 else "{red}"
                line += "{available}{reset}"
                # second line: pay due
                line += "  Due: "
                line += "{red}" if data['pay_amount'] > 0 else "{green}"
                line += "{amount}{reset} on "
                if datetime.date.today() > data['pay_date']:
                    line += "{red}" if data['pay_amount'] > 0 else "{white}"
                else:
                    line += "{yellow}" if data['pay_amount'] > 0 else "{green}"
                line += "{duedate}{reset}"
                out += [line.format(account=account,
                                    available=data['available'],
                                    amount=data['pay_amount'],
                                    duedate=data['pay_date'].strftime("%a, %b %d, %Y"),
                                    **ansi)]
                out += [""]
                continue

            snap = self.snapshots[account]
            # generate gauge
            percent = round(100*100*(snap.balance+snap.temp)/snap.limit)/100
            perfifty = int(round(50*(snap.balance+snap.temp)/snap.limit))
            #gauge = ("{red}" if perfifty > 0 else "{green}") + "["
            gauge = "["
            if perfifty > 0:
                gauge += "{red}" + "*" * perfifty
            if perfifty < 50:
                gauge += "{green}" + "=" * (50 - perfifty)
            gauge += "]{reset}"

            # first line: account, numbers, gauge
            line = "{yellow}{account}{reset}  "

            numbers = []
            if snap.available:
                numbers += ["{green}{available}{reset}"]
            if snap.temp:
                numbers += ["{yellow}{temp}{reset}"]
            if snap.balance:
                numbers += ["{red}{balance}{reset}"]
            line += " + ".join(numbers)
            line += " > " if snap.balance > snap.limit else " = "
            line += "{limit}  "

            line += gauge + " {percent}%"

            out += [line.format(account=account,
                                available=snap.available,
                                temp=snap.temp,
                                balance=snap.balance,
                                limit=snap.limit,
                                percent=percent,
                                **ansi)]

            # second line: pay due
            line = " " * (len(account) + 2)
            line += "Due:  "
            if datetime.date.today() < snap.pay_date:
                line += "{yellow}" if snap.pay_amount > 0 else "{green}"
            else:
                line += "{red}" if snap.pay_amount > 0 else "{white}"
            line += "{amount} on {duedate}{reset}"
            out += [line.format(amount=snap.pay_amount,
                                duedate=snap.pay_date.strftime("%a, %b %d, %Y"),
                                **ansi)]

            # third line: last payment
            line = " " * (len(account) + 2)
            line += "Paid: "
            if snap.last_pay_date < snap.last_stmt_date:
                line += "{red}"
            elif snap.last_pay_date >= snap.last_stmt_date and snap.last_pay_date <= snap.pay_date:
                line += "{green}"
            elif snap.last_pay_date > snap.pay_date and snap.last_pay_date < snap.next_stmt_date:
                line += "{yellow}"
            line += "{amount} on {duedate}{reset}"
            out += [line.format(amount=snap.last_pay_amount,
                                duedate=snap.last_pay_date.strftime("%a, %b %d, %Y"),
                                **ansi)]

            # fourth line: next statement
            line = " " * (len(account) + 2)
            line += "Next: on "
            days_left = (snap.next_stmt_date - datetime.date.today()).days
            if days_left <= 5:
                line += "{yellow}"
            elif days_left <= 10:
                line += "{green}"
            else:
                line += "{white}"
            line += "{nextdate}{reset}"
            out += [line.format(nextdate=snap.next_stmt_date.strftime("%a, %b %d, %Y"),
                                **ansi)]


            # lines 6+: activity
            line = " " * (len(account) + 2) + "-" * 86
            out += [line]

            activities = sorted(snap.activity, key=lambda a: a['trans_date'], reverse=True)
            for activity in activities:
                line = " " * (len(account) + 2)
                if activity['amount'] < 0:
                    color = "{green}"
                elif activity['ref_num'] == 'TEMP':
                    color = "{yellow}"
                else:
                    color = "{blue}"
                line += color + "{date}{reset} "
                if activity['amount'] < 0:
                    line += "{green}"
                elif activity['ref_num'] == 'TEMP':
                    line += "{yellow}"
                line += "{amount: >8.2f}{reset}  " + color + "{desc}{reset}"
                out += [line.format(date=activity['trans_date'].strftime("%a, %b %d, %Y"),
                                    amount=activity['amount'],
                                    desc=activity['desc'],
                                    ref=activity['ref_num'],
                                    **ansi)]

            # lines A+1+: latest statement
            if '_latest' in self.statements.get(account, {}):
                line = " " * (len(account) + 2) + "-" * 86
                out += [line]

                statement = self.statements[account]['_latest']
                out += [statement.__ansistr__(prefix=" " * (len(account) + 2))]

            out += [""]

        return "\n".join(out)


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
                'url': urlparse.urljoin(self.url, link),
                'available': dollar_to_float(data_raw['Credit Available:']),
                'pay_amount': dollar_to_float(pay['amt']),
                'pay_date': datetime.date(int(pay['Y']), int(pay['M']), int(pay['D'])),
                }

        self.accounts = accounts
        return self

    def next(self, account=None):
        if account is not None:
            return SnapshotPage(url=self.accounts[account]['url'], session=self.session)

    @property
    def __dict__(self):
        return self.accounts


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
        updated = datetime.datetime(int(m['Y']),
                                    MONTHS.get(m['month'], None),
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

        # Extract various links
        self.links = {}
        statements_a = soup.find('a', text=re.compile('Statements'))
        if statements_a is None:
            raise ParseError('a[text="Statements"] not found')
        self.links['statements'] = urlparse.urljoin(self.url, statements_a['href'])

        return self

    def next(self, link=None):
        if link == 'statements':
            url = self.links[link]
            return StatementPage(url=url, session=self.session)

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
            'links': self.links,
            }


class StatementPage(scraping.FormPage):
    def parse(self, body=None):
        if body is not None:
            self.body = body
        soup = body_to_soup(self.body)

        # Parse list of available statements
        stmts_select = soup.select('select[name="STMT"]')
        if stmts_select:
            stmts_select = stmts_select[0]
        else:
            raise scraping.ParseError('select[name="STMT"] not found')
        self.form = stmts_select.find_parent('form')
        self.parse_form()
        self.form_data['acrobatCheck'] = 3
        stmt_values = [o['value'] for o in stmts_select.find_all('option')][:-2]
        self.statements = []
        for stmt in stmt_values:
            (m, d, y) = [int(s) for s in stmt.split('.')[2].split('-')]
            self.form_data['STMT'] = stmt
            self.statements.append({
                'closing_date': datetime.date(y, m, d),
                'url': urlparse.urljoin(self.form_action, '?' + urllib.urlencode(self.form_data)),
                'value': stmt,
                })
        del self.form_data['STMT']

        # Parse statement date
        stmt_date = soup.find('p', class_='stmtDate').text.strip()
        (m, d, y) = re.match('^(\w*) (\d*), (\d*)$', stmt_date).groups()
        self.date = datetime.date(int(y), MONTHS[m], int(d))

        # Parse statement header data
        header_t = soup.find('table', class_='acctdetailmodule')
        header_ths = [" ".join(map(lambda s: s.strip(), th.strings)) for th in header_t.findAll('th')]
        header_tds = [" ".join(map(lambda s: s.strip(), td.strings)) for td in header_t.findAll('td')]
        header = dict(zip(header_ths, header_tds))
        for k in header.keys():
            if header[k].startswith('$'):
                header[k] = dollar_to_float(header[k])
        header['Account Number'] = re.match('^Ending in (?P<cc>\d+)$', header['Account Number']).group('cc')
        self.account = header['Account Number']
        header['Statement Closing Date'] = str_to_date(header['Statement Closing Date'])
        header['Total Min. Payment Due Date'] = str_to_date(header['Total Min. Payment Due Date'])
        self.header = header
        self.days = int(header['Days in Billing Cycle'])
        self.available = header['Credit Available']
        self.limit = header['Credit Limit']
        self.balance = self.limit - self.available
        self.pay_amount = header['Total Min. Payment Due']
        self.pay_date = header['Total Min. Payment Due Date']

        # Parse statement activity
        activity_t = soup.find('table', class_='acctregistermodule')
        activity_trs = activity_t.find_all('tr')[1:]
        activity_data = [[td.text.strip() for td in tr.find_all('td')] for tr in activity_trs]
        currencies = {
            'U.S. DOLLARDOLLAR': 'USD',
            'U.S. DOLLAR': 'USD',
            }
        sections = {
            'Payments and Other Credits': 'debit',
            'Purchases and Adjustments': 'credit',
            'Interest Charged': 'interest',
            }
        activity = []
        activity_type = None
        for row in activity_data:
            (trans_date, post_date, desc, offer_id, ref_num, amt) = row
            desc = re.sub('\s+', ' ', desc)
            amt = dollar_to_float(amt)
            trans_date = str_to_date(trans_date)
            if desc in sections:
                activity_type = sections[desc]
                continue
            if not trans_date:
                if desc.startswith('FOREIGN CURRENCY'):
                    (amt, currency) = desc[17:].split(' ', 1)
                    activity[-1].update({
                        'foreign_amount': dollar_to_float(amt),
                        'foreign_currency': currencies.get(currency, currency),
                        })
                    continue
                if desc.startswith('Interest on'):
                    trans_date = activity[-1]['trans_date']
            act = {
                'type': activity_type,
                'trans_date': trans_date,
                'post_date': str_to_date(post_date),
                'ref_num': ref_num,
                'amount': amt,
                }
            if activity_type == 'credit':
                # parse desc into name and location
                (name, location) = desc.split(' - ', 1)
                name = ' '.join([s.capitalize() for s in name.split(' ')])
                location = location.split(' ')
                location = ' '.join([s.capitalize() for s in location[:-1]] + location[-1:])
                act.update({
                    'desc_raw': desc,
                    'desc': name,
                    'location': location,
                    })
            else:
                act.update({
                    'desc': desc,
                    })
            activity.append(act)
        self.activity = activity

        return self

    def next(self, statement_index=None):
        if statement_index is not None and statement_index < len(self.statements):
            return StatementPage(url=self.statements[statement_index]['url'], session=self.session)

    @property
    def __dict__(self):
        return {
            'date': self.date,
            'statements': [stmt['closing_date'] for stmt in self.statements],
            }

    def __ansistr__(self, prefix=""):
        out = []
        line = prefix + '{bold}{magenta}{due_date} {due_amt: >8.2f}  Minimum payment due'
        out += [line.format(due_amt=self.pay_amount, due_date=self.pay_date.strftime("%a, %b %d, %Y"),
                            **ansi)]
        line = prefix + '{bold}{magenta}{date} {amount: >8.2f}  Statement covering {days} days, limit of {limit:.2f}'
        out += [line.format(date=self.date.strftime("%a, %b %d, %Y"), days=self.days,
                            amount=self.balance, limit=self.limit, **ansi)]

        activities = self.activity
        activities = sorted(self.activity, key=lambda a: (a['trans_date'], a['amount']), reverse=True)
        for activity in activities:
            line = prefix
            params = ansi.copy()

            if activity['amount'] < 0:
                color = "{green}"
            elif activity['type'] == 'interest':
                color = "{yellow}"
            else:
                color = "{blue}"
            line += color + "{date}{reset} "
            if activity['amount'] < 0:
                line += "{green}"
            elif activity['type'] == 'interest':
                if activity['amount'] > 0:
                    line += "{red}"
                else:
                    line += "{yellow}"
            if type(activity['amount']) == float:
                line += "{amount: >8.2f}{reset}  "
            else:
                line += " " * 12
            line += color + "{desc}{reset}"
            if activity.get('location', None):
                line += ", {location}{reset}"
            act_date = activity['trans_date'].strftime("%a, %b %d, %Y") if activity['trans_date']\
                            else " " * 17
            out += [line.format(date=act_date,
                                amount=activity['amount'],
                                desc=activity['desc'],
                                ref=activity['ref_num'],
                                location=activity.get('location', ''),
                                **ansi)]
        return "\n".join(out)

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
