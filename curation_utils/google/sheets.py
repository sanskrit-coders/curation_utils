import logging
import os
import pprint

import gspread
import pandas
from oauth2client.service_account import ServiceAccountCredentials

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s"
)
logging.getLogger('gspread').setLevel(logging.INFO)
logging.getLogger('oauth2client').setLevel(logging.INFO)


def get_sheet(spreadhsheet_id, worksheet_name, google_key):
    """

    :param spreadhsheet_id: 
    :param worksheet_name: 
    :param google_key: Path to a json file which can be obtained from https://console.cloud.google.com/iam-admin/serviceaccounts (create a project, generate a key via "Actions" column.).

    :return: 
    """
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(google_key, scopes)

    client = gspread.authorize(creds)
    logging.debug(pprint.pformat(client.list_spreadsheet_files()))
    sheet_book = client.open_by_key(spreadhsheet_id)
    logging.debug(sheet_book.worksheets())
    return sheet_book.worksheet(worksheet_name)


class IndexSheet(object):
    def __init__(self, spreadhsheet_id, worksheet_name, google_key,
                 id_column):
        self.data_sheet = get_sheet(spreadhsheet_id=spreadhsheet_id, worksheet_name=worksheet_name, google_key=google_key)
        self.id_column = id_column
        episode_sheet_values = self.data_sheet.get_all_values()
        df = pandas.DataFrame(episode_sheet_values[1:], columns=episode_sheet_values.pop(0))
        df = df.set_index(self.id_column)
        self._df = df

    def get_value(self, id, column_name):
        try:
            return self._df.loc[id, column_name]
        except KeyError:
            logging.debug("Could not find %s in the sheet", id)
            return None


class FileUrlSheet(IndexSheet):
    """
    Represents image data stored in a Google spreadsheet.
    """
    def __init__(self, spreadhsheet_id, worksheet_name, google_key,
                 url_column, file_name_column=None):
        """
    
        :return: 
        """
        # noinspection PyPep8Naming
        super(FileUrlSheet, self).__init__(spreadhsheet_id=spreadhsheet_id, worksheet_name=worksheet_name, google_key=google_key, id_column=url_column)
        self.file_name_column = file_name_column

    def get_file_name(self, url):
        """
        Read the name of the person who recorded this episode.
    
        :param url: 
        :return: 
        """
        file_name = self._df.loc[url, self.file_name_column]
        file_name = file_name.strip()
        import re
        file_name = re.sub("[^a-zA-Z0-9]+", "-", file_name)
        return file_name

    def download_all(self, destination_dir, skip_existing=True):
        import wget
        os.makedirs(destination_dir, exist_ok=True)
        for url in self._df.index:
            extension = os.path.splitext(url)[1]
            out_file = os.path.join(destination_dir, "%s%s" % (self.get_file_name(url=url), extension))
            if not skip_existing or not os.path.exists(out_file):
                logging.info("Getting %s as %s", url, out_file)
                wget.download(url=url, out=out_file)