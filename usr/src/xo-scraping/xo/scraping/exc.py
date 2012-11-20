class ParseError(Exception):
    pass

class RequestError(Exception):
    pass

class UAIdentifierError(Exception):
    def __init__(self, ua_id):
        return super(UAIdentifierError, self).__init__(self,
            'User Agent identifier not configured: "{0}"'.format(ua_id))

