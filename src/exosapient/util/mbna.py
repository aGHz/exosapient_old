from bs4 import BeautifulSoup, Comment
import cookielib
import datetime
from pprint import pprint
import re
import urllib
import urllib2
import urlparse

from xo.scraping.exc import ParseError, RequestError
from xo.scraping.page import Page, FormPage
from xo.scraping.session import Session

from exosapient.model.local import mbna_user, mbna_security, mbna_pass
from exosapient.util.ansi import colors as ansi


MONTHS = dict(zip(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                   'September', 'October', 'November', 'December'
                  ], range(1, 13)))

def login(cookie_jar=None):
    session = Session(jar=cookie_jar)
    mbnahome = MBNAHomePage(session=session)
    security = mbnahome.next(user=mbna_user) # already requested in MBNAHomePage
    password = security.next(answer=mbna_security[security.question])
    overview = password.next(password=mbna_pass)
    return overview

def test(cookie_jar=None):
    session = Session(jar=cookie_jar)

    mbnahome = MBNAHomePage(session=session)
    security = mbnahome.next(user=mbna_user)
    password = security.next(answer=mbna_security[security.question])
    overview = password.next(password=mbna_pass)
    snapshot = overview.next(account=overview.__dict__.keys()[0])

    statement = snapshot.next(link='statements')
    s1 = statement.next(statement_index=3)

    pprint(overview.__dict__)
    pprint(snapshot.__dict__)
    pprint(statement.__dict__)
    pprint(s1.__dict__)

    return (session, overview, snapshot, statement, s1)

def test1(cookie_jar=None):
    session = Session(jar=cookie_jar)

    mbnahome = MBNAHomePage(session=session)
    security = mbnahome.next(user=mbna_user)
    password = security.next(answer=mbna_security[security.question])
    overview = password.next(password=mbna_pass)
    snapshot = overview.next(account=overview.__dict__.keys()[0])

    return (session, overview, snapshot)


class MBNA(object):
    session = None
    overview = None
    snapshots = {}
    statements = {}

    def __init__(self, login=True, cookie_jar=None):
        self.session = Session(jar=cookie_jar)
        if login:
            self.get_overview()

    def get_overview(self):
        if self.overview is None:
            mbnahome = MBNAHomePage(session=self.session)
            security = mbnahome.next(user=mbna_user)
            password = security.next(answer=mbna_security[security.question])
            overview = password.next(password=mbna_pass)

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
            self.snapshots[account] = self.overview.next(account=account)
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
        if force or not self.statements.get(account, False):
            statement = snapshot.next(link='statements')
            self.statements[account][statement.date] = statement
        else:
            statement = self.statements[account].values()[0]
        return statement

    def load_latest_statements(self, force=True):
        if self.overview is None:
            self.get_overview()
        for account in self.accounts:
            self.get_latest_statement(account, force=force)
        return self.statements

    def get_statement(self, account, index):
        if not self.statements.get(account, False):
            latest = self.get_latest_statement(account, force=True)
        else:
            latest = self.statements[account].values()[0]
        statement = latest.next(statement_index=index)
        self.statements[account][statement.date] = statement
        return statement

    def load_statements(self, index, force=True):
        if self.overview is None:
            self.get_overview()
        for account in self.accounts:
            self.get_statement(account, index)
        return self.statements


    def __ansistr__(self):
        out = []
        for account in self.accounts:
            prefix = ' ' * (len(account) + 2)
            line = "{yellow}{account}{reset}  ".format(account=account, **ansi)
            if account not in self.snapshots:
                # we only have information from the overview
                out += [line + self.overview.__ansistr__()]
            else:
                # display the information from the snapshot
                out += [line + self.snapshots[account].__ansistr__(prefix=prefix)]

                # display the information from the available statements
                statements = sorted(self.statements.get(account, {}).values(), key=lambda s: s.date, reverse=True)
                for statement in statements:
                    out += [prefix + "-" * 87]
                    out += [statement.__ansistr__(prefix=prefix)]
            out += [""]

        return "\n".join(out)


