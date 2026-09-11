"""Isolated standard-library-only public OHLC fetch worker.

The operator starts this file with ``python -I -S -B`` and enforces its entire
lifetime from the parent. No Aureon package, trading client, credential store,
site package, runtime service or application state is imported here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROVIDER_URL = "https://api.kraken.com/0/public/OHLC"
MAX_RESPONSE_BYTES = 512 * 1024
PAIRS = {"BTCUSD": "XBTUSD", "ETHUSD": "ETHUSD", "SOLUSD": "SOLUSD"}


class SourceError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("source_redirect_refused")


def _read_source(url: str) -> bytes:
    """The private transport seam is used by loopback regression fixtures.

    Production main builds the URL only from the fixed host and closed choices.
    The parent process deadline covers DNS, connect, TLS, headers and all body
    framing. Socket idle timeouts are supplementary, not the total-time bound.
    """
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json", "User-Agent": "Aureon-Historical-Replay/1.0"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=5) as response:
        if response.status != 200:
            raise SourceError("source_unavailable")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SourceError("source_too_large")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Internal isolated public OHLC source fetch")
    parser.add_argument("--symbol", choices=tuple(PAIRS), required=True)
    parser.add_argument("--interval-minutes", type=int, choices=(60, 1440), required=True)
    parser.add_argument("--since", type=int, required=True)
    args = parser.parse_args(argv)
    if not 0 <= args.since <= int(time.time()):
        parser.error("since must be a non-future Unix timestamp")
    if os.environ.get("AUREON_NO_EXTERNAL_API_CALLS", "").strip().lower() in {"1", "true", "yes", "on", "t", "y"}:
        print(json.dumps({"reason_code": "external_reads_held"}), file=sys.stderr)
        return 2
    url = PROVIDER_URL + "?" + urllib.parse.urlencode({"pair": PAIRS[args.symbol], "interval": args.interval_minutes, "since": args.since})
    try:
        raw = _read_source(url)
        sys.stdout.buffer.write(raw)
        return 0
    except SourceError as exc:
        code = exc.code
    except (OSError, urllib.error.URLError):
        code = "source_unavailable"
    except Exception:
        code = "source_failed"
    # No remote error body, headers, traceback, paths or environment values.
    print(json.dumps({"reason_code": code}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
