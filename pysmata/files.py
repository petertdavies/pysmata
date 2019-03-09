import sys
import pathlib
import json
import requests
import gzip

import pysmata.loader as loader

def get_replay(code):
  p = pathlib.Path.home() / '.pysmata' / 'replays' / code
  try:
    with p.open('x') as f:
      try:
        r = requests.get("http://saved-games-alpha.s3-website-us-east-1.amazonaws.com/" + code + ".json.gz")
        j = json.loads(gzip.decompress(r.content).decode())
        json.dump(j, f, indent=2, sort_keys=True)
      except BaseException:
        p.unlink()
        raise
  except FileExistsError:
    with p.open() as f:
      j = json.load(f)
  return j

def get_game(code, log=False):
  j = get_replay(code)
  try:
    p = pathlib.Path.home() / '.pysmata' / 'games' / code
    with p.open('x') as f:
      try:
        if log:
          with (pathlib.Path.home() / '.pysmata' / 'log').open("w") as log_file:
            j2 = loader.load_game(j, log_file=log_file)
        else:
          j2 = loader.load_game(j, log_file=None)
      except Exception:
        f.write("Replay processing failed!")
        raise Exception("Could not process " + code)
      else:
        json.dump(j2, f, indent=2, sort_keys=True)
        return j2
  except FileExistsError:
    with p.open() as f:
      j = json.load(f)
      return j
