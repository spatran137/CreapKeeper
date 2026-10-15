#!/usr/bin/env python3
"""Backward-compatible one-click command: record a direct approach."""

import sys
from cli import main


if __name__ == "__main__":
    raise SystemExit(main(["count", *sys.argv[1:]]))
