# TARGET_FILE: "Options   v3.5.html" next to this script
"""
HTML Comment Stripper (auto-run edition)
-----------------------------------------
GUI mode is disabled (commented out below, kept for future use).
On execution, this script now runs directly against the fixed path
in TARGET_FILE above and writes "<name>_stripped.html" next to it,
with all documentation/explanation comments removed (HTML comments,
plus CSS/JS comments inside <style>/<script> blocks). Actual code,
markup, strings, regex literals and template literals are left
untouched so functionality is not affected.
"""

import os
import re
import shutil

# --- GUI imports (disabled - kept for future use) --------------------------
# import tkinter as tk
# from tkinter import filedialog, messagebox, scrolledtext


# ---------------------------------------------------------------------------
# CSS comment stripping
# ---------------------------------------------------------------------------

def strip_css_comments(code: str) -> str:
    out = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in ('"', "'"):
            quote = c
            start = i
            i += 1
            while i < n:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                i += 1
            out.append(code[start:i])
            continue
        if c == '/' and i + 1 < n and code[i + 1] == '*':
            j = code.find('*/', i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)


# ---------------------------------------------------------------------------
# JS comment stripping (string/template/regex aware)
# ---------------------------------------------------------------------------

_JS_REGEX_KEYWORDS = {
    'return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void',
    'throw', 'case', 'do', 'else', 'yield', 'await', 'default',
}
_JS_REGEX_PUNCT = set('([{,;:=!&|?+-*%^~<>\n')


def _regex_allowed(last_sig: str, last_word: str) -> bool:
    if last_sig == '':
        return True
    if last_word:
        return last_word in _JS_REGEX_KEYWORDS
    return last_sig in _JS_REGEX_PUNCT


def strip_js_comments(code: str) -> str:
    out = []
    i = 0
    n = len(code)
    last_sig = ''
    last_word = ''

    while i < n:
        c = code[i]

        # line comment
        if c == '/' and i + 1 < n and code[i + 1] == '/':
            j = code.find('\n', i)
            i = n if j == -1 else j
            continue

        # block comment
        if c == '/' and i + 1 < n and code[i + 1] == '*':
            j = code.find('*/', i + 2)
            i = n if j == -1 else j + 2
            continue

        # possible regex literal
        if c == '/' and _regex_allowed(last_sig, last_word):
            start = i
            i += 1
            in_class = False
            closed = False
            while i < n:
                cc = code[i]
                if cc == '\\':
                    i += 2
                    continue
                if cc == '[':
                    in_class = True
                elif cc == ']':
                    in_class = False
                elif cc == '/' and not in_class:
                    i += 1
                    closed = True
                    break
                elif cc == '\n':
                    break
                i += 1
            if closed:
                while i < n and code[i].isalpha():
                    i += 1
                out.append(code[start:i])
                last_sig = code[i - 1]
                last_word = ''
                continue
            else:
                # not actually a regex (unterminated) - treat '/' as division
                i = start

        # string literals
        if c in ('"', "'"):
            quote = c
            start = i
            i += 1
            while i < n:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                if code[i] == '\n':
                    break
                i += 1
            out.append(code[start:i])
            last_sig = quote
            last_word = ''
            continue

        # template literals (nested ${...} tracked shallowly)
        if c == '`':
            start = i
            i += 1
            depth = 0
            while i < n:
                cc = code[i]
                if cc == '\\':
                    i += 2
                    continue
                if cc == '`' and depth == 0:
                    i += 1
                    break
                if cc == '$' and i + 1 < n and code[i + 1] == '{':
                    depth += 1
                    i += 2
                    continue
                if cc == '}' and depth > 0:
                    depth -= 1
                    i += 1
                    continue
                i += 1
            out.append(code[start:i])
            last_sig = '`'
            last_word = ''
            continue

        # word run (identifiers / numbers / keywords)
        if c.isalnum() or c in ('_', '$'):
            start = i
            i += 1
            while i < n and (code[i].isalnum() or code[i] in ('_', '$')):
                i += 1
            word = code[start:i]
            out.append(word)
            last_word = word
            last_sig = word[-1]
            continue

        out.append(c)
        if not c.isspace():
            last_sig = c
        last_word = ''
        i += 1

    return ''.join(out)


# ---------------------------------------------------------------------------
# Document-level scanner: walks the raw HTML once, in order, handling
# <!-- --> comments and <script>/<style> blocks with correct precedence
# so a commented-out <script> block can't get corrupted.
# ---------------------------------------------------------------------------

_TYPE_ATTR_RE = re.compile(r'''type\s*=\s*(['"])(.*?)\1''', re.I)

