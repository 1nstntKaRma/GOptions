#!/usr/bin/env python3
"""
update_client_id.py

Finds index.html in the current working directory and replaces the line:
    const GOOGLE_CLIENT_ID = 'X';
with:
    const GOOGLE_CLIENT_ID = '562729416343-3mb12lrlckvpf8h1l7hjpng5f770e9m8.apps.googleusercontent.com';

Runs automatically with no prompts. Exits with a non-zero status and a
clear message if the file is missing or the target line can't be found.
"""

import re
import sys
from pathlib import Path

TARGET_FILE = "index.html"
NEW_CLIENT_ID = "562729416343-3mb12lrlckvpf8h1l7hjpng5f770e9m8.apps.googleusercontent.com"

# Matches:  const GOOGLE_CLIENT_ID = '<anything except a quote>';
# - Works no matter what the current placeholder/value is (X, asdasd, a real ID, etc.)
# - Captures the surrounding pieces (whitespace, quote style, trailing semicolon)
#   so only the value inside the quotes is swapped; everything else is preserved
#   exactly as-is (indentation, quote char, spacing around '=').
DECL_PATTERN = re.compile(
    r"""(?P<prefix>const\s+GOOGLE_CLIENT_ID\s*=\s*(?P<quote>['"]))"""
    r"""(?P<value>[^'"]*)"""
    r"""(?P<suffix>(?P=quote)\s*;)"""
)


def _replace(match: "re.Match[str]") -> str:
    return f"{match.group('prefix')}{NEW_CLIENT_ID}{match.group('suffix')}"


def main() -> int:
    file_path = Path.cwd() / TARGET_FILE

    if not file_path.is_file():
        print(f"ERROR: '{TARGET_FILE}' not found in {Path.cwd()}", file=sys.stderr)
        return 1

    content = file_path.read_text(encoding="utf-8")

    new_content, count = DECL_PATTERN.subn(_replace, content)

    if count == 0:
        print(
            f"ERROR: No 'const GOOGLE_CLIENT_ID = \"...\";' declaration found in {file_path}. "
            "No changes made.",
            file=sys.stderr,
        )
        return 1

    if count > 1:
        print(
            f"WARNING: Found {count} occurrences of the GOOGLE_CLIENT_ID declaration; "
            "all were updated.",
            file=sys.stderr,
        )

    file_path.write_text(new_content, encoding="utf-8")
    print(f"Updated {count} occurrence(s) of GOOGLE_CLIENT_ID in {file_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())