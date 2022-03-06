import codecs
import logging
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import regex
import requests
from chardet import UniversalDetector
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes import roman

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")
logging.getLogger('charsetgroupprober').setLevel(logging.WARNING)
logging.getLogger("charsetgroupprober").propagate = False
logging.getLogger('sbcharsetprober').setLevel(logging.WARNING)
logging.getLogger("sbcharsetprober").propagate = False

re_chars_to_remove = re.compile('[\uFEFF\u00A0\r﻿​]')


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
  BLOCKSIZE = 1048576  # or some other, desired size in bytes
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
  with open(output_path, 'wb') as outfile:
    for f in input_path_list:
      with open(f, 'rb') as fd:
        shutil.copyfileobj(fd, outfile)
      if add_newline_inbetween:
        outfile.write("\n".encode())


def clean_file_path(file_path):
  file_path_out = regex.sub("[^a-zA-Z0-9 _\\-~./]", "", file_path.strip())
  # Handle avagrahas
  file_path_out = regex.sub(r"(\S)\.a", "\\1-", file_path_out)
  file_path_out = regex.sub(" +", "_", file_path_out)
  file_path_out = regex.sub("__+", "__", file_path_out)
  file_path_out = regex.sub("_([./])", "\\1", file_path_out)
  return file_path_out


def clean_file_name(name):
  name_parts = name.split(".")
  fixed_parts = []
  for name_part in name_parts:
    fixed_parts.append(clean_file_path(file_path=name_part).replace("/", "_SLASH_"))
  return ".".join(fixed_parts)


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


def download_file(url: str, filepath: str = None):
  ''' Download file from url to specified filepath.
      If filepath is None, then the file is saved in the current directory
      and the path is returned.
  '''
  if filepath is None:
    path = urlparse(url).path
    filepath = Path(path).name
  r = requests.get(url, stream=True)
  with open(filepath, "wb") as fd:
    for chunk in r.iter_content(chunk_size=128):
      fd.write(chunk)
  return filepath


def remove_empty_dirs(path):
  def remove_dir_if_empty(path):
    try:
      os.rmdir(path)
    except OSError:
      pass

  remove_dir_if_empty(path=path)
  for root, dirnames, filenames in os.walk(path, topdown=False):
    for dirname in dirnames:
      remove_dir_if_empty(os.path.realpath(os.path.join(root, dirname)))


def get_storage_name(text, source_script=None, max_length=50, maybe_use_dravidian_variant=True, mixed_languages_in_titles=True):
  from indic_transliteration import detect
  if source_script is None:
    source_script = detect.detect(text=text)
  text_optitrans = regex.sub("/ *", "__", text)
  if source_script in roman.ALL_SCHEME_IDS:
    if source_script in roman.CAPITALIZABLE_SCHEME_IDS:
      if mixed_languages_in_titles:
        text_optitrans = sanscript.SCHEMES[sanscript.IAST].mark_off_non_indic_in_line(text_optitrans)
      text_optitrans = sanscript.transliterate(text_optitrans, source_script, sanscript.OPTITRANS, suspend_on= set('<'), suspend_off = set('>'), maybe_use_dravidian_variant=maybe_use_dravidian_variant)
  else:
    text_optitrans = sanscript.transliterate(text_optitrans, source_script, sanscript.OPTITRANS, maybe_use_dravidian_variant=maybe_use_dravidian_variant)
  storage_name = clean_file_path(text_optitrans)
  if max_length is not None:
    storage_name = storage_name[:max_length]
  return storage_name


def substitute_with_latest(paths_in, latest_file_paths, dry_run=False):
  basenames = [os.path.basename(file) for file in latest_file_paths]
  undated_basenames = ["_".join(basename.split("_")[1:]) for basename in basenames if "_" in basename]
  undated_basename_to_latest_path = dict(zip(undated_basenames, latest_file_paths))
  basename_to_latest_path = dict(zip(basenames, latest_file_paths))
  for file in paths_in:
    basename = os.path.basename(file)
    if basename in basename_to_latest_path and basename != "_index.md":
      logging.info("Updating %s at %s", basename, file)
      if not dry_run:
        shutil.copy(basename_to_latest_path[basename], file)
    elif basename in undated_basename_to_latest_path and basename != "_index.md":
      logging.info("Updating %s at %s", basename, file)
      if not dry_run:
        shutil.copy(undated_basename_to_latest_path[basename], file)
    elif basename != "_index.md":
      logging.warning("Could not update %s at %s", basename, file)


def rename_files(name_map, path_prefix=None, dry_run=False):
  for original, new in name_map.items():
    if path_prefix is not None:
      original = os.path.join(path_prefix, original)
      new = os.path.join(path_prefix, new)
    if original == new or not os.path.exists(original):
      continue
    logging.info("%s → %s", original, new) 
    if not dry_run:
      if os.path.exists(new):
        shutil.rmtree(new)
      shutil.move(original, new)
