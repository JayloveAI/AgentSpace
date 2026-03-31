#!/usr/bin/env python3
"""
ClawHub OpenClaw Patch Injector
================================
Injects Three-Level Waterfall fallback strategy into OpenClaw's core files.

This script modifies OpenClaw's core files to add clawhub_request_data
as a fallback when web_search or browser tools encounter errors.

V1.6.3 - Three-Level Waterfall Strategy
"""

import os
import re
import sys
import shutil
import hashlib
from pathlib import Path


# Color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
CYAN = '\033[96m'


def log_info(msg):
    print(f"{CYAN}[INFO]{RESET} {msg}")


def log_success(msg):
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def log_warning(msg):
    print(f"{YELLOW}[WARNING]{RESET} {msg}")


def log_error(msg):
    print(f"{RED}[ERROR]{RESET} {msg}")


def find_openclaw_path():
    """Find OpenClaw installation path"""
    # Try multiple possible locations
    possible_paths = []

    # NPM global
    try:
        import subprocess
        result = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True)
        if result.returncode == 0:
            npm_global = result.stdout.strip()
            possible_paths.append(os.path.join(npm_global, 'openclaw'))
    except Exception:
        pass

    # User AppData
    if os.getenv('APPDATA'):
        possible_paths.append(os.path.join(os.getenv('APPDATA'), 'npm', 'node_modules', 'openclaw'))

    if os.getenv('USERPROFILE'):
        possible_paths.append(os.path.join(os.getenv('USERPROFILE'), 'AppData', 'Roaming', 'npm', 'node_modules', 'openclaw'))

    # Linux paths
    possible_paths.extend([
        '/usr/local/lib/node_modules/openclaw',
        '/usr/lib/node_modules/openclaw',
    ])

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def find_openclaw_core_files(openclaw_path):
    """Find core files to patch"""
    core_files = []

    # Main entry point
    if os.path.exists(os.path.join(openclaw_path, 'dist', 'index.js')):
        core_files.append(os.path.join(openclaw_path, 'dist', 'index.js'))

    # Alternative locations
    for pattern in ['src/index.ts', 'lib/index.js', 'openclaw.js']:
        if os.path.exists(os.path.join(openclaw_path, pattern)):
            core_files.append(os.path.join(openclaw_path, pattern))

    return core_files


def create_backup(file_path):
    """Create backup of original file"""
    backup_path = f"{file_path}.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        log_info(f"Backup created: {backup_path}")
    return backup_path


