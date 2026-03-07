# Security: Protecting Your Genomic Data

Genomic data is uniquely sensitive -- it is immutable, identifies you and your relatives, and can reveal health predispositions. This document covers platform-specific storage recommendations.

## Store your VCF on an encrypted volume

Your annotated VCF and `config.toml` (which contains the path to your VCF) should live on an encrypted volume.

### macOS (APFS encrypted disk image)

```bash
# Create a 5 GB encrypted sparse image (grows as needed)
hdiutil create -size 5g -fs APFS -encryption AES-256 \
    -volname GenomeData -type SPARSE ~/GenomeData.sparseimage

# Mount it (prompts for password)
hdiutil attach ~/GenomeData.sparseimage

# Your VCF goes in /Volumes/GenomeData/
cp /path/to/annotated.vcf.gz /Volumes/GenomeData/
cp /path/to/annotated.vcf.gz.tbi /Volumes/GenomeData/

# Point config.toml at the mounted volume
# vcf_path = "/Volumes/GenomeData/annotated.vcf.gz"

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

# Copy VCF and unmount when done
sudo umount /mnt/genome_vault
sudo cryptsetup close genome_vault
```

### External encrypted drive

For additional isolation, store your VCF on an external encrypted USB drive. Use the same encrypted volume approach above, but on the external drive. Update `vcf_path` in `config.toml` to point to the mount path.

## File permissions

Restrict access to your VCF and config file:

```bash
chmod 600 /path/to/annotated.vcf.gz /path/to/annotated.vcf.gz.tbi
chmod 600 /path/to/config.toml
```

`genechat init` sets `chmod 600` on the generated config file automatically.

## MCP client logs

MCP clients like Claude Desktop and Claude Code store conversation history locally. These logs will contain your genomic findings (genotypes, clinical interpretations, risk assessments). Be aware of:

- Where your client stores conversation logs
- Whether cloud sync (iCloud, Dropbox) is enabled on those directories
- Who has access to your machine
