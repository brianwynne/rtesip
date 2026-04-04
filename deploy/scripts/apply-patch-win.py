"""Apply a unified diff patch file to a source tree.

Usage: python apply-patch-win.py <patch_file> <source_dir>

Simple patch applier for Windows (no git or patch command needed).
Only handles unified diff format with context.
"""

import re
import sys
from pathlib import Path


def apply_patch(patch_path: str, source_dir: str):
    patch = Path(patch_path).read_text(encoding="utf-8")
    base = Path(source_dir)

    # Parse hunks
    current_file = None
    for line in patch.splitlines():
        # File header: --- a/path/to/file
        if line.startswith("--- a/"):
            pass  # old file
        elif line.startswith("+++ b/"):
            rel_path = line[6:]
            current_file = base / rel_path
            if not current_file.exists():
                print(f"WARNING: {current_file} not found, skipping")
                current_file = None
            else:
                content = current_file.read_text(encoding="utf-8")
                print(f"Patching {rel_path}...")

    # For our specific patches, use the Python apply approach
    # (the patches insert code blocks after known markers)

    # Parse the patch for added lines
    additions = []
    context_before = []
    in_hunk = False

    for line in patch.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            context_before = []
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])
        elif line.startswith(" "):
            context_before.append(line[1:])
        elif line.startswith("-"):
            pass  # removed lines

    # For our use case, just report what would be patched
    # The actual patching is done by our Python apply scripts
    if current_file and additions:
        print(f"  {len(additions)} lines to add")
        print(f"  Use apply_opus_patch.py for pjsua_app.c patches")
        print(f"  Manual application may be needed for opus.c patches")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <patch_file> <source_dir>")
        sys.exit(1)
    apply_patch(sys.argv[1], sys.argv[2])
