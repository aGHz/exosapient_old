from bs4 import BeautifulSoup
import cookielib
import re
import urllib
import urllib2
import urlparse

from exosapient.model.local import mbna_user, mbna_security, mbna_pass
from exosapient.util import scraping

re_goto = re.compile('goto\(\'(?P<url>.*?)\'\)', re.I | re.M | re.S | re.U)
re_question = re.compile('label [^>]*?question_id', re.I | re.M | re.S | re.U)

def run(load=None):
    scraper = scraping.Session(load_jar=load)

    # get and parse the username form
    print 'get and parse the username form'
    url_index = 'http://mbna.ca/index.html'
    print 'url: ', url_index
    (resp, body) = scraper.get_page(url_index)
    user_form = extract_user_form(body)
    (action, method, inputs, data) = scraper.parse_form(user_form)
    scraper.print_jar()
    print

    # submit the username form
    print 'submit the username form'
    print 'action: ', scraper.next_url
    (resp, body) = scraper.submit_next({'username': mbna_user})
    scraper.print_jar()
    print

    # at this point we can get served either the challenge redirect page,
    # or sometimes the security question page if there was something wrong with the cookies
    goto_url = extract_goto_url(body, scraper.prev_url)
    if goto_url is not None:
        # perform the redirect
        print 'username submit returned challenge redirection page'
        print 'url: ', goto_url
        (resp, body) = scraper.get_page(goto_url)
        scraper.print_jar()
        print

    # parse security question form
    (sec_form, sec_q) = extract_security_form(body)
    if sec_q not in mbna_security:
        raise Exception('Security answer not found: "%s"' % sec_q)
    (action, method, inputs, data) = scraper.parse_form(sec_form)

    # submit the security question form
    print 'submit the security question form'
    print 'action: ', scraper.next_url
    (resp, body) = scraper.submit_next({'answer': mbna_security[sec_q]})
    scraper.print_jar()
    print

    # parse the password form
    pass_form = extract_pass_form(body)
    (action, method, inputs, data) = scraper.parse_form(pass_form)

    # submit the password form
    print 'submit the security question form'
    print 'action: ', scraper.next_url
    (resp, body) = scraper.submit_next({'password': mbna_pass})
    scraper.print_jar()
    print


    return (resp, body, scraper)

def extract_user_form(body):
    soup = BeautifulSoup(body)

    form = soup.find('form')
    if not form.select('div.signinform'):
        raise Exception('extract_user_form failed, div.signinform not found in first form')

    return form

def extract_goto_url(body, prev_url):
    m = re_goto.search(body)
    if m is None:
        return None
    next_path = m.group('url')

    prev_parse = urlparse.urlparse(prev_url)
    next_parse = urlparse.urlparse(next_path)
    next_url = urlparse.urlunparse((prev_parse.scheme,
                                    prev_parse.netloc,
                                    next_parse.path,
                                    next_parse.params,
                                    next_parse.query,
                                    next_parse.fragment))
    return next_url

def extract_security_form(body):
    soup = BeautifulSoup(body)

    try:
        q = soup.select('label#question_id')[0]
    except Exception:
        raise Exception('extract_security_form failed, label#question_id not found in body')
    form = q.find_parent('form')
    return (form, q.text)

def extract_pass_form(body):
    soup = BeautifulSoup(body)

    form = soup.find('form', id='pwd_form.id')
    if form is None:
        raise Exception('extract_pass_form failed, form[id="pwd_form.id"] not found in body')
    return form

