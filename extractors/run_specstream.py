#!/usr/bin/env python3
"""
Run the SpecStream Extract API on the benchmark's saved HTML.

The HTML of each page and its URL from ground-truth.json are sent in the
request body ("pages" items), so the API fetches nothing and reads exactly the
HTML the other extractors read.

Usage (from the repository root):

    SPECSTREAM_API_KEY=... python3 extractors/run_specstream.py

API docs: https://specstream.ai/agents.md
"""
import gzip
import json
import os
import time
from pathlib import Path

import requests

from output_util import write_output_json

API_URL = os.environ.get("SPECSTREAM_EXTRACT_URL", "https://api.specstream.ai/v1/extract")
BATCH = 10
VERSION = "2026-11-08"


def read_html(path: Path) -> str:
    raw = gzip.open(path).read()
    try:
        return raw.decode("utf8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def extract(session: requests.Session, pages: list) -> list:
    for attempt in range(5):
        resp = session.post(API_URL, json={"pages": pages, "format": "text"}, timeout=180)
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        body = resp.json()
        if body.get("data") is None:
            raise RuntimeError((body.get("error") or {}).get("message", "no data in reply"))
        return body["data"]["results"]
    resp.raise_for_status()
    raise RuntimeError(f"Extract API returned {resp.status_code}")


def main():
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + os.environ["SPECSTREAM_API_KEY"]
    urls = {k: v.get("url") for k, v in json.loads(Path("ground-truth.json").read_text("utf8")).items()}
    paths = sorted(Path("html").glob("*.html.gz"))
    output = {}
    for start in range(0, len(paths), BATCH):
        chunk = paths[start:start + BATCH]
        results = extract(session, [{"html": read_html(p), "url": urls.get(p.stem.split(".")[0])} for p in chunk])
        for path, result in zip(chunk, results):
            item_id = path.stem.split(".")[0]
            output[item_id] = {"articleBody": result.get("text") or ""}
    write_output_json(Path("output") / "specstream.json", output=output, version=VERSION)


if __name__ == "__main__":
    main()
