import os.path
from web.core import request, response, Controller

from exosapient.util.response import STATIC_SERVER
from .util import TEMPLATE


STATIC_PATH = os.path.join(os.path.dirname(__file__), 'static')

class RootController(Controller):
    static = STATIC_SERVER(STATIC_PATH)

    def index(self, *args, **kwargs):
        return TEMPLATE('index', {'foo': 'bar'})
