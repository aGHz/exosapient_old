from web.core import Controller

from exosapient.apt.nodes import RootController as apt_root
from exosapient.util.response import *

log = __import__('logging').getLogger(__name__)

FOOBAR = 0

class RootController(Controller):
    apt = apt_root()

    def test(self, *args, **kwargs):
        global FOOBAR
        FOOBAR = 108
        return TEMPLATE('index', {'project_name': FOOBAR})

    def __default__(self, *args, **kwargs):
        global FOOBAR
        #log.info('-- Request --')
        return TEMPLATE('index', {'project_name': FOOBAR})

