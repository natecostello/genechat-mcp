# First-Run Setup

On first use in a fresh clone, initialize project memory:

1. Create `MEMORY.md` in the project root if it doesn't exist:
   ```markdown
   # Project Memory

   Specific facts, edge cases, and session-specific context that doesn't belong
   in CLAUDE.md (which covers general workflow and standards).
   ```
2. Find your Claude Code auto-memory directory. The path includes a hash
   derived from your project's absolute path:
   ```bash
   ls ~/.claude/projects/
   # Look for the directory matching your clone path, e.g.:
   #   -Users-yourname-genechat-mcp
   ```
   Write the following to `~/.claude/projects/<your-dir>/memory/MEMORY.md`
   (create the `memory/` subdirectory if it doesn't exist):
   ```markdown
   # Auto Memory Redirect

   Do not store project memory here. All project memory belongs in the project root:

       /absolute/path/to/this/clone/MEMORY.md

   Use that file for specific facts, edge cases, and session context.
   General workflow and standards go in CLAUDE.md.
   ```

These files are gitignored. Each clone maintains its own memory.
