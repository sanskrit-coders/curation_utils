from urllib.parse import urlparse, urljoin

import codecs
import logging
import random
import time
from functools import lru_cache

import httpx
import backoff
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import regex

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, \
  ElementNotInteractableException, ElementClickInterceptedException, JavascriptException, TimeoutException, \
  UnexpectedAlertPresentException, NoAlertPresentException
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
safari_headers = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15'
}
opera_headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 OPR/80.0.4170.63'
}
edge_headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 Edg/94.0.992.47'
}
ie_headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko'
}
common_headers = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
  "Cache-Control": "no-cache",
  "Pragma": "no-cache"
}

common_headers.update(requests.utils.default_headers())
chrome_headers.update(common_headers)
firefox_headers.update(common_headers)
safari_headers.update(common_headers)
edge_headers.update(common_headers)
ie_headers.update(common_headers)
opera_headers.update(common_headers)

chrome_headers_android.update(common_headers)
headers = chrome_headers
header_choices = [chrome_headers_android, chrome_headers, firefox_headers, safari_headers, opera_headers, edge_headers, ie_headers]


def sleep_approx(duration, jitter=0):
  import time
  logging.info(f"Sleeping for {duration} + approx {jitter/2}")
  start = time.time()
  while time.time() - start < duration:
      time.sleep(1)
  time.sleep(random.uniform(0, jitter))


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


def get_base_url(url: str, with_trailing_slash: bool = False) -> str:
  """Returns scheme://netloc (the origin/base)"""
  parsed = urlparse(url)
  if not parsed.scheme or not parsed.netloc:
    return ""
  base = f"{parsed.scheme}://{parsed.netloc}"
  return base + "/" if with_trailing_slash else base


def clean_url(url):
  if "#" in url:
    url = "#".join(url.split("#")[:-1])
  return url


def build_get_url_backoffed(retry_on_404=False):
  def base_get_url(url, method=httpx.get, timeout=30.0):
    return method(url=url,
                  headers=random.choice(header_choices),
                  follow_redirects=True,
                  timeout=timeout)
  # Apply tenacity retry for connection errors
  fn = retry(wait=wait_exponential(multiplier=1, min=4, max=60),
             stop=stop_after_attempt(5),
             retry=retry_if_exception_type(httpx.ConnectError))(base_get_url)

  # Apply backoff on exceptions
  fn = backoff.on_exception(wait_gen=backoff.expo,
                            exception=(ConnectError, RequestError),
                            max_time=6000,
                            factor=2, max_value=300, max_tries=5)(fn)

  # Predicate-based backoff
  base_predicate = lambda result: 400 <= result.status_code < 523 and result.status_code not in [403, 503]
  if retry_on_404:
    predicate = base_predicate
  else:
    predicate = lambda result: base_predicate(result) and result.status_code not in [404]

  fn = backoff.on_predicate(wait_gen=backoff.expo,
                            predicate=predicate,
                            max_time=6000,
                            factor=2, max_value=300, max_tries=5)(fn)

  return fn



def get_url_backoffed(url, method=httpx.get, timeout=30.0, retry_on_404=False):
  get_url = build_get_url_backoffed(retry_on_404=retry_on_404) 
  return get_url(url=url, method=method, timeout=timeout)


def get_url_aws(url, config_aws=None):
  # Source - https://stackoverflow.com/a/68451842
  
  import requests
  from requests_ip_rotator import ApiGateway, EXTRA_REGIONS
  
  gateway = ApiGateway(url, access_key_id = config_aws[0], access_key_secret = config_aws[1])
  gateway.start()
  
  session = requests.Session()
  session.mount(url, gateway)
  
  response = session.get(url)
  # print(response.status_code)
  return response
  # Only run this line if you are no longer going to run the script, as it takes longer to boot up again next time.
  gateway.shutdown()


@lru_cache(maxsize=2)
def get_soup(url, config_aws=None, features="html.parser", retry_on_404=False):
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
    result = None
  else:
    if config_aws is not None:
      result = get_url_aws(url=url, config_aws=config_aws)
    else:
      result = get_url_backoffed(url=url, retry_on_404=retry_on_404)

    if 400 <= result.status_code < 600:
      return (None, result)

    content = result.text

  soup = BeautifulSoup(content, features=features)
  return (soup, result)


def get_post_soup(url, timeout=30.0, retry_on_404=False):
  result = get_url_backoffed(url=url, method=httpx.post, timeout=timeout, retry_on_404=retry_on_404)
  content = result.text
  soup = BeautifulSoup(content, features="html.parser")
  return soup


def accept_alert(browser):
  from selenium.common.exceptions import NoAlertPresentException
  
  try:
      alert = browser.switch_to.alert
      print("Alert text:", alert.text)
      alert.accept()  # or alert.dismiss()
  except NoAlertPresentException:
      pass


