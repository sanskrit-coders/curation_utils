import io
import logging
import os
from functools import lru_cache

import socket
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

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
    def __init__(self, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json'):
        """ Interact with Google Drive via this client.
        
        :param google_key: Path to a json file which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.).

        """
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(google_key, scopes)
        self.service = discovery.build('drive', 'v3', credentials=creds, cache_discovery=False)

    def upload(self, local_file_path, mime='application/vnd.google-apps.document'):
        from googleapiclient.http import MediaFileUpload
        logging.info("Uploading %s", local_file_path)
        result = self.service.files().create(
            body={
                'name': local_file_path,
                'mimeType': mime
            },
            media_body=MediaFileUpload(local_file_path, mimetype=mime, resumable=True)
        ).execute()
        return result

    def download_text(self, local_file_path, file_id):
        from googleapiclient.http import MediaIoBaseDownload
        logging.info("Downloading %s", local_file_path)
        dl = MediaIoBaseDownload(
            io.FileIO(local_file_path, 'wb'),
            self.service.files().export_media(fileId=file_id, mimeType="text/plain")
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
            logging.warning("Not OCRing: %s already exists", ocr_file_path)
        else:
            upload_result = self.upload(local_file_path=local_file_path)
            uploaded_file_id = upload_result["id"]
            self.download_text(local_file_path=ocr_file_path, file_id=uploaded_file_id)
            self.delete_file(file_id=uploaded_file_id)
