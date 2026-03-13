# Security: Protecting Your Genomic Data

Genomic data is uniquely sensitive -- it is immutable, identifies you and your relatives, and can reveal health predispositions. This document covers data flow, LLM provider considerations, and platform-specific storage recommendations.

## Understanding the data flow

GeneChat's MCP server makes **zero network calls** during tool execution. It reads your raw VCF from disk and queries local SQLite databases. However, GeneChat is an MCP server — it returns tool responses to the MCP client (e.g. Claude Desktop), which forwards them to the LLM. Some CLI commands (`genechat status --check-updates`, `genechat annotate --stale`) do make network requests to check for newer reference databases — these are opt-in and clearly labeled.

**What stays local:**
- Your raw VCF file (never read by the LLM, never uploaded)
- Your patch.db and lookup databases
- Your config.toml (contains VCF paths)

**What is sent to the LLM provider (per tool call):**
- Genotypes (e.g. "rs4149056: TC, heterozygous")
- Clinical annotations (e.g. "Pathogenic — Hereditary breast cancer")
- Gene names, rsIDs, risk scores, drug interaction findings
- Any other content in tool responses

This means your specific genetic findings are processed by the LLM provider. The raw VCF (millions of variants) is never sent — only the specific variants returned by each tool call.

### Cloud LLMs (Claude, ChatGPT, Gemini, etc.)

When using a cloud-hosted LLM, tool responses are transmitted to the provider's servers. Review your provider's data retention and privacy policies:
- [Anthropic Privacy Policy](https://www.anthropic.com/privacy)
- [OpenAI Privacy Policy](https://openai.com/policies/privacy-policy)

### Local / self-hosted LLMs (Ollama, llama.cpp, vLLM, etc.)

For maximum privacy, use an MCP client configured to run a local/self-hosted model. With a local model, all data — including tool responses — stays on your machine. No genetic information is transmitted over the network.

Local options include:
- [Ollama](https://ollama.com/) with an MCP-compatible client
- Any local inference server paired with a client that supports the MCP protocol

## Store your VCF on an encrypted volume

Your VCF files (one per registered genome), patch databases, and `config.toml` (which contains VCF paths) should all live on an encrypted volume. If you have multiple genomes registered, the same encryption recommendations apply to all of them.

### macOS (APFS encrypted disk image)

```bash
# Create a 5 GB encrypted sparse image (grows as needed)
hdiutil create -size 5g -fs APFS -encryption AES-256 \
    -volname GenomeData -type SPARSE ~/GenomeData.sparseimage

# Mount it (prompts for password)
hdiutil attach ~/GenomeData.sparseimage

# Your VCF goes in /Volumes/GenomeData/
cp /path/to/raw.vcf.gz /Volumes/GenomeData/
cp /path/to/raw.vcf.gz.tbi /Volumes/GenomeData/

# Point config.toml at the mounted volume
# vcf_path = "/Volumes/GenomeData/raw.vcf.gz"

# Unmount when not in use
hdiutil detach /Volumes/GenomeData
```

### Linux (LUKS encrypted volume)

```bash
# Create and format an encrypted volume
dd if=/dev/zero of=~/genome_vault.img bs=1M count=5120
sudo cryptsetup luksFormat ~/genome_vault.img
sudo cryptsetup open ~/genome_vault.img genome_vault
sudo mkfs.ext4 /dev/mapper/genome_vault
sudo mkdir -p /mnt/genome_vault
sudo mount /dev/mapper/genome_vault /mnt/genome_vault
sudo chown "$(whoami)" /mnt/genome_vault

# Copy VCF and unmount when done
sudo umount /mnt/genome_vault
sudo cryptsetup close genome_vault
```

### External encrypted drive

For additional isolation, store your VCF on an external encrypted USB drive. Use the same encrypted volume approach above, but on the external drive. Update `vcf_path` in `config.toml` to point to the mount path.

## File permissions

Restrict access to your VCF and config file:

```bash
chmod 600 /path/to/raw.vcf.gz /path/to/raw.vcf.gz.tbi
chmod 600 /path/to/config.toml
```

`genechat init` sets `chmod 600` on the generated config file automatically.

## MCP client logs

MCP clients like Claude Desktop and Claude Code store conversation history locally. These logs will contain your genomic findings (genotypes, clinical interpretations, risk assessments). Be aware of:

- Where your client stores conversation logs
- Whether cloud sync (iCloud, Dropbox) is enabled on those directories
- Who has access to your machine
