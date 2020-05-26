import logging

import requests

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

# Set headers
headers = requests.utils.default_headers()
headers.update({ 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'})

from selenium.webdriver.remote.remote_connection import LOGGER
LOGGER.setLevel(logging.WARNING)

from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)


def get_selenium_browser(headless=True):
    from selenium import webdriver
    from selenium.webdriver.chrome import options
    opts = options.Options()
    opts.headless = headless
    return webdriver.Chrome(options=opts)

def request_url(url):
    return requests.get(url, headers)