def run_js_safely(script, browser, *args, **kwargs):
  try:
    return browser.execute_script(script, *args, **kwargs)
  except UnexpectedAlertPresentException:
    try:
      alert = browser.switch_to.alert
      print("Alert text:", alert.text)
      alert.accept()
    except NoAlertPresentException:
      pass
    return browser.execute_script(script, *args, **kwargs)



def scroll_with_selenium(
    url,
    browser,
    scroll_pause=2,
    element_css="body",
    scroll_btn_css=None,
    stable_checks=3,
    timeout=600
):
  if browser is None:
    browser = get_selenium_chrome()
  if url is not None:
    browser.get(url)

  wait = WebDriverWait(browser, 20)
  try:
    wait.until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, element_css)))
  except Exception:
    logging.debug(f"Element {element_css} not present after initial wait")

  # Use document.documentElement for standard HTML5 viewport height measurements
  if element_css != "body":
    element_js = f"document.querySelector('{element_css}')"
  else:
    element_js = "document.documentElement"

  # initial measurements
  try:
    last_height = run_js_safely(f"return {element_js}.scrollHeight", browser)
  except JavascriptException:
    last_height = None

  try:
    last_text_len = run_js_safely(f"return (document.querySelector('{element_css}') || document.documentElement).innerText.length", browser)
  except JavascriptException:
    last_text_len = None

  stable_count_height = 0
  stable_count_text = 0
  start_time = time.time()

  page_id = 0
  with tqdm(desc="Scrolling", unit=" scrolls") as pbar:
    while True:
      # global timeout guard
      if time.time() - start_time > timeout:
        logging.warning("Timeout reached while waiting for stability")
        break

      # Scroll down to bottom or click load-more button if provided
      if scroll_btn_css is not None:
        try:
          scroll_btn = browser.find_element(By.CSS_SELECTOR, scroll_btn_css)
          try:
            scroll_btn.click()
          except ElementNotInteractableException:
            try:
              run_js_safely("arguments[0].click();", browser, scroll_btn)
            except Exception:
              logging.info(f"Non clickable element found {scroll_btn_css}")
              break
        except NoSuchElementException:
          logging.debug(f"No such element found {scroll_btn_css}")
        except ElementClickInterceptedException:
          logging.info(f"Can't click {scroll_btn_css}. Breaking.")
          break

      try:
        element = browser.find_element(By.CSS_SELECTOR, element_css)

        # Scroll using appropriate target
        if element_css == "body":
          run_js_safely("window.scrollTo(0, document.documentElement.scrollHeight);", browser)
        else:
          run_js_safely("arguments[0].scrollTop = arguments[0].scrollHeight;", browser, element)

        # Wait to load page
        time.sleep(scroll_pause)

        # Measure new scroll height
        try:
          new_height = run_js_safely(script=f"return {element_js}.scrollHeight", browser=browser)
        except JavascriptException:
          new_height = None

        # Measure new text length (visible text)
        try:
          new_text_len = run_js_safely(
            script=f"return (document.querySelector('{element_css}') || document.documentElement).innerText.length",
            browser=browser
          )
        except JavascriptException:
          new_text_len = None

        logging.debug(f"Height: {last_height} -> {new_height}; TextLen: {last_text_len} -> {new_text_len}")
        page_id += 1
        pbar.set_postfix_str(f"Height: {new_height} TextLen: {new_text_len}")
        pbar.update(1)

        # Update stability counters for height
        if last_height is None or new_height is None:
          stable_count_height = 0
        else:
          if new_height > last_height:
            stable_count_height = 0
          else:
            stable_count_height += 1
        last_height = new_height

        # Update stability counters for text length
        if last_text_len is None or new_text_len is None:
          stable_count_text = 0
        else:
          if new_text_len > last_text_len:
            stable_count_text = 0
          else:
            stable_count_text += 1
        last_text_len = new_text_len

        # If both metrics have been stable for required consecutive checks, stop
        if stable_count_height >= stable_checks and stable_count_text >= stable_checks:
          logging.info(f"Both height and text length stabilized (height stable {stable_count_height}, text stable {stable_count_text})")
          break

        # Fallback: if neither metric changed at all this iteration, break to avoid infinite loop
        if new_height == last_height and new_text_len == last_text_len:
          logging.debug("No change detected in both metrics this iteration")
          # allow loop to continue to accumulate stable counts; do not break immediately

      except NoSuchElementException:
        logging.warning(f"No such element found {element_css}")
        break


  logging.info(f"Scrolled and stabilized {element_css} in {url}")
  return browser.page_source

def scroll_and_get_soup(*args, **kwargs):
  content = scroll_with_selenium(*args, **kwargs)
  soup = BeautifulSoup(content, features="html.parser")
  return soup
