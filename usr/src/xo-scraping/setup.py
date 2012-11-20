#!/usr/bin/env python
# encoding: utf-8

from setuptools import setup, find_packages


setup(
        name = "xo.scraping",
        version = "0.0.1",
        description = "XO scraping library",
        author = "Adrian Ghizaru",
        author_email = "adrian.ghizaru@gmail.com",
        url = "http://aghz.ca/",

        install_requires = [
            'lxml',
            'BeautifulSoup4',
            ],
        packages = find_packages(),

        zip_safe = True,
        include_package_data = True,
        package_data = {
                '': ['README.md', 'LICENSE'],
            },

        entry_points = {}
    )
