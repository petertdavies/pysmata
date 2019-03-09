import sys
import pathlib
import argparse
import gzip
import json
import requests
import datadiff

import pysmata.loader as loader
import pysmata.files

def main_replay(args):
  j = pysmata.files.get_replay(args.code)
  json.dump(j, sys.stdout, indent=2, sort_keys=True)

def main_game(args):
  j = pysmata.files.get_game(args.code, log=args.log)
  json.dump(j, sys.stdout, indent=2, sort_keys=True)

def main_bulk(args):
  with open(args.codes_file) as f:
    for n, line in enumerate(f):
      sline = line.strip()
      if sline != "" and sline[0] != '#':
        pysmata.files.get_game(sline)
        print(n, sline)

def main():
  parser = argparse.ArgumentParser(description="Process Prismata replays and games")
  
  subparsers = parser.add_subparsers()
  
  parser_replay = subparsers.add_parser('get-replay')
  parser_replay.add_argument('code', help="Replay code")
  parser_replay.set_defaults(func=main_replay)
  
  parser_game = subparsers.add_parser('get-game')
  parser_game.add_argument('code', help='Replay code')
  parser_game.add_argument('-l', '--log', help="Write a log file", action='store_true')
  parser_game.set_defaults(func=main_game)
  
  parser_bulk = subparsers.add_parser('bulk')
  parser_bulk.add_argument('codes_file', help="File with list of replay codes")
  parser_bulk.set_defaults(func=main_bulk)
  
  args = parser.parse_args()
  
  if hasattr(args, "func"):
    return args.func(args)
  else:
    parser.print_help()

if __name__ == "__main__":
  main()
