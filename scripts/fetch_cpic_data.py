#!/usr/bin/env python3
"""Fetch pharmacogenomics data from CPIC API.

Thin wrapper — delegates to genechat.seeds.fetch_cpic_data.
"""

import sys

if __name__ == "__main__":
    from genechat.seeds.fetch_cpic_data import main

    sys.exit(main())
