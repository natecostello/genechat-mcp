# First-Run Setup

On first use in a fresh clone, initialize project memory:

1. Create `MEMORY.md` in the project root if it doesn't exist:
   ```markdown
   # Project Memory

   Specific facts, edge cases, and session-specific context that doesn't belong
   in CLAUDE.md (which covers general workflow and standards).
   ```
2. Configure Claude Code's auto-memory to redirect here. Write the following to the auto-memory file at `~/.claude/projects/*/memory/MEMORY.md` (the exact path depends on your project hash — check `~/.claude/projects/` for the directory matching this project):
   ```markdown
   # Auto Memory Redirect

   Do not store project memory here. All project memory belongs in the project root:

       /absolute/path/to/this/clone/MEMORY.md

   Use that file for specific facts, edge cases, and session context.
   General workflow and standards go in CLAUDE.md.
   ```

These files are gitignored. Each clone maintains its own memory.
