from pathlib import Path
import tomllib


def get_toml_value(key: str, path: str | Path="/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/tokens.toml", default=None):
  with open(path, "rb") as f:
    data = tomllib.load(f)

  value = data
  for part in key.split("."):
    if not isinstance(value, dict) or part not in value:
      return default
    value = value[part]

  return value