_JS_TYPES = {
    '', 'text/javascript', 'application/javascript', 'application/ecmascript',
    'text/ecmascript', 'application/x-javascript', 'module',
}


def _is_js_script(open_tag_text: str) -> bool:
    m = _TYPE_ATTR_RE.search(open_tag_text)
    if not m:
        return True
    return m.group(2).strip().lower() in _JS_TYPES


def _find_tag_start(lower: str, i: int):
    """Find earliest '<script' or '<style' at/after i with a valid boundary."""
    def valid(idx, taglen):
        if idx == -1:
            return -1
        nc = lower[idx + taglen] if idx + taglen < len(lower) else '>'
        return idx if nc in (' ', '\t', '\n', '\r', '>', '/') else -1

    a = valid(lower.find('<script', i), 7)
    b = valid(lower.find('<style', i), 6)
    candidates = [(x, name) for x, name in ((a, 'script'), (b, 'style')) if x != -1]
    if not candidates:
        return -1, None
    return min(candidates, key=lambda t: t[0])


def strip_document(html_text: str) -> str:
    out = []
    i = 0
    n = len(html_text)
    lower = html_text.lower()

    while i < n:
        c_idx = lower.find('<!--', i)
        s_idx, tagname = _find_tag_start(lower, i)

        if c_idx == -1 and s_idx == -1:
            out.append(html_text[i:])
            break

        if s_idx == -1 or (c_idx != -1 and c_idx < s_idx):
            # next relevant token is an HTML comment
            out.append(html_text[i:c_idx])
            end = lower.find('-->', c_idx + 4)
            if end == -1:
                out.append(html_text[c_idx:])
                break
            content = html_text[c_idx + 4:end]
            stripped = content.strip()
            # preserve IE conditional comments untouched
            if stripped.startswith('[if') or stripped.startswith('[endif') or stripped.lower().endswith('endif]'):
                out.append(html_text[c_idx:end + 3])
            i = end + 3
            continue

        # next relevant token is a <script> or <style> block
        out.append(html_text[i:s_idx])
        gt = html_text.find('>', s_idx)
        if gt == -1:
            out.append(html_text[s_idx:])
            break
        open_tag = html_text[s_idx:gt + 1]

        # self-closing (e.g. <script src="x.js" />) - no body
        if open_tag.rstrip().endswith('/>'):
            out.append(open_tag)
            i = gt + 1
            continue

        close_needle = '</' + tagname
        close_idx = lower.find(close_needle, gt + 1)
        if close_idx == -1:
            out.append(html_text[s_idx:])
            break
        close_gt = html_text.find('>', close_idx)
        if close_gt == -1:
            out.append(html_text[s_idx:])
            break

        inner = html_text[gt + 1:close_idx]
        close_tag = html_text[close_idx:close_gt + 1]

        if tagname == 'style':
            new_inner = strip_css_comments(inner)
        else:
            new_inner = strip_js_comments(inner) if _is_js_script(open_tag) else inner

        out.append(open_tag + new_inner + close_tag)
        i = close_gt + 1

    return ''.join(out)


# ---------------------------------------------------------------------------
# Blank-line cleanup: comment stripping often leaves lines that are now
# empty (or whitespace-only) where a comment used to be. This collapses
# runs of blank lines down to a single blank line, and removes lines that
# are purely whitespace, WITHOUT touching any actual content lines, their
# indentation, or trailing content on non-blank lines. Safe because it
# never alters a line that contains anything other than whitespace.
# ---------------------------------------------------------------------------

_PRESERVE_TAGS_RE = re.compile(r'<(pre|textarea)\b[^>]*>.*?</\1\s*>', re.I | re.S)


def collapse_blank_lines(text: str) -> str:
    """Collapse runs of blank/whitespace-only lines to a single blank line.

    Content inside <pre>...</pre> and <textarea>...</textarea> is left
    completely untouched, since whitespace there is semantically
    significant. Everything else has consecutive blank lines squashed
    down to one, and whitespace-only lines normalized to empty. No line
    that contains any non-whitespace content is ever modified.
    """
    def _collapse_segment(segment: str) -> str:
        lines = segment.split('\n')
        out_lines = []
        prev_blank = False
        for line in lines:
            is_blank = (line.strip() == '')
            if is_blank:
                if prev_blank:
                    continue
                out_lines.append('')
                prev_blank = True
            else:
                out_lines.append(line)
                prev_blank = False
        return '\n'.join(out_lines)

    out = []
    pos = 0
    for m in _PRESERVE_TAGS_RE.finditer(text):
        out.append(_collapse_segment(text[pos:m.start()]))
        out.append(m.group(0))  # untouched
        pos = m.end()
    out.append(_collapse_segment(text[pos:]))
    return ''.join(out)



