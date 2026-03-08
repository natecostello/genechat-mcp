# MCP Server Setup Comparison

How GeneChat's setup compares to other MCP servers with significant data or infrastructure requirements.

## Setup Step Comparison

### 1. Install System Dependencies

| Server | What | Command |
|--------|------|---------|
| **GeneChat** | bcftools + SnpEff | `brew install bcftools brewsci/bio/snpeff` |
| **bio-mcp-blast** | BLAST+ | `conda install -c bioconda blast` |
| **SCMCP** | None (pure Python) | `pip install scmcp` |
| **Graphiti** | Docker + npm | `docker`, `npm install -g mcp-remote` |
| **Crawl4AI RAG** | Playwright + Chromium | `crawl4ai-setup` |
| **GDAL MCP** | None (bundled via uv) | `uvx --from gdal-mcp gdal` |
| **Engram** | Go + Ollama | `ollama pull nomic-embed-text` |

GeneChat's dependency story is similar to bio-mcp-blast: domain-specific bioinformatics tools that must be installed separately.

### 2. Clone / Install

| Server | Method | Command |
|--------|--------|---------|
| **GeneChat** | Clone + uv sync | `git clone ... && uv sync` |
| **bio-mcp-blast** | Clone + pip | `git clone ... && pip install -e .` |
| **SCMCP** | PyPI | `pip install scmcp` |
| **Graphiti** | Clone + uv sync | `git clone ... && cd mcp_server && uv sync` |
| **Crawl4AI RAG** | Clone + uv pip | `git clone ... && uv pip install -e .` |
| **GDAL MCP** | PyPI via uvx | `uvx --from gdal-mcp gdal` |
| **Engram** | Binary download or Go build | `go build -o engram ./cmd/engram/main.go` |

Most complex servers require cloning. Only SCMCP, GDAL MCP, and Engram (binary) skip this.

### 3. Download / Provision External Data

| Server | Data | Size | Command |
|--------|------|------|---------|
| **GeneChat** | ClinVar + SnpEff DB + gnomAD (optional) | ~10 GB | `uv run genechat download [--gnomad]` |
| **bio-mcp-blast** | BLAST databases (nt, nr, swissprot) | 100+ GB | `update_blastdb.pl --decompress nt` |
| **SCMCP** | None (operates on user data) | — | — |
| **Graphiti** | Neo4j (Docker container) | ~500 MB | `docker compose up` |
| **Crawl4AI RAG** | Supabase schema + Chromium | ~200 MB | Manual SQL in dashboard + `crawl4ai-setup` |
| **GDAL MCP** | None (operates on user data) | — | — |
| **Engram** | Ollama embedding model | ~270 MB | `ollama pull nomic-embed-text` |

GeneChat and bio-mcp-blast are the heaviest here — bioinformatics reference databases are large. But GeneChat's is a one-time download via a single CLI command, while BLAST databases must be individually selected and downloaded.

### 4. Process / Transform Data

| Server | What | Time | Command |
|--------|------|------|---------|
| **GeneChat** | Build patch.db (SnpEff → ClinVar → gnomAD) | ~20-30 min | `uv run genechat annotate --all` (or via `uv run genechat init`) |
| **bio-mcp-blast** | None (databases used as-is) | — | — |
| **SCMCP** | None | — | — |
| **Graphiti** | None (graph built at runtime) | — | — |
| **Crawl4AI RAG** | Execute SQL schema in Supabase | ~1 min | Manual copy-paste in dashboard |
| **GDAL MCP** | None | — | — |
| **Engram** | None (DB created on first run) | — | — |

**GeneChat is unique here.** The VCF annotation step is a significant data transformation pipeline that takes 20-30 minutes. No other MCP server has an equivalent processing step. This is inherent to the domain — raw WGS data must be annotated before it's queryable.

### 5. Configure

| Server | Method | Command |
|--------|--------|---------|
| **GeneChat** | `genechat init` (writes config + prints MCP JSON) | `uv run genechat init /path/to/raw.vcf.gz` |
| **bio-mcp-blast** | 6+ env vars | `export BLASTDB=... BLAST_NUM_THREADS=...` |
| **SCMCP** | None needed | — |
| **Graphiti** | `.env` file (6+ vars) | `cp .env.example .env && edit` |
| **Crawl4AI RAG** | `.env` file (10+ vars) | Create `.env` with API keys + Supabase creds |
| **GDAL MCP** | 1 env var | `export GDAL_MCP_WORKSPACES=/path/to/data` |
| **Engram** | 3 env vars | `export DUCKDB_PATH=... OLLAMA_URL=...` |

GeneChat's `genechat init` is notably cleaner than most. It auto-generates config and prints the exact MCP JSON to paste — no manual env var juggling.

### 6. MCP Client Config

| Server | Config style |
|--------|-------------|
| **GeneChat** | `"command": "uv", "args": ["run", "--directory", "...", "genechat"]` with `GENECHAT_CONFIG` env |
| **bio-mcp-blast** | `"command": "python", "args": ["-m", "src.server"]` with `cwd` |
| **SCMCP** | `"command": "/path/to/scmcp", "args": ["run", "--run-mode", "tool"]` |
| **Graphiti** | `"command": "npx", "args": ["mcp-remote", "http://localhost:8000/mcp/"]` |
| **Crawl4AI RAG** | HTTP/SSE: `"url": "http://localhost:8051/sse"` |
| **GDAL MCP** | `"command": "uvx", "args": ["--from", "gdal-mcp", "gdal"]` |
| **Engram** | `"command": "/path/to/engram"` with env vars |

GeneChat follows the standard `uv run` pattern. GDAL MCP is the gold standard (`uvx` one-liner), but it has no data dependencies.

## End-to-End Command Count

| Server | Total commands to working server | External services needed |
|--------|--------------------------------|------------------------|
| **GeneChat** | 5 (install tools, clone, download refs, annotate, init) | None |
| **bio-mcp-blast** | 4+ (install BLAST, clone, download DBs, set env vars) | None |
| **SCMCP** | 1 (`pip install scmcp`) | None |
| **Graphiti** | 5 (install uv, clone, configure .env, docker compose, start server) | Docker (Neo4j), OpenAI API |
| **Crawl4AI RAG** | 6+ (clone, venv, install, setup, SQL schema, configure .env) | Supabase, OpenAI API |
| **GDAL MCP** | 1 (`uvx --from gdal-mcp gdal`) | None |
| **Engram** | 3 (install Ollama, pull model, download binary) | Ollama |

## Key Takeaway

GeneChat's setup complexity is comparable to bio-mcp-blast and simpler than Crawl4AI RAG or Graphiti. The VCF annotation step is the unique burden — but that's the core value proposition (turning a raw VCF into something an LLM can query). Every other step follows established patterns.

No MCP server in the ecosystem has tried to automate away domain-specific data preparation. They all document it and leave it to the user.
