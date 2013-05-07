from bs4 import BeautifulSoup
import datetime
import re

from xo.scraping import Page


class ApaPage(Page):
    def __init__(self, min_rent=None, max_rent=None, city='montreal', language='en', tld='ca', *args, **kwargs):
        for v in ['city', 'language', 'tld', 'min_rent', 'max_rent']:
            setattr(self, v, locals()[v])
        # construct the search page URL
        url = craigslist_domain(city=city, language=language, tld=tld)
        url += 'search/apa'
        params = {} # bedrooms, hasPic=1, zoomToPosting, query, srchType=A
        if min_rent is not None:
            params['minAsk'] = min_rent
        if max_rent is not None:
            params['maxAsk'] = max_rent
        if params:
            url += '?' + '&'.join('{k}={v}'.format(k=k, v=v) for k, v in params.iteritems())
        super(ApaPage, self).__init__(url=url, *args, **kwargs)

    @Page.parser
    def parse(self):
        rows = self.soup.select('p.srch.row')
        results = {}
        for row in rows:
            # Main data
            link = row.find('span', class_='title1').find('a')
            result = {
                'pid': row.attrs['data-pid'],
                'date': row.find('span', class_='itemdate').text.strip(),
                'url': link.attrs['href'],
                'title': link.text.strip(),
                }
            price_span = row.find('span', class_='itemprice')
            if price_span:
                result['rent'] = int(price_span.text.strip()[1:])

            # Number of bedrooms and sq.ft.
            extra = row.find('span', class_='itempnr')
            m = re.search(r"(\d+)br", extra.text)
            if m:
                result['br'] = int(m.groups()[0])
            m = re.search(r"(\d+)ft", extra.text)
            if m:
                result['ft'] = int(m.groups()[0])
                
            # Geographical area
            area = extra.find('small')
            if area:
                result['area'] = area.text.strip()[1:-1].strip()
                if result['area'][0] == '(' and result['area'][-1] == ')':
                    result['area'] = result['area'][1:-1].strip()

            # Has pics or map
            tags = row.find('span', class_='itempx')
            result['pic'] = 'pic' in tags.text
            result['map'] = 'map' in tags.text

            results[result['pid']] = result

        self.results = results
        return self

    @Page.self_referrer
    def next(self, pid):
        #return ApaDetailPage(pid, city=self.city, language=self.language, tld=self.tld)
        return ApaDetailPage(pid, url=self[pid]['url'])

    def fetch_details(self, start, count):
        ids = self.results.keys()[start:count]
        return [self.next(pid) for pid in ids]

    # List interface
    def __getitem__(self, pid):
        for result in self.results.values():
            if result['pid'] == pid:
                return result
        raise KeyError('No post with id %s on this page' % pid)
    def __contains__(self, pid):
        for result in self.results.values():
            if result['pid'] == pid:
                return True
        return False
    def __len__(self):
        return len(self.results)
    def __iter__(self):
        for result in self.results.values():
            yield result


class ApaDetailPage(Page):
    def __init__(self, pid, city='montreal', language='en', tld='ca', *args, **kwargs):
        self.pid = pid

        if 'url' not in kwargs:
            # construct the details page URL
            url = craigslist_domain(city=city, language=language, tld=tld)
            url += 'apa/' + pid + '.html'
            super(ApaDetailPage, self).__init__(url=url, *args, **kwargs)
        else:
            super(ApaDetailPage, self).__init__(*args, **kwargs)

    @Page.parser
    def parse(self):
        # Details
        body = self.soup.find('section', id='postingbody')
        self.details = "\n".join([re.sub(r"\s+", ' ', s.strip()) for s in body.strings])

        # Date
        info = self.soup.find('p', class_='postinginfo')
        timestamp = int(info.find('date').attrs['title'][:-3])
        self.date = datetime.datetime.fromtimestamp(timestamp)

        # Images
        img_div = self.soup.find('div', id='thumbs')
        if img_div:
            links = img_div.find_all('a')
            self.images = dict((l.attrs['title'], l.attrs['href']) for l in links)
        else:
            self.images = {}

        # Special Craigslist tags such as geo area, dogs/cats, etc
        # We want the CLTAGS comments but they're removed from self.soup, so make another soup
        soup = BeautifulSoup(self.body)
        tags = soup.find('section', class_='cltags')
        if tags:
            tags = [s.strip() for s in tags.strings]
            tags = [line[6:] for line in tags if line.startswith('CLTAG')]
            tags = dict(tag.split('=') for tag in tags)
        else:
            tags = {}
        self.tags = tags

        return self

    @Page.self_referrer
    @Page.file_downloader
    def get_image(self, i):
        if i not in self.images:
            return None
        return self.images[i]

    def __dict__(self):
        return {
            'details': self.details,
            'date': self.date,
            'images': self.images,
            'tags': self.tags
            }


def craigslist_domain(city='montreal', language='en', tld='ca'):
    domain_parts = [city]
    if language is not None:
        domain_parts.append(language)
    domain_parts.extend(['craigslist', tld])
    url = 'http://' + '.'.join(domain_parts) + '/'
    return url

