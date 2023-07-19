import codecs
import logging
import time
from functools import lru_cache

import httpx
import backoff

import requests
from bs4 import BeautifulSoup
from curation_utils import file_helper

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
firefox_headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}
chrome_headers_android = {
  'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G928X Build/LMY47X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.83 Mobile Safari/537.36'}
chrome_headers = {
  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36',
  'sec-ch-ua': '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"'
}
common_headers = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
}
headers = requests.utils.default_headers()
headers.update(common_headers)
headers.update(chrome_headers)


def get_selenium_chrome(headless=True):
  from selenium import webdriver
  from selenium.webdriver.chrome import options
  opts = options.Options()
  opts.headless = headless
  opts.add_argument('--remote-debugging-port=9222')
  return webdriver.Chrome(options=opts)



def get_selenium_firefox(headless=True):
  from selenium import webdriver
  from selenium.webdriver.firefox import options
  opts = options.Options()
  opts.headless = headless
  return webdriver.Firefox(options=opts)


def get_url_with_requests_lib(url):
  import urllib3
  urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
  result = requests.get(url, headers, verify=False)
  # result.content has the content.
  return result


def clean_url(url):
  if "#" in url:
    url = "#".join(url.split("#")[:-1])
  return url


@backoff.on_predicate(wait_gen=backoff.expo,
                      predicate=lambda result: 400 <= result.status_code < 500 and result.status_code not in [404],
                      max_time=6000,
                      factor=2, max_value=300)
def get_url_backoffed(url, method=httpx.get, timeout=30.0):
  result = method(url=url, follow_redirects=True, timeout=timeout)
  return result



@lru_cache(maxsize=2)
def get_soup(url, features="lxml"):
  """
  
  :param url: Examples: https://a:b@c.com/ https://xyz.com 
  :return: 
  """
  url = url.replace("file://", "")
  url = clean_url(url)
  if url.startswith("/"):
    file_helper.unicodify(url)
    with codecs.open(url, 'r') as f:
      content = f.read()
  else:
    result = get_url_backoffed(url=url)
    content = result.text
  soup = BeautifulSoup(content, features=features)
  return soup


def get_post_soup(url, timeout=30.0):
  result = get_url_backoffed(url=url, method=httpx.post, timeout=timeout)
  content = result.text
  soup = BeautifulSoup(content, features="lxml")
  return soup


def scroll_with_selenium(url, browser, scroll_pause=2):
  browser.get(url)

  # Get scroll height
  last_height = browser.execute_script("return document.body.scrollHeight")

  while True:
    # Scroll down to bottom
    browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    # Wait to load page
    time.sleep(scroll_pause)

    # Calculate new scroll height and compare with last scroll height
    new_height = browser.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
      break
    last_height = new_height
  logging.info("Scrolled to the bottom of %s", url)
  return browser.page_source


def scroll_and_get_soup(url, browser):
  content = scroll_with_selenium(url=url, browser=browser)
  soup = BeautifulSoup(content, features="lxml")
  return soup