def inject_waterfall_patch(content):
    """
    Inject Three-Level Waterfall patch into OpenClaw content
    Compatible with both old and new OpenClaw versions.

    The patch adds clawhub_request_data as a fallback when:
    1. web_search returns 401/403/402/429
    2. browser encounters paywall/login wall
    """

    # Check if already patched
    if 'clawhub_request_data' in content and 'fallback' in content:
        log_warning("Already patched, skipping")
        return content, False

    modified = content

    # Pattern 1: New OpenClaw (2026.3.28+) — throw new Error directly
    new_version_pattern = r'throw new Error\(`Web fetch failed \(\$\{res\.status\}\): \$\{wrappedDetail\.text\}`\);'
    if re.search(new_version_pattern, content):
        modified = re.sub(
            new_version_pattern,
            '{const status = res.status;\n'
            '\t\t// --- [ClawHub] Level 1 Waterfall Injection ---\n'
            '\t\tif (status === 401 || status === 403 || status === 402 || status === 429) {\n'
            '\t\t\tif (typeof clawhub_request_data === \'function\') {\n'
            '\t\t\t\tclawhub_request_data({\n'
            '\t\t\t\t\ttype: \'web_search\',\n'
            '\t\t\t\t\tquery: typeof searchQuery !== \'undefined\' ? searchQuery : \'\',\n'
            '\t\t\t\t\terror: status,\n'
            '\t\t\t\t\tfallback: true\n'
            '\t\t\t\t}).catch(() => {});\n'
            '\t\t\t}\n'
            '\t\t}\n'
            '\t\tthrow new Error(`Web fetch failed (${status}): ${wrappedDetail.text}`);}',
            content
        )
        if modified != content:
            log_success("Level 1 waterfall injected (new OpenClaw version)")
            return modified, True

    # Pattern 2: Old OpenClaw — throwWebSearchApiError function (strict)
    old_strict_pattern = r'(async function throwWebSearchApiError\(res, providerLabel\) \{\s*const detail = \(await readResponseText\(res, \{ maxBytes: 64e3 \}\)\.text;)'
    old_patch = r'''\1
\tconst status = res.status;
\t// --- [ClawHub] Level 1 Waterfall Injection ---
\tif (status === 401 || status === 403 || status === 402 || status === 429) {
\t\tif (typeof clawhub_request_data === 'function') {
\t\t\tclawhub_request_data({
\t\t\t\ttype: 'web_search',
\t\t\t\tquery: typeof searchQuery !== 'undefined' ? searchQuery : '',
\t\t\t\terror: status,
\t\t\t\tfallback: true
\t\t\t}).catch(() => {});
\t\t}
\t}'''

    if re.search(old_strict_pattern, content):
        modified = re.sub(old_strict_pattern, old_patch, content)
        if modified != content:
            log_success("Level 1 waterfall injected (old OpenClaw, strict match)")
            return modified, True

    # Pattern 3: Old OpenClaw — throwWebSearchApiError function (loose)
    old_loose_pattern = r'(async function throwWebSearchApiError\(res, providerLabel\) \{[\s\S]*?const detail = .*?\.text;)'
    if re.search(old_loose_pattern, content):
        modified = re.sub(old_loose_pattern, old_patch, content)
        if modified != content:
            log_success("Level 1 waterfall injected (old OpenClaw, loose match)")
            return modified, True

    # Pattern 4: Browser error handling (.catch)
    browser_error_pattern = r'(\.catch\s*\(\s*\(\s*err\s*\)\s*=>\s*\{)'
    if re.search(browser_error_pattern, content):
        modified = re.sub(
            browser_error_pattern,
            r'\1\n'
            '\t\t// --- [ClawHub] Level 2 Waterfall Injection ---\n'
            '\t\tif (typeof clawhub_request_data === \'function\') {\n'
            '\t\t\tclawhub_request_data({\n'
            '\t\t\t\ttype: \'browser\',\n'
            '\t\t\t\tquery: typeof searchQuery !== \'undefined\' ? searchQuery : \'\',\n'
            '\t\t\t\terror: typeof err !== \'undefined\' ? String(err) : \'unknown\',\n'
            '\t\t\t\tfallback: true\n'
            '\t\t\t}).catch(() => {});\n'
            '\t\t}',
            content
        )
        if modified != content:
            log_success("Level 2 waterfall injected (browser error handler)")
            return modified, True

    # Pattern 5: Alternative — find webSearch function body
    alt_pattern = r'(function\s+webSearch\s*\([^)]*\)\s*\{)'
    if re.search(alt_pattern, content):
        modified = re.sub(
            alt_pattern,
            r'\1\n'
            '\t// --- [ClawHub] Waterfall Fallback ---\n'
            '\tif (typeof clawhub_request_data === \'function\') {\n'
            '\t\tclawhub_request_data({\n'
            '\t\t\ttype: \'web_search\',\n'
            '\t\t\tquery: typeof searchQuery !== \'undefined\' ? searchQuery : \'\',\n'
            '\t\t\terror: \'unknown\',\n'
            '\t\t\tfallback: true\n'
            '\t\t}).catch(() => {});\n'
            '\t}',
            content
        )
        if modified != content:
            log_success("Injected via alternative method (webSearch function)")
            return modified, True

    log_warning("Could not find any injection point")
    return content, False


def patch_file(file_path, dry_run=False):
    """Patch a single OpenClaw core file"""

    if not os.path.exists(file_path):
        log_error(f"File not found: {file_path}")
        return False

    log_info(f"Patching: {file_path}")

    # Create backup
    backup_path = create_backup(file_path)

    # Read content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject patch
    modified, success = inject_waterfall_patch(content)

    if not success:
        log_warning(f"No changes made to {file_path}")
        return False

    if dry_run:
        log_info("Dry run - not writing changes")
        return True

    # Write modified content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(modified)

    log_success(f"Patched: {file_path}")
    return True


def main():
    print("=" * 50)
    print("  ClawHub OpenClaw Patch Injector V1.6.3")
    print("=" * 50)
    print()

    # Find OpenClaw
    log_info("Searching for OpenClaw installation...")
    openclaw_path = find_openclaw_path()

    if not openclaw_path:
        log_error("OpenClaw not found!")
        log_info("Please ensure OpenClaw is installed:")
        log_info("  npm install -g openclaw")
        return 1

    log_success(f"Found OpenClaw at: {openclaw_path}")

    # Find core files
    core_files = find_openclaw_core_files(openclaw_path)

    if not core_files:
        log_error("Could not find core files to patch")
        log_info("OpenClaw structure may have changed")
        return 1

    log_info(f"Found {len(core_files)} core file(s)")

    # Patch each file
    patched = 0
    for core_file in core_files:
        if patch_file(core_file, dry_run=False):
            patched += 1

    print()
    print("=" * 50)

    if patched > 0:
        log_success(f"Successfully patched {patched} file(s)")
        print("=" * 50)
        return 0
    else:
        log_warning("No files were patched")
        log_info("This may be expected if already patched")
        print("=" * 50)
        return 0


if __name__ == '__main__':
    sys.exit(main())
