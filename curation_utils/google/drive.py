import io
import logging
import os
import time
from functools import lru_cache

import socket

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Set the default timeout to 10 minutes
# https://github.com/googleapis/google-api-python-client/issues/632#issuecomment-541973021
socket.setdefaulttimeout(600)

# Remove all handlers associated with the root logger object.
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
    """ Interact with Google Drive via this client.
    
    :param google_key: Path to a json file which can be obtained from https://console.cloud.google.com/apis/credentials - create oauth key for desktop app; download client secret. Enable drive api access.
    Deprecated (Cant access user drive.) - https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.). 
      
    :param folder_key - share a folder with the service account mail id, then copy it's key (xxxx) from the url - https://drive.google.com/drive/folders/XXXXXXXXXXXX  

    """
    # 'https://spreadsheets.google.com/feeds', 
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
          flow = InstalledAppFlow.from_client_secrets_file(
            google_key, scopes)
          creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
          token.write(creds.to_json())

    self.service = discovery.build('drive', 'v3', credentials=creds)
    self.folder_key = folder_key


  def upload(self, local_file_path, mime='application/vnd.google-apps.document', max_retries=4):
    from googleapiclient.http import MediaFileUpload
    logging.info(f"Uploading {local_file_path} to {self.folder_key}")
    for attempt in range(1, max_retries + 1):
      try:
        logging.info("Attempt %d: Uploading %s", attempt, local_file_path)
        result = self.service.files().create(
          body={
            'name': local_file_path,
            'mimeType': mime,
            'parents': [self.folder_key]
          },
          media_body=MediaFileUpload(local_file_path, mimetype=mime, resumable=True),
          supportsAllDrives=True
        ).execute()
        logging.info("Upload succeeded on attempt %d", attempt)
        return result
      except HttpError as e:
        logging.warning("HttpError on attempt %d: %s", attempt, e)
        if attempt == max_retries:
          raise  # re‑raise after last attempt
        # backoff before retrying
        time.sleep(2 ** attempt)


  def download_text(self, local_file_path, file_id, mime_type="text/markdown"):
    # Alternates - "text/plain"
    from googleapiclient.http import MediaIoBaseDownload
    logging.info("Downloading %s", local_file_path)
    dl = MediaIoBaseDownload(
      io.FileIO(local_file_path, 'wb'),
      self.service.files().export_media(fileId=file_id, mimeType=mime_type)
    )
    done = False
    while done is False:
      status, done = dl.next_chunk()
    logging.info("Done downloading %s", local_file_path)

  def delete_file(self, file_id):
    logging.info("Deleting %s", str(file_id))
    self.service.files().delete(fileId=file_id).execute()

  def ocr_file(self, local_file_path, ocr_file_path=None):
    if ocr_file_path == None:
      ocr_file_path = local_file_path + ".txt"
    if os.path.exists(ocr_file_path):
      logging.debug("Not OCRing: %s already exists", ocr_file_path)
    else:
      logging.info("OCRing %s to %s", local_file_path, ocr_file_path)
      upload_result = self.upload(local_file_path=local_file_path)
      uploaded_file_id = upload_result["id"]
      self.download_text(local_file_path=ocr_file_path, file_id=uploaded_file_id)
      self.delete_file(file_id=uploaded_file_id)
