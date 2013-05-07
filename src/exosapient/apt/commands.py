import datetime
import os.path

from .scraper import ApaPage


DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
IMAGES_PATH = os.path.join(DATA_PATH, 'images')

def craigslist(min_rent=None, max_rent=875):
    """Fetch latest Craigslist posts"""
    apa = ApaPage(min_rent=min_rent, max_rent=max_rent)
    return apa

def kijiji():
    """Fetch latest Kijiji posts"""
    pass

