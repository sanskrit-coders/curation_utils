import codecs
import logging
import time
from functools import lru_cache

import httpx
import backoff
from selenium.webdriver.support.wait import WebDriverWait
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import regex

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, \
  ElementNotInteractableException, ElementClickInterceptedException, JavascriptException, TimeoutException
from selenium.webdriver import Keys, DesiredCapabilities
from httpx import ConnectError, RequestError
from selenium.webdriver.common.by import By
from tqdm import tqdm

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


# Set the logging level for your specific loggers
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)


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
  options = options.Options()
  options.add_argument('--ignore-ssl-errors=yes')
  options.add_argument('--ignore-certificate-errors')
  options.add_argument("--allow-running-insecure-content");
  options.set_capability('acceptInsecureCerts', True)
  options.add_argument('--disable-web-security') # Can be useful in some cases
  
  options.headless = headless
  if headless:
    options.add_argument("--headless")    
    options.add_argument("--disable-gpu")  # Applicable for Windows OS
    options.add_argument("--no-sandbox")
  # options.add_argument('--remote-debugging-port=9222')
  browser = webdriver.Chrome(options=options)
  browser.set_page_load_timeout(1000)
  return browser



def get_selenium_firefox(headless=True):
  from selenium import webdriver
  from selenium.webdriver.firefox import options
  opts = options.Options()
  return webdriver.Firefox(options=opts)


def get_selenium_url(url, browser):
  from selenium.webdriver.support import expected_conditions as EC

  # --- Step 3: Navigate and Handle the Privacy Screen ---
  print(f"Navigating to {url}...")
  browser.get(url)
  try:
    proceed_btn = WebDriverWait(browser, 5).until(
      EC.element_to_be_clickable((By.ID, "proceed-button"))
    )
    print("Found and clicking 'Advanced' button.")
    proceed_btn.click()


  except TimeoutException:
    # If the "Advanced" button is not found after 5 seconds,
    # we assume the page loaded correctly without the privacy error.
    # print("Privacy error screen not detected. Page should be loaded.")
    pass

  # --- Step 5: Confirm successful navigation ---
  # Wait for the title of the actual page to be something other than the error page title
  WebDriverWait(browser, 10).until(
    lambda d: d.title and "privacy" not in d.title.lower()
  )
  print(f"Successfully navigated. Page title is: '{browser.title}'")


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


@retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5), retry=retry_if_exception_type(httpx.ConnectError))
@backoff.on_exception(wait_gen=backoff.expo,
                      exception=(ConnectError, RequestError),
                      max_time=6000,
                      factor=2, max_value=300)
@backoff.on_predicate(wait_gen=backoff.expo,
                      predicate=lambda result: 400 <= result. status_code < 500 and result.status_code not in [404, 403, 503],
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


def scroll_with_selenium(url, browser, scroll_pause=2, element_css="body", scroll_btn_css=None):
  if browser is None:
    browser = get_selenium_chrome()
  if url is not None:
    browser.get(url)

  if element_css != "body":
    element_js = f"document.querySelector('{element_css}')";
  else:
    element_js = "document.body"
  # Get scroll height
  try:
    last_height = browser.execute_script(f"return {element_js}.scrollHeight")
  except JavascriptException:
    last_height = None
  page_id = 0
  with tqdm(desc="Scrolling", unit=" scrolls") as pbar:
    while True:
      # Scroll down to bottom
  
      if scroll_btn_css is not None:
        try:
          scroll_btn = browser.find_element(By.CSS_SELECTOR, scroll_btn_css)
          browser.execute_script("arguments[0].click();", scroll_btn)
          # The below may fail in case of a disabled button
          try:
            scroll_btn.click()
          except ElementNotInteractableException:
            break
        except NoSuchElementException:
          logging.info(f"No such element found {scroll_btn_css}")
        except ElementClickInterceptedException:
          logging.info(f"Can't click {scroll_btn_css}. Breaking.")
          break
  
      # logging.info(f"Moving to page {page_id}.")
      try:
        element = browser.find_element(By.CSS_SELECTOR, element_css)
        browser.execute_script("arguments[0].click();", element)
        # element.click()
        # element.send_keys(Keys.END)
        browser.execute_script(f"{element_js}.scrollTo(0, {element_js}.scrollHeight);")
        # Wait to load page
        time.sleep(scroll_pause)
    
        # Calculate new scroll height and compare with last scroll height
        new_height = browser.execute_script(f"return {element_js}.scrollHeight")
        # logging.debug(f"{last_height} to {new_height}")
        page_id += 1
        pbar.set_postfix_str(f"Height: {new_height}")
        pbar.update(1)
        if new_height == last_height:
          break
        last_height = new_height
      except NoSuchElementException:
        logging.warning(f"No such element found {element_css}")
        break
        # browser.execute_script(f"{element_js}.scrollDown += 100;")

  logging.info(f"Scrolled to the bottom of {element_css} in {url}")
  return browser.page_source


def scroll_and_get_soup(url, browser, scroll_pause=2, element_css="body", scroll_btn_css=None):
  content = scroll_with_selenium(url=url, browser=browser, scroll_pause=scroll_pause, element_css=element_css, scroll_btn_css=scroll_btn_css)
  soup = BeautifulSoup(content, features="lxml")
  return soup
