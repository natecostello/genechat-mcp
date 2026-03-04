#!/usr/bin/env bash
# Lint Claude Code skills for common invariant violations.
# Checks INV-1 (valid frontmatter), INV-2 (unique names), INV-3 (gitignore entries).
set -euo pipefail

SKILLS_DIR=".claude/skills"
GITIGNORE=".gitignore"
errors=0

# INV-1: Every SKILL.md must have valid YAML frontmatter with name + description
echo "=== INV-1: Checking frontmatter ==="
for skill_md in "$SKILLS_DIR"/*/SKILL.md; do
    dir=$(basename "$(dirname "$skill_md")")
    if ! head -1 "$skill_md" | grep -q '^---$'; then
        echo "  FAIL: $skill_md missing YAML frontmatter delimiter"
        errors=$((errors + 1))
        continue
    fi
    if ! grep -q '^name:' "$skill_md"; then
        echo "  FAIL: $skill_md missing 'name' field"
        errors=$((errors + 1))
    fi
    if ! grep -q '^description:' "$skill_md"; then
        echo "  FAIL: $skill_md missing 'description' field"
        errors=$((errors + 1))
    fi
done
echo "  Done."

# INV-2: Skill names must be unique
echo "=== INV-2: Checking name uniqueness ==="
dupes=$(grep -rh '^name: ' "$SKILLS_DIR"/*/SKILL.md | sort | uniq -d)
if [ -n "$dupes" ]; then
    echo "  FAIL: Duplicate skill names found:"
    echo "$dupes" | sed 's/^/    /'
    errors=$((errors + 1))
else
    echo "  Done. All names unique."
fi

# INV-3: Every tracked skill directory must have a negated gitignore entry
echo "=== INV-3: Checking .gitignore entries ==="
for skill_dir in "$SKILLS_DIR"/*/; do
    dir=$(basename "$skill_dir")
    [ -f "$skill_dir/SKILL.md" ] || continue
    pattern="!.claude/skills/${dir}/"
    if ! grep -qF "$pattern" "$GITIGNORE"; then
        echo "  FAIL: Missing gitignore entry for $dir (expected: $pattern)"
        errors=$((errors + 1))
    fi
done
echo "  Done."

# Summary
echo ""
if [ "$errors" -gt 0 ]; then
    echo "FAILED: $errors error(s) found."
    exit 1
else
    echo "PASSED: All skill invariants satisfied."
fi
