import io
import os
from builtins import open as fopen


class MultiFileReader(io.BufferedIOBase):

  def __init__(self, *args):
    filenames = []
    for arg in args:
      if isinstance(arg, str):
        filenames.append(arg)
      else:
        for name in arg:
          filenames.append(name)
    files = []
    ranges = []
    offset = 0
    for name in filenames:
      size = os.stat(name).st_size
      ranges.append(range(offset, offset+size))
      files.append(fopen(name, 'rb'))
      offset += size
    self.size = offset
    self._ranges = ranges
    self._files = files
    self._fcount = len(self._files)
    self._offset = -1
    self.seek(0)

  def  __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.close()
    return False

  def close(self):
    for f in self._files:
      f.close()
    self._files.clear()
    self._ranges.clear()

  def closed(self):
    return len(self._ranges) == 0

  def isatty(self):
    return False

  def readable(self):
    return True

  def seek(self, offset, whence=io.SEEK_SET):
    if whence == io.SEEK_SET:
      self._offset = offset
    elif whence == io.SEEK_CUR:
      self._offset = self._offset + offset
    elif whence == io.SEEK_END:
      self._offset = self.size + offset
    else:
      raise ValueError('Invalid value for parameter whence: %r' % whence)
    return self._offset

  def seekable(self):
    return True

  def tell(self):
    return self._offset

  def writable(self):
    return False

  def read(self, n=-1):
    file_index = -1
    actual_offset = 0
    for i, r in enumerate(self._ranges):
      if self._offset in r:
        file_index = i
        actual_offset = self._offset - r.start
        break
    result = b''
    if (n == -1 or n is None):
      to_read = self.size
    else:
      to_read = n
    while -1 < file_index < self._fcount:
      f = self._files[file_index]
      f.seek(actual_offset)
      read = f.read(to_read)
      read_count = len(read)
      self._offset += read_count
      result += read
      to_read -= read_count
      if to_read > 0:
        file_index += 1
        actual_offset = 0
      else:
        break
    return result


