# Verify required dev tools are on PATH (works with Nix or Homebrew).
# Sourced by .envrc — uses direnv builtins (has, log_error). Not standalone.
_missing=()
for _cmd in python3 uv ruff; do
    has "$_cmd" || _missing+=("$_cmd")
done
if [[ ${#_missing[@]} -gt 0 ]]; then
    log_error "Missing dev tools: ${_missing[*]}"
    log_error "Install via: brew install ${_missing[*]}"
    log_error "Or use Nix: direnv allow  (loads flake.nix)"
fi
unset _missing _cmd
