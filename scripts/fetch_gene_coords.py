#!/usr/bin/env python3
"""Fetch gene coordinates from Ensembl REST API.

Thin wrapper — delegates to genechat.seeds.fetch_gene_coords.
"""

import sys

if __name__ == "__main__":
    from genechat.seeds.fetch_gene_coords import main

    sys.exit(main())
