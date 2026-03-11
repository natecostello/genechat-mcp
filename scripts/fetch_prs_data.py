#!/usr/bin/env python3
"""Fetch polygenic risk score weights from PGS Catalog FTP.

Thin wrapper — delegates to genechat.seeds.fetch_prs_data.
"""

import sys

if __name__ == "__main__":
    from genechat.seeds.fetch_prs_data import main

    sys.exit(main())
