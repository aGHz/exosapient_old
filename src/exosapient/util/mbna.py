from BeautifulSoup import BeautifulSoup
import urllib
import urllib2

def load_index(url='http://mbna.ca/index.html'):
    body = urllib2.urlopen(url).read()
    soup = BeautifulSoup(body)

    for form in soup.findAll('form'):
        inputs = {}
        for inp in form.findAll('input'):
            inputs[inp['name']] = dict(inp.attrs)

        if 'username' not in inputs:
            # this is not the login form
            continue

        return (form['action'], form['method'], inputs.keys())

    # couldn't find the login form
    return None

def login_username(url='https://www.onlineaccess.ca/NASApp/NetAccess/LoginValidation', method='post', data=''):
    body = urllib2.urlopen(url, urllib.urlencode(data)).read()
    soup = BeautifulSoup(body)
