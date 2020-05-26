import logging

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
