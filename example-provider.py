#!/usr/bin/env python

"""External engine provider example for lichess.org"""

import argparse
import contextlib
import json
import logging
import multiprocessing
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import requests


def ok(res):
    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.exception("Response: %s", res.text)
    return res


def register_engine(args, http):
    res = ok(http.get(f"{args.lichess}/api/external-engine"))

    secret = args.provider_secret or secrets.token_urlsafe(32)

    registration = {
        "name": args.name,
        "maxThreads": args.max_threads,
        "maxHash": args.max_hash,
        "shallowDepth": args.shallow_depth,
        "deepDepth": args.deep_depth,
        "providerSecret": secret,
    }

    for engine in res.json():
        if engine["name"] == args.name:
            logging.info("Updating engine %s", engine["id"])
            ok(http.put(f"{args.lichess}/api/external-engine/{engine['id']}", json=registration))
            break
    else:
        logging.info("Registering new engine")
        ok(http.post(f"{args.lichess}/api/external-engine", json=registration))

    return secret


def main(args):
    engine = Engine(args)
    http = requests.Session()
    http.headers["Authorization"] = f"Bearer {args.token}"
    secret = register_engine(args, http)

    def request_handler(*args, **kwargs):
        return EngineRequestHandler(*args, **kwargs, engine=engine)

    server = ThreadedHTTPServer(("", 9666), request_handler)
    server.serve_forever()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


class EngineRequestHandler(BaseHTTPRequestHandler):
    PATH_REGEX = re.compile(r"/api/external-engine/[^/]+/analyse")

    def __init__(self, *args, engine, **kwargs):
        self.engine = engine
        super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Length, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()

    def do_POST(self):
        if not self.PATH_REGEX.fullmatch(self.path):
            logging.warning(f"Received unknown API request {self.path}")
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            logging.warning("Invalid Content-Length header")
            self.send_error(HTTPStatus.BAD_REQUEST)
            return

        body = self.rfile.read(length)

        try:
            job = json.loads(body)
        except json.JSONDecodeError:
            logging.warning("Invalid JSON:")
            logging.warning(body)
            self.send_error(HTTPStatus.BAD_REQUEST)
            return

        logging.info(job)
        self.black = self.check_if_black(job)

        self.analysis = {
            "time": 0,
            "nodes": 0,
            "pvs": [{
                "depth": 0,
                "moves": []
            }] * job["work"]["multiPv"]
        }

        self.send_response(HTTPStatus.OK)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()

        with self.engine.analyse(job) as analysis_stream:
            for line in analysis_stream:
                self.update_analysis(line)
                response = json.dumps(self.analysis) + "\r\n"
                try:
                    self.wfile.write(response.encode())
                except ConnectionAbortedError:
                    break

    def check_if_black(self, job):
        work = job["work"]
        black = work["initialFen"].split()[1] == "b"
        return black ^ (len(work["moves"]) % 2 == 1)

    def update_analysis(self, line):
        it = iter(line.split())
        pv = {"depth": 0, "moves": []}
        pv_index = 0
        score_sign = -1 if self.black else 1

        try:
            if next(it) != "info":
                return
            while True:
                match next(it):
                    case "depth":      pv["depth"] = int(next(it))
                    case "multipv":    pv_index = int(next(it)) - 1
                    case "nodes":      self.analysis["nodes"] = int(next(it))
                    case "time":       self.analysis["time"] = int(next(it))
                    case "score":      key, pv[key] = (next(it), int(next(it)) * score_sign)
                    case "upperbound": pass
                    case "lowerbound": pass
                    case "pv":         pv["moves"] += [*it]
                    case _:            next(it)
        except StopIteration:
            pass

        self.analysis["pvs"][pv_index] = pv

