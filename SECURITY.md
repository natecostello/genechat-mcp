# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in GeneChat, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/natecostello/genechat-mcp/security/advisories/new)
3. Include steps to reproduce and any relevant details

You should receive a response within 72 hours.

## Data Privacy

GeneChat processes sensitive genomic data locally. While your VCF file never leaves your machine, tool responses (containing genotypes and clinical interpretations) are sent to your LLM provider as part of the conversation.

For platform-specific encryption guidance, see [docs/security.md](docs/security.md).
