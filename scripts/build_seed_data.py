#!/usr/bin/env python3
"""Build seed data pipeline: fetch from APIs, rebuild SQLite.

Thin wrapper — delegates to genechat.seeds.pipeline.
"""

import sys

if __name__ == "__main__":
    from genechat.seeds.pipeline import run_pipeline

    sys.exit(run_pipeline())