#
# class StripperApp:
#     def __init__(self, root):
#         self.root = root
#         root.title("HTML Comment Stripper")
#         root.resizable(True, False)
#
#         pad = {'padx': 10, 'pady': 6}
#
#         frame = tk.Frame(root)
#         frame.pack(fill='x', **pad)
#
#         tk.Label(frame, text="HTML file:").grid(row=0, column=0, sticky='w')
#
#         self.path_var = tk.StringVar()
#         self.path_entry = tk.Entry(frame, textvariable=self.path_var, width=60)
#         self.path_entry.grid(row=1, column=0, sticky='we', padx=(0, 6))
#         frame.columnconfigure(0, weight=1)
#
#         browse_btn = tk.Button(frame, text="Browse...", command=self.browse)
#         browse_btn.grid(row=1, column=1)
#
#         strip_btn = tk.Button(
#             root, text="Strip HTML", command=self.strip_file,
#             height=2, bg="#2d6cdf", fg="white", font=('Segoe UI', 10, 'bold')
#         )
#         strip_btn.pack(fill='x', padx=10, pady=(4, 8))
#
#         self.log = scrolledtext.ScrolledText(root, height=8, width=70, state='disabled')
#         self.log.pack(fill='both', expand=True, padx=10, pady=(0, 10))
#
#     def log_msg(self, msg: str):
#         self.log.configure(state='normal')
#         self.log.insert('end', msg + '\n')
#         self.log.see('end')
#         self.log.configure(state='disabled')
#
#     def browse(self):
#         path = filedialog.askopenfilename(
#             title="Select HTML file",
#             filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")]
#         )
#         if path:
#             self.path_var.set(path)
#
#     def strip_file(self):
#         path = self.path_var.get().strip()
#         if not path:
#             messagebox.showwarning("No file", "Please choose an HTML file first.")
#             return
#         if not os.path.isfile(path):
#             messagebox.showerror("Not found", f"File not found:\n{path}")
#             return
#
#         try:
#             with open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
#                 original = f.read()
#         except OSError as e:
#             messagebox.showerror("Read error", str(e))
#             return
#
#         try:
#             stripped = strip_document(original)
#         except Exception as e:
#             messagebox.showerror("Processing error", str(e))
#             return
#
#         folder, filename = os.path.split(path)
#         name, ext = os.path.splitext(filename)
#         out_path = os.path.join(folder, f"{name}_stripped{ext or '.html'}")
#
#         try:
#             with open(out_path, 'w', encoding='utf-8', errors='surrogateescape') as f:
#                 f.write(stripped)
#         except OSError as e:
#             messagebox.showerror("Write error", str(e))
#             return
#
#         removed = len(original) - len(stripped)
#         self.log_msg(f"Done: {out_path}")
#         self.log_msg(f"Removed {removed:,} characters of comments.")
#         messagebox.showinfo("Done", f"Stripped file saved to:\n{out_path}")


# ---------------------------------------------------------------------------
# Auto-run: strips the fixed TARGET_FILE with no GUI / no prompts
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGET_FILE = os.path.join(SCRIPT_DIR, "Options   v3.5.html")

# Second location that always receives an exact copy of the freshly
# stripped output (overwritten every run).
SECOND_COPY_TARGET = os.path.join(SCRIPT_DIR, "index.html")


def run_auto(path: str = TARGET_FILE) -> None:
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return

    with open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        original = f.read()

    stripped = strip_document(original)
    stripped = collapse_blank_lines(stripped)

    folder, filename = os.path.split(path)
    name, ext = os.path.splitext(filename)
    out_path = os.path.join(folder, f"{name}_stripped{ext or '.html'}")

    with open(out_path, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(stripped)

    removed = len(original) - len(stripped)
    print(f"Done: {out_path}")
    print(f"Removed {removed:,} characters of comments.")

    # Also place an exact copy of the stripped file at the fixed second
    # location (folder is created if it doesn't exist yet).
    try:
        second_dir = os.path.dirname(SECOND_COPY_TARGET)
        os.makedirs(second_dir, exist_ok=True)
        shutil.copyfile(out_path, SECOND_COPY_TARGET)
        print(f"Copied to: {SECOND_COPY_TARGET}")
    except OSError as e:
        print(f"Warning: could not copy to {SECOND_COPY_TARGET}: {e}")


def main():
    run_auto()
    # GUI mode disabled:
    # root = tk.Tk()
    # StripperApp(root)
    # root.mainloop()


if __name__ == '__main__':
    main()