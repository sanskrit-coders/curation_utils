import threading
import time
from unittest import mock


def test_plain_chrome_pins_chromium_binary():
  from curation_utils import scraping
  with mock.patch("selenium.webdriver.Chrome") as chrome_cls:
    scraping.get_selenium_chrome(headless=True, undetected=False)
  (args, kwargs) = chrome_cls.call_args
  options = kwargs.get("options", args[0] if args else None)
  assert options.binary_location == "/usr/bin/chromium"
  assert "--headless=new" in options.arguments


def test_plain_chrome_headed_has_no_headless_flag():
  from curation_utils import scraping
  with mock.patch("selenium.webdriver.Chrome") as chrome_cls:
    scraping.get_selenium_chrome(headless=False, undetected=False)
  (args, kwargs) = chrome_cls.call_args
  options = kwargs.get("options", args[0] if args else None)
  assert options.binary_location == "/usr/bin/chromium"
  assert "--headless=new" not in options.arguments


def test_chrome_launch_is_serialized_across_threads():
  from curation_utils import scraping

  def slow_chrome(*args, **kwargs):
    time.sleep(0.6)
    return mock.Mock()

  with mock.patch("selenium.webdriver.Chrome", side_effect=slow_chrome):
    start = time.monotonic()
    threads = [threading.Thread(target=lambda: scraping.get_selenium_chrome(headless=True, undetected=False))
               for _ in range(2)]
    for thread in threads:
      thread.start()
    for thread in threads:
      thread.join()
    elapsed = time.monotonic() - start
  # Serialized: 0.6 + 0.6. Parallel (broken lock) would finish in ~0.6.
  assert elapsed >= 1.1
