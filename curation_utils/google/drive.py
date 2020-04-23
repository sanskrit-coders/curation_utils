import io
import logging
import os

from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)
logging.getLogger('oauth2client').setLevel(logging.INFO)

class DriveClient(object):
    def __init__(self, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json'):
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

    def ocr_file(self, local_file_path):
        ocr_file_path = local_file_path + ".txt"
        if os.path.exists(ocr_file_path):
            logging.warning("Not OCRing: %s already exists", ocr_file_path)
        else:
            upload_result = self.upload(local_file_path=local_file_path)
            uploaded_file_id = upload_result["id"]
            self.download_text(local_file_path=ocr_file_path, file_id=uploaded_file_id)
            self.delete_file(file_id=uploaded_file_id)