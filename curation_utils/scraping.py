import logging

import requests
from bs4 import BeautifulSoup

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

logger = logging.getLogger('chardet')
logger.setLevel(logging.CRITICAL)


from selenium.webdriver.remote.remote_connection import LOGGER
LOGGER.setLevel(logging.WARNING)

from urllib3.connectionpool import log as urllibLogger
urllibLogger.setLevel(logging.WARNING)
# Set headers
firefox_headers = { 'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}
chrome_headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G928X Build/LMY47X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.83 Mobile Safari/537.36'}
headers = requests.utils.default_headers()
headers.update(chrome_headers)



def get_selenium_browser(headless=True):
    from selenium import webdriver
    from selenium.webdriver.chrome import options
    opts = options.Options()
    opts.headless = headless
    return webdriver.Chrome(options=opts)

def get_soup(url):
    result = requests.get(url, headers)
    soup = BeautifulSoup(result.content, features="lxml")
    return soup
