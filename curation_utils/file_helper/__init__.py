import codecs
import itertools
import logging
import os
import re
import shutil
from pathlib import Path

import regex
from chardet import UniversalDetector

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")
logging.getLogger('charsetgroupprober').setLevel(logging.WARNING)
logging.getLogger("charsetgroupprober").propagate = False
logging.getLogger('sbcharsetprober').setLevel(logging.WARNING)
logging.getLogger("sbcharsetprober").propagate = False

re_chars_to_remove = re.compile('[\uFEFF\u00A0\r﻿]')


def clear_bad_chars(s):
    s = re_chars_to_remove.sub('', s)
    return s


def detect_encoding(file_path):
    detector = UniversalDetector()
    detector.reset()
    with open(file_path, 'rb') as file:
        for line in file.readlines():
            detector.feed(line)
            if detector.done: break
    detector.close()
    return detector.result['encoding']


def unicodify(file_path):
    encoding = detect_encoding(file_path=file_path)
    if encoding == "utf-8":
        return 
    logging.info("From %s to utf-8: Converting %s", file_path, encoding)
    BLOCKSIZE = 1048576 # or some other, desired size in bytes
    tmp_file = str(file_path) + ".utf.local"
    with codecs.open(file_path, "r", encoding) as sourceFile:
        with codecs.open(tmp_file, "w", "utf-8") as targetFile:
            while True:
                contents = sourceFile.read(BLOCKSIZE)
                if not contents:
                    break
                targetFile.write(contents)
    _ = shutil.move(tmp_file, file_path)


def clear_bad_chars_in_file(file_path, dry_run=False):
    try:
        with open(file_path, 'r', encoding="utf-8") as file:
            text = clear_bad_chars(s=file.read())
    except Exception:
        unicodify(file_path=file_path)
        with open(file_path, 'r', encoding="utf-8") as file:
            text = clear_bad_chars(s=file.read())
    with open(file_path, 'w', encoding="utf-8") as file:
        if not dry_run:
            file.writelines(text)
        else:
            logging.info(text)


def concatenate_files(input_path_list, output_path, add_newline_inbetween=False):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path,'wb') as outfile:
        for f in input_path_list:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, outfile)
            if add_newline_inbetween:
                outfile.write("\n".encode())


def clean_file_path(file_path):
    file_path_out = regex.sub("[^a-zA-Z0-9 _\\-~./]", "", file_path.strip())
    file_path_out = regex.sub(" +", "_", file_path_out)
    file_path_out = regex.sub("__+", "_", file_path_out)
    file_path_out = regex.sub("_([./])", "\\1", file_path_out)
    return file_path_out


def clean_file_names(dir_path, dry_run=False):
    paths = list(Path(dir_path).glob("**/*"))
    logging.info("Got %d paths", len(paths))
    for path in paths:
        path = str(path)
        # logging.debug("Checking '%s'", path)
        dest_path = clean_file_path(path)
        if path != dest_path:
            logging.info("Changing '%s' to '%s'", path, dest_path)
            if not dry_run:
                os.rename(path, dest_path)


def copy_file_tree(source_dir, dest_dir, file_pattern, file_name_filter=None):
    file_paths = sorted(filter(file_name_filter, Path(source_dir).glob(file_pattern)))
    for file_path in file_paths:
        dest_path = str(file_path).replace(source_dir, dest_dir)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        logging.info("Moving %s to %s", file_path, dest_path)
        _ = shutil.copyfile(file_path, dest_path)