class MBNAHomePage(FormPage):
    def __init__(self, url='http://mbna.ca/index.html', *args, **kwargs):
        return super(MBNAHomePage, self).__init__(url=url, *args, **kwargs)

    @Page.parser
    def parse(self):
        form = self.soup.find('form')
        if not form.select('div.signinform'):
            raise ParseError('div.signinform not found in first form')

        self.form = form
        self.parse_form()
        if 'username' not in self.form_data:
            raise ParseError('input[name="username"] not found')
        return self

    def next(self, user):
        # We must perform the request here to check if it's a challenge redirect page,
        # a maintenance page or a security question page, so you only need to parse() the result
        self.form_data.update({'username': user})
        (resp, body) = self.session.post(self.form_action, self.form_data)
        if 'Maintenance' in resp.url:
            raise MaintenanceError()
        try:
            redirect = ChallengeRedirect(url=resp.url, body=body, session=self.session)
        except ParseError:
            return SecurityQuestion(url=resp.url, body=body, session=self.session)
        else:
            return redirect.next()


class ChallengeRedirect(Page):
    @Page.parser
    def parse(self):
        re_goto = re.compile('goto\(\'(?P<url>.*?)\'\)', re.I | re.M | re.S | re.U)
        m = re_goto.search(self.body)
        if m is None:
            raise ParseError('goto(\'...\') not found')

        self.goto = m.group('url')
        return self

    def next(self):
        url = urlparse.urljoin(self.url, self.goto)
        return SecurityQuestion(url=url, session=self.session)


class SecurityQuestion(FormPage):
    @Page.parser
    def parse(self):
        try:
            q = self.soup.select('label#question_id')[0]
        except Exception:
            raise ParseError('label#question_id not found')

        self.question = q.text
        self.form = q.find_parent('form')
        self.parse_form()
        if 'answer' not in self.form_data:
            raise ParseError('input[name="answer"] not found')
        return self

    def next(self, answer):
        self.form_data.update({'answer': answer})
        return PasswordPage(url=self.form_action, data=self.form_data, session=self.session)


class PasswordPage(FormPage):
    @Page.parser
    def parse(self):
        form = self.soup.find('form', id='pwd_form.id')
        if form is None:
            raise ParseError('form[id="pwd_form.id"] not found')

        self.form = form
        self.parse_form()
        if 'password' not in self.form_data:
            raise ParseError('input[name="password"] not found')
        return self

    def next(self, password):
        self.form_data.update({'password': password})
        return OverviewPage(url=self.form_action, data=self.form_data, session=self.session)


class OverviewPage(Page):
    @Page.parser
    def parse(self):
        accounts = {}
        account_tds = self.soup.select('td.accountName')
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

    def __ansistr__(self, account=None):
        if account is None:
            return "\n\n".join(["{yellow}{account}{reset}  ".format(account=a, **ansi)\
                                + self.__ansistr__(account=a) for a in self.accounts])\

        data = self.accounts[account]
        line = ''
        line += "{green}" if data['available'] > 0 else "{red}"
        line += "{available}{reset}"
        line += "  Due: "
        line += "{red}" if data['pay_amount'] > 0 else "{green}"
        line += "{amount}{reset} on "
        if datetime.date.today() > data['pay_date']:
            line += "{red}" if data['pay_amount'] > 0 else "{white}"
        else:
            line += "{yellow}" if data['pay_amount'] > 0 else "{green}"
        line += "{duedate}{reset}"
        return line.format(available=data['available'],
                           amount=data['pay_amount'],
                           duedate=data['pay_date'].strftime("%a, %b %d, %Y"),
                           **ansi)


class SnapshotPage(Page):
    @Page.parser
    def parse(self):
        # Extract last 4 digits from page header
        header = self.soup.find('form', action='HeaderController')
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
        currencies = {
            'U.S. DOLLARDOLLAR': 'USD',
            'U.S. DOLLAR': 'USD',
            }
        for row in activity_data:
            (trans_date, post_date, desc, offer_id, ref_num, amt) = row
            desc = re.sub('\s+', ' ', desc)
            amt = dollar_to_float(amt)
            trans_date = str_to_date(trans_date)
            if trans_date is None:
                trans_date = activity[-1]['trans_date'] if activity else datetime.date.today()
                if desc.startswith('FOREIGN CURRENCY'):
                    # doesn't look like foreign currency appears in snapshots
                    (amt, currency) = desc[17:].split(' ', 1)
                    activity[-1].update({
                        'foreign_amount': dollar_to_float(amt),
                        'foreign_currency': currencies.get(currency, currency),
                        })
                continue
            if desc == 'PAYMENT - THANK YOU':
                desc = 'Payment, thank you'
            act = {
                'type': 'debit' if amt < 0 else ('credit_temp' if ref_num == 'TEMP' else 'credit'),
                'trans_date': trans_date,
                'post_date': str_to_date(post_date),
                'desc': desc,
                'ref_num': ref_num,
                'amount': amt,
                }
            if amt > 0:
                # parse desc into name and location
                (name, location) = desc.split(' - ', 1)
                name = ' '.join([s.capitalize() for s in name.split(' ')])
                location = location.split(' ')
                if len(location[-1]) == 2:
                    # last part is the state/province
                    location = ' '.join([s.capitalize() for s in location[:-1]] + location[-1:])
                else:
                    location = ' '.join([s.capitalize() for s in location])
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

        # Extract various links
        self.links = {}
        statements_a = self.soup.find('a', text=re.compile('Statements'))
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

    def __ansistr__(self, prefix=''):
        entries = list(self.activity)
        # system line: today with limit, balance, temp, avail
        entries.append({
            'type': 'system',
            'trans_date': datetime.date.today(),
            'amount': self.limit,
            'desc': "= {red}{balance}{reset} + {yellow}{temp}{reset} + {green}{avail}"\
                    .format(balance=self.balance, temp=self.temp, avail=self.available, **ansi),
            })
        # system line: today with balance+temp and gauge
        percent = round(100*100*(self.balance+self.temp)/self.limit)/100
        perfifty = int(round(50*(self.balance+self.temp)/self.limit))
        gauge = "{reset}["
        if perfifty > 0:
            gauge += "{red}" + "*" * perfifty
        if perfifty < 50:
            gauge += "{green}" + "=" * (50 - perfifty)
        gauge += "{reset}]"
        entries.append({
            'type': 'system',
            'trans_date': datetime.date.today(),
            'amount': self.balance + self.temp,
            'desc': (gauge + " {percent}%").format(percent=percent, **ansi),
            '_amtcolot': '{red}',
            })
        # system line: payment due
        days = (self.pay_date - datetime.date.today()).days
        if self.pay_amount > 0:
            if days <= 5: days_color = '{red}'
            elif days <= 10: days_color = '{yellow}'
            else: days_color = '{green}'
        else:
            days_color = '{linecolor}'
        if days > 0:
            desc = 'in %s%d{linecolor} days' % (days_color, days)
        elif days < 0:
            desc = '%s%d days ago{linecolor}' % (days_color, -1 * days)
        else:
            desc = '%stoday{linecolor}' % days_color
        entries.append({
            'type': 'system',
            'trans_date': self.pay_date,
            'amount': self.pay_amount,
            'desc': 'Payment due ' + desc,
            '_amtcolor': days_color.format(**ansi) if days_color != '{linecolor}' else '{linecolor}',
            })
        # system line: last payment
        if self.last_pay_date < self.last_stmt_date:
            last_pay_color = "{linecolor}"
        elif self.last_pay_date >= self.last_stmt_date and self.last_pay_date <= self.pay_date:
            last_pay_color = "{green}"
        elif self.last_pay_date > self.pay_date and self.last_pay_date < self.next_stmt_date:
            last_pay_color = "{yellow}"
        entries.append({
            'type': 'system',
            'trans_date': self.last_pay_date,
            'amount': self.last_pay_amount,
            'desc': 'Last payment received',
            '_amtcolor': last_pay_color,
            })
        # system line: next invoice
        entries.append({
            'type': 'system',
            'trans_date': self.next_stmt_date,
            'amount': '    ----',
            'desc': 'Next invoice',
            })

        # print the lines
        out = []
        activities = sorted(entries, key=lambda a: (a['trans_date'], a['amount']), reverse=True)
        line_colors = {'system': ansi['magenta'],
                       'debit': ansi['green'],
                       'credit': ansi['blue'],
                       'credit_temp': ansi['yellow']}
        first = True
        for activity in activities:
            if first:
                line = ''
                first = False
            else:
                line = prefix
            line += '{linecolor}'
            params = ansi.copy()
            params['linecolor'] = line_colors[activity.get('type', 'system')]

            # date
            line += '{date} '
            params['date'] = activity['trans_date'].strftime("%a, %b %d, %Y") if activity['trans_date'] else " " * 17

            # amount
            if type(activity['amount']) == float:
                line += '{amtcolor}{amount: >8.2f}{linecolor}  '
            else:
                line += '{amtcolor}{amount}{linecolor}  '
            params['amount'] = activity['amount']
            if activity['type'] == 'credit':
                params['amtcolor'] = ansi['reset']
            elif '_amtcolor' in activity:
                params['amtcolor'] = activity['_amtcolor']
                if params['amtcolor'].startswith('{'):
                    params['amtcolor'] = params['amtcolor'].format(**params)
            else:
                params['amtcolor'] = params['linecolor']

            # foreign amount
            if activity.get('foreign_amount', None):
                line += "{reset}({foreign_amount} {foreign_currency}){linecolor} "
                params['foreign_amount'] = activity['foreign_amount']
                params['foreign_currency'] = activity['foreign_currency']

            # desc
            line += '{desc}{reset}'
            params['desc'] = activity['desc'].format(**params)
            if activity.get('location', None):
                line += ", {location}{reset}"
                params['location'] = activity['location']

            out += [line.format(**params)]

        return "\n".join(out)




