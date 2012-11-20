from xo.scraping.exc import UAIdentifierError


UA_STRINGS = {
    'chrome21': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/537.1',
    }

def user_agent(ua_id, strict=False):
    ua_string = UA_STRINGS.get(ua_id, None)
    if ua_string is None:
        if strict:
            raise UAIdentifierError(ua_id)
        else:
            return ua_id
    else:
        return ua_string

