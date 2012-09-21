"""
This file is run by the admin command before starting a shell.
"""

from exosapient.util import ansi
_ansi = {
    'mdl': ansi.green,
    'cls': ansi.blue,
    'obj': ansi.yellow,
    'r': ansi.reset
}

print ''
print 'Available {mdl}modules{r}, {cls}classes{r} and {obj}objects{r}'.format(**_ansi)
print '-' * 38
print 'import {mdl}web{r}'.format(**_ansi)
import web
print 'from web.core import {mdl}http{r}, {cls}Controller{r}, {obj}request{r}, {obj}response{r}'.format(**_ansi)
from web.core import http, Controller, request, response
print 'from exosapient.util import {mdl}mbna{r}'.format(**_ansi)
from exosapient.util import mbna

print 'from datetime import {cls}date{r}, {cls}time{r}, {cls}datetime{r}'.format(**_ansi)
from datetime import date, time, datetime
#print 'from dateutil.relativedelta import {cls}relativedelta{r}'.format(**_ansi)
#from dateutil.relativedelta import relativedelta
#print 'from pytz import {cls}timezone{r}, {obj}utc{r}'.format(**_ansi)
#from pytz import timezone, utc
#print 'from exosapient import {obj}settings{r}'.format(**_ansi)
#from exosapient import settings
#print 'from exosapient.model import session as {obj}db{r}'.format(**_ansi)
#from exosapient.model import session as db
print '{obj}app{r} = paste.fixture.TestApp'.format(**_ansi)
print "          Make requests with app.get('<path>'), app.post('<path>', params='<params>'), etc."

print ''
print 'Admin shell'
print '-' * 11,