class StatementPage(FormPage):
    @Page.parser
    def parse(self):
        # Parse list of available statements
        stmts_select = self.soup.select('select[name="STMT"]')
        if stmts_select:
            stmts_select = stmts_select[0]
        else:
            raise ParseError('select[name="STMT"] not found')
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
        stmt_date = self.soup.find('p', class_='stmtDate').text.strip()
        (m, d, y) = re.match('^(\w*) (\d*), (\d*)$', stmt_date).groups()
        self.date = datetime.date(int(y), MONTHS[m], int(d))

        # Parse statement header data
        header_t = self.soup.find('table', class_='acctdetailmodule')
        header_ths = [" ".join(map(lambda s: s.strip(), th.strings)) for th in header_t.findAll('th')]
        header_tds = [" ".join(map(lambda s: s.strip(), td.strings)) for td in header_t.findAll('td')]
        header = dict(zip(header_ths, header_tds))
        for k in header.keys():
            if header[k].startswith('$') or header[k].startswith('-'):
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
        activity_t = self.soup.find('table', class_='acctregistermodule')
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
            if desc == 'PAYMENT - THANK YOU':
                desc = 'Payment, thank you'
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

            # date
            if activity['amount'] < 0:
                color = "{green}"
            elif activity['type'] == 'interest':
                color = "{yellow}"
            else:
                color = "{blue}"
            line += color + "{date}{reset} "
            act_date = activity['trans_date'].strftime("%a, %b %d, %Y") if activity['trans_date']\
                            else " " * 17

            # amount
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

            # foreign amount
            if activity.get('foreign_amount', None):
                line += "({foreign_amount} {foreign_currency}) "

            # desc
            line += color + "{desc}{reset}"
            if activity.get('location', None):
                line += ", {location}{reset}"

            out += [line.format(date=act_date,
                                amount=activity['amount'],
                                desc=activity['desc'],
                                ref=activity['ref_num'],
                                location=activity.get('location', ''),
                                foreign_amount=activity.get('foreign_amount', ''),
                                foreign_currency=activity.get('foreign_currency', ''),
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

