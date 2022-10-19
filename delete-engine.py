#!/usr/bin/env python

import argparse
import logging
import os
import sys

import requests


def ok(res):
    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.exception("Response: %s", res.text)
    return res

def main(args):
    http = requests.Session()
    http.headers["Authorization"] = f"Bearer {args.token}"

    res = ok(http.get(f"{args.lichess}/api/external-engine"))

    if args.name is not None or args.id is not None:
        for engine in res.json():
            if engine["name"] == args.name or engine["id"] == args.id:
                logging.info("Deleting engine %s", engine["id"])
                ok(http.delete(f"{args.lichess}/api/external-engine/{engine['id']}"))
                return
        logging.error("Engine not found.")

    logging.info("Registered engines:")
    for engine in res.json():
        logging.info("    %32s %s", engine["name"], engine["id"])

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=None, help="Engine name to delete")
    parser.add_argument("--id", default=None, help="Engine ID to delete")
    parser.add_argument("--lichess", default="https://lichess.org", help="Defaults to https://lichess.org")
    parser.add_argument("--token", default=os.environ.get("LICHESS_API_TOKEN"), help="API token with engine:read and engine:write scopes")

    try:
        import argcomplete
    except ImportError:
        pass
    else:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if not args.token:
        print(f"Need LICHESS_API_TOKEN environment variable from {args.lichess}/account/oauth/token/create?scopes[]=engine:read&scopes[]=engine:write")
        sys.exit(128)

    try:
        main(args)
    except KeyboardInterrupt:
        pass
