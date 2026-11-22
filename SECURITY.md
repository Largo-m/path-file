# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in path_file, please report it responsibly:

1. **Do not** create a public issue
2. Use GitHub private vulnerability reporting:
   <https://github.com/Largo-m/path-file/security/advisories/new>
3. Include details about the vulnerability:
   - Description of the issue
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Considerations

path-file is designed with security in mind:

### Path Traversal Protection
- Archive extraction validates all paths stay within destination directory
- `safe_path()` utility prevents directory escape
- Symlink resolution is controlled

### Dry-Run by Default
- All destructive operations (delete, move, overwrite) require explicit confirmation
- `dry_run=True` is default for safety
- CLI requires `--confirm` flag for actual deletion

### Input Validation
- Size parsing validates format and ranges
- Duration parsing validates format
- Regex patterns are compiled with error handling
- TOML rules are parsed with validation

### No Code Execution
- No `eval()` or `exec()` anywhere in the codebase
- No dynamic code execution; the rules engine uses safe pattern matching only
- `run_command()` uses `subprocess` with an argument list (no shell involved)
- `run_shell()` is an explicit opt-in helper for users who *need* shell syntax
  (it passes `shell=True` by design and is documented accordingly); it is never
  used internally by path-file itself

### Permissions
- File operations respect OS permissions
- No privilege escalation
- Operations fail gracefully on permission errors

## Known Limitations

- Symlink cycles are detected but not automatically resolved on all platforms
- Windows recycle bin requires `send2trash` package (fallback provided)
- Very deep directory trees may hit recursion limits (iterative walker available)

## Dependencies

path-file has **zero runtime dependencies**. Only Python standard library is used.

Development dependencies are pinned and regularly updated for security.