class Engine:
    def __init__(self, args):
        self.process = subprocess.Popen(args.engine, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
        self.args = args
        self.session = None
        self.hash = None
        self.threads = None
        self.last_used = time.monotonic()
        self.lock = threading.Lock()
        self.owner_uid = None
        self.analysis = iter(())

        self.uci()
        self.setoption("UCI_AnalyseMode", "true")
        self.setoption("UCI_Chess960", "true")

    def idle_time(self):
        return time.monotonic() - self.last_used

    def terminate(self):
        logging.info("Terminating engine")
        self.process.terminate()

    def stop(self):
        logging.info("Stopping engine")
        self.send("stop")
        for _ in self.analysis:
            pass

    def send(self, command):
        logging.debug("%d << %s", self.process.pid, command)
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def recv(self):
        while True:
            line = self.process.stdout.readline()
            if line == "":
                raise EOFError()

            line = line.rstrip()
            logging.debug("%d >> %s", self.process.pid, line)
            if line:
                return line

    def recv_uci(self):
        command_and_params = self.recv().split(None, 1)
        if len(command_and_params) == 1:
            return command_and_params[0], ""
        else:
            return command_and_params

    def uci(self):
        self.send("uci")
        while True:
            line, _ = self.recv_uci()
            if line == "uciok":
                break

    def isready(self):
        self.send("isready")
        while True:
            line, _ = self.recv_uci()
            if line == "readyok":
                break

    def setoption(self, name, value):
        self.send(f"setoption name {name} value {value}")

    @contextlib.contextmanager
    def analyse(self, job):
        with self.lock:
            if self.owner_uid is not None:
                # Take over the engine
                self.stop()

            work = job["work"]
            uid = object()
            self.owner_uid = uid

            if work["sessionId"] != self.session:
                self.session = work["sessionId"]
                self.send("ucinewgame")
                self.isready()

            if self.threads != work["threads"]:
                self.setoption("Threads", work["threads"])
                self.threads = work["threads"]
            if self.hash != work["hash"]:
                self.setoption("Hash", work["hash"])
                self.hash = work["hash"]
            self.setoption("MultiPV", work["multiPv"])
            self.isready()

            self.send(f"position fen {work['initialFen']} moves {' '.join(work['moves'])}")
            self.send(f"go depth {self.args.deep_depth if work['deep'] else self.args.shallow_depth}")

        def stream():
            while True:
                with self.lock:
                    if self.owner_uid is not uid:
                        break
                    command, params = self.recv_uci()

                match command:
                    case "bestmove":
                        break
                    case "info":
                        if "score" in params:
                            yield f"{command} {params}\r\n"
                    case _:
                        logging.warning("Unexpected engine command: %s", command)

        self.analysis = stream()
        try:
            yield self.analysis
        finally:
            with self.lock:
                if self.owner_uid is uid:
                    self.stop()
                    self.owner_uid = None

        self.last_used = time.monotonic()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="Alpha 2", help="Engine name to register")
    parser.add_argument("--engine", help="Shell command to launch UCI engine", required=True)
    parser.add_argument("--lichess", default="https://lichess.org", help="Defaults to https://lichess.org")
    parser.add_argument("--broker", default="https://engine.lichess.ovh", help="Defaults to https://engine.lichess.ovh")
    parser.add_argument("--token", default=os.environ.get("LICHESS_API_TOKEN"), help="API token with engine:read and engine:write scopes")
    parser.add_argument("--provider-secret", default=os.environ.get("PROVIDER_SECRET"), help="Optional fixed provider secret")
    parser.add_argument("--deep-depth", type=int, default=99)
    parser.add_argument("--shallow-depth", type=int, default=25)
    parser.add_argument("--max-threads", type=int, default=multiprocessing.cpu_count(), help="Maximum number of available threads")
    parser.add_argument("--max-hash", type=int, default=512, help="Maximum hash table size in MiB")
    parser.add_argument("--keep-alive", type=int, default=120, help="Number of seconds to keep an idle/unused engine process around")

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
