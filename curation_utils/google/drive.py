import io
import logging
import os
import socket

import socket

# Force Python to use IPv4 socket connections only
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
  responses = old_getaddrinfo(*args, **kwargs)
  return [response for response in responses if response[0] == socket.AF_INET]

socket.getaddrinfo = new_getaddrinfo

import time
from functools import lru_cache

# Catch both socket/OS timeout errors and HTTP error responses
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from oauth2client.service_account import ServiceAccountCredentials

# Set the default socket timeout to 10 minutes
socket.setdefaulttimeout(600)

# Remove existing handlers and set up logging
for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)
logging.getLogger('oauth2client').setLevel(logging.INFO)


@lru_cache(2)
def get_cached_client(google_key):
  return DriveClient(google_key=google_key)


class DriveClient(object):
  def __init__(self,
               google_key='/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/google/proofing/service_account_key.json', folder_key='0B1_QBT-hoqqVa0xDRHFmM2EzWUk'):
    """Interact with Google Drive via this client."""
    scopes = ['https://www.googleapis.com/auth/drive']
    if "service_account" in google_key:
      creds = ServiceAccountCredentials.from_json_keyfile_name(google_key, scopes)
      logging.info(f"creds.service_account_email {creds.service_account_email}")
    else:
      token_file = os.path.join(os.path.dirname(google_key), "tokens.json")
      creds = None
      if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
      if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
          creds.refresh(Request())
        else:
          flow = InstalledAppFlow.from_client_secrets_file(google_key, scopes)
          creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
          token.write(creds.to_json())

    self.service = build('drive', 'v3', credentials=creds)
    self.folder_key = folder_key

  def upload(self, local_file_path, mime='application/vnd.google-apps.document', max_retries=2):
    """Uploads a file to Google Drive with retries covering network socket timeouts."""
    logging.info(f"Uploading {local_file_path} to folder {self.folder_key}")

    # Define retryable exceptions (Socket/OS level + Google HTTP level)
    RETRYABLE_ERRORS = (HttpError, TimeoutError, OSError, socket.timeout)

    for attempt in range(1, max_retries + 1):
      try:
        logging.info("Attempt %d: Uploading %s", attempt, local_file_path)

        # Explicit 1MB chunk size prevents httplib2 from timing out on large payloads
        media = MediaFileUpload(
          local_file_path,
          mimetype=mime,
          resumable=True,
          chunksize=1024 * 1024
        )

        request = self.service.files().create(
          body={
            'name': os.path.basename(local_file_path),
            'mimeType': mime,
            'parents': [self.folder_key]
          },
          media_body=media,
          supportsAllDrives=True
        )

        # num_retries parameter inside execute() enables internal exponential backoff
        result = request.execute(num_retries=max_retries)
        logging.info("Upload succeeded on attempt %d", attempt)
        return result

      except RETRYABLE_ERRORS as e:
        wait_time = 2 ** attempt
        logging.warning("Error on attempt %d (%s): %s. Retrying in %ds...", attempt, type(e).__name__, e, wait_time)
        if attempt == max_retries:
          raise
        time.sleep(wait_time)

  def download_text(self, local_file_path, file_id, mime_type="text/markdown", max_retries=5):
    """Downloads exported text with chunk retry support."""
    logging.info("Downloading file ID %s to %s", file_id, local_file_path)

    request = self.service.files().export_media(fileId=file_id, mimeType=mime_type)

    with io.FileIO(local_file_path, 'wb') as fh:
      downloader = MediaIoBaseDownload(fh, request)
      done = False
      while not done:
        # Pass num_retries to handle intermittent transport drops during download
        status, done = downloader.next_chunk(num_retries=max_retries)
        if status:
          logging.debug("Download %d%%.", int(status.progress() * 100))

    logging.info("Done downloading %s", local_file_path)

  def delete_file(self, file_id, max_retries=3):
    logging.info("Deleting file ID %s", str(file_id))
    for attempt in range(1, max_retries + 1):
      try:
        self.service.files().delete(fileId=file_id).execute(num_retries=max_retries)
        return
      except (HttpError, TimeoutError, OSError) as e:
        if attempt == max_retries:
          logging.error("Failed to delete remote file %s: %s", file_id, e)
        time.sleep(2)

  def ocr_file(self, local_file_path, ocr_file_path=None):
    if ocr_file_path is None:
      ocr_file_path = local_file_path + ".txt"

    if os.path.exists(ocr_file_path):
      logging.debug("Not OCRing: %s already exists", ocr_file_path)
      return

    logging.info("OCRing %s to %s", local_file_path, ocr_file_path)
    upload_result = self.upload(local_file_path=local_file_path)
    uploaded_file_id = upload_result["id"]

    try:
      self.download_text(local_file_path=ocr_file_path, file_id=uploaded_file_id)
    finally:
      # Ensure file cleanup on drive even if download fails
      self.delete_file(file_id=uploaded_file_id)