"""
AutoCraft
=========
Web (Playwright codegen) test-code generator.

Dependencies:
    pip install playwright
    playwright install chromium

Run tests:
    python autocraft.py --test

Output:
    C:/autocraft/web/    Playwright pytest files
"""

import json
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

APP_NAME    = "AutoCraft"
APP_VERSION = "v5.0"

BASE_DIR     = "C:/autocraft"
WEB_DIR      = os.path.join(BASE_DIR, "web")
TEMP_CODEGEN = os.path.join(BASE_DIR, "_codegen_tmp.py")
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")

for _d in (BASE_DIR, WEB_DIR):
    os.makedirs(_d, exist_ok=True)

if os.path.exists(TEMP_CODEGEN):
    try:
        os.remove(TEMP_CODEGEN)
    except OSError:
        pass

# ── Palette ───────────────────────────────────────────────────────────────────
P = {
    "bg":        "#0f0f0f",
    "panel":     "#181818",
    "card":      "#1e1e1e",
    "input":     "#252525",
    "hover":     "#2a2a2a",
    "active":    "#303030",
    "border":    "#2d2d2d",
    "border2":   "#3a3a3a",
    "fg":        "#ebebeb",
    "fg2":       "#a8a8a8",
    "fg3":       "#626262",
    "blue":      "#2196f3",
    "blue_d":    "#1565c0",
    "green":     "#43a047",
    "green_d":   "#2e7d32",
    "orange":    "#fb8c00",
    "orange_d":  "#e65100",
    "teal":      "#00897b",
    "teal_d":    "#00695c",
    "red":       "#e53935",
    "red_d":     "#b71c1c",
    "ok":        "#4caf50",
    "warn":      "#ff9800",
    "err":       "#f44336",
    "info":      "#29b6f6",
    "web_bg":    "#071829",
    "web_bd":    "#1a3a5c",
    "ed_bg":     "#0d1117",
    "ln_bg":     "#090d12",
    "ln_fg":     "#3d444d",
    "s_kw":      "#ff7b72",
    "s_fn":      "#d2a8ff",
    "s_str":     "#a5d6ff",
    "s_cmt":     "#6e7681",
    "s_num":     "#79c0ff",
    "s_page":    "#56d364",
    "s_spec":    "#f0883e",
}

# ── Fonts (set after Tk root created) ─────────────────────────────────────────
UI_FONT    = None
LABEL_FONT = None
CODE_FONT  = None
SMALL_FONT = None

def _init_fonts():
    global UI_FONT, LABEL_FONT, CODE_FONT, SMALL_FONT
    UI_FONT    = ("Segoe UI", 10)
    LABEL_FONT = ("Segoe UI", 10, "bold")
    CODE_FONT  = ("Consolas", 10)
    SMALL_FONT = ("Segoe UI", 8)

# ── Validation ────────────────────────────────────────────────────────────────
TC_RE   = re.compile(r"^[A-Za-z0-9_]+$")
DESC_RE = re.compile(r"^[A-Za-z0-9_]+$")

# ══════════════════════════════════════════════════════════════════════════════
# Pure helpers  (zero UI, fully testable)
# ══════════════════════════════════════════════════════════════════════════════

def safe_url(url: str) -> str:
    url = url.strip()
    if url and not re.match(r"^https?://", url, re.I):
        return "https://" + url
    return url

def is_duplicate_tc(srs_file, fn_name: str) -> bool:
    if not srs_file or not os.path.exists(srs_file):
        return False
    with open(srs_file, encoding="utf-8") as f:
        return f"def {fn_name}(" in f.read()

def build_fn_name(srs: str, tc: str, tc_type: str, desc: str) -> str:
    return f"test_{srs}_{tc}_{tc_type}_{desc}"

def count_tcs(srs_file) -> int:
    if not srs_file or not os.path.exists(srs_file):
        return 0
    with open(srs_file, encoding="utf-8") as f:
        return sum(1 for ln in f if ln.startswith("def test_"))

def validate_fields(srs, tc, tc_type, desc) -> tuple:
    checks = [
        (not srs,                          "SRS ID cannot be empty"),
        (srs  and not TC_RE.match(srs),    "SRS ID: letters, digits, underscore only"),
        (not tc,                           "TC ID cannot be empty"),
        (tc   and not TC_RE.match(tc),     "TC ID: letters, digits, underscore only"),
        (not tc_type,                      "Select a Type"),
        (not desc,                         "Description cannot be empty"),
        (desc and not DESC_RE.match(desc), "Description: letters, digits, underscore only"),
        (desc and len(desc) > 20,          "Description max 20 characters"),
    ]
    for cond, msg in checks:
        if cond:
            return False, msg
    return True, ""

def write_web_fixture(path: str) -> None:
    fixture = (
        "import pytest\n"
        "from playwright.sync_api import sync_playwright, expect\n\n\n"
        "@pytest.fixture\ndef page():\n"
        "    with sync_playwright() as p:\n"
        "        browser = p.chromium.launch(headless=False)\n"
        "        page = browser.new_page()\n"
        "        yield page\n"
        "        browser.close()\n\n"
    )
    if not os.path.exists(path):
        open(path, "w", encoding="utf-8").write(fixture)
        return
    with open(path, encoding="utf-8") as f:
        c = f.read()
    if "def page()" not in c:
        open(path, "w", encoding="utf-8").write(fixture + c)

def append_test_fn(path: str, fn_name: str, steps: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n\ndef {fn_name}(page):\n")
        for line in steps.splitlines():
            if line.strip():
                f.write(f"    {line}\n")


def write_conftest(srs_dir: str,
                   screenshot: bool = False,
                   trace: bool = False,
                   storage_state: str = "") -> None:
    """
    Write/overwrite conftest.py in srs_dir.
    Called from tc_complete() whenever screenshot, trace, or
    storage_state is enabled.  Overwrites each time so the file
    always reflects the current option settings.

      screenshot    — pytest hook saves a PNG to screenshots/ on test failure
      trace         — tracing.start/stop wraps each test, zip saved to traces/
      storage_state — full path to a Playwright storage-state JSON file
                      (cookies + localStorage). Passed into new_context().
    """
    screenshots_dir = os.path.join(srs_dir, "screenshots")
    traces_dir      = os.path.join(srs_dir, "traces")

    L = []
    L += ["import os",
          "import pytest",
          "from playwright.sync_api import sync_playwright, expect",
          ""]

    if screenshot:
        L += [f'SCREENSHOT_DIR = r"{screenshots_dir}"',
              "os.makedirs(SCREENSHOT_DIR, exist_ok=True)",
              ""]
    if trace:
        L += [f'TRACE_DIR = r"{traces_dir}"',
              "os.makedirs(TRACE_DIR, exist_ok=True)",
              ""]

    L += ["",
          "@pytest.fixture",
          "def page(request):"]

    L += ["    with sync_playwright() as p:",
          "        browser = p.chromium.launch(headless=False)"]

    if storage_state:
        safe = storage_state.replace("\\", "/")
        L.append(f'        context = browser.new_context(storage_state=r"{safe}")')
    else:
        L.append("        context = browser.new_context()")

    if trace:
        L.append("        context.tracing.start("
                 "screenshots=True, snapshots=True, sources=True)")

    L += ["        page = context.new_page()",
          "        yield page"]

    if screenshot:
        L += ["        # Screenshot on failure",
              "        failed = (hasattr(request.node, 'rep_call')"
              " and request.node.rep_call.failed)",
              "        if failed:",
              "            safe_name = request.node.name.replace('/', '_')",
              "            page.screenshot("
              "path=os.path.join(SCREENSHOT_DIR, f'{safe_name}.png'))"]

    if trace:
        L += ["        # Save trace zip",
              "        safe_name = request.node.name.replace('/', '_')",
              "        context.tracing.stop("
              "path=os.path.join(TRACE_DIR, f'{safe_name}.zip'))"]

    L += ["        context.close()",
          "        browser.close()",
          ""]

    if screenshot:
        L += ["",
              "@pytest.hookimpl(tryfirst=True, hookwrapper=True)",
              "def pytest_runtest_makereport(item, call):",
              "    outcome = yield",
              "    rep = outcome.get_result()",
              "    setattr(item, 'rep_' + rep.when, rep)",
              ""]

    content = "\n".join(L) + "\n"
    dest = os.path.join(srs_dir, "conftest.py")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(content)

# ── Config ────────────────────────────────────────────────────────────────────

def load_cfg() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cfg(**kw) -> None:
    try:
        d = load_cfg()
        d.update(kw)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

def add_recent(path: str) -> None:
    d = load_cfg()
    r = d.get("recent", [])
    if path in r:
        r.remove(path)
    r.insert(0, path)
    d["recent"] = r[:8]
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

def get_recent() -> list:
    return [p for p in load_cfg().get("recent", []) if os.path.exists(p)]

# ══════════════════════════════════════════════════════════════════════════════
# UI helpers
# ══════════════════════════════════════════════════════════════════════════════

def _sep(parent, bg=None, height=1):
    return tk.Frame(parent, bg=bg or P["border"], height=height)

def _btn(parent, text, command, bg=None, fg="white",
         pad_x=14, pad_y=7, font=None, cursor="hand2", **kw):
    b = tk.Button(parent, text=text, command=command,
                  bg=bg or P["blue"],
                  fg=fg,
                  activebackground=_darken(bg or P["blue"]),
                  activeforeground=fg,
                  relief="flat", bd=0,
                  font=font or UI_FONT,
                  padx=pad_x, pady=pad_y,
                  cursor=cursor, **kw)
    def _e(_): b.config(bg=_darken(bg or P["blue"]))
    def _l(_): b.config(bg=bg or P["blue"])
    b.bind("<Enter>", _e)
    b.bind("<Leave>", _l)
    return b

def _darken(hex_col: str) -> str:
    try:
        r = max(0, int(hex_col[1:3], 16) - 30)
        g = max(0, int(hex_col[3:5], 16) - 30)
        b = max(0, int(hex_col[5:7], 16) - 30)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_col

def _card(parent, bg=None, bd_col=None):
    outer = tk.Frame(parent, bg=bd_col or P["border"], padx=1, pady=1)
    inner = tk.Frame(outer, bg=bg or P["card"])
    inner.pack(fill="both", expand=True)
    return outer, inner

def _step_row(parent, number: int, title: str, accent: str, bg=None):
    bg = bg or P["panel"]
    f  = tk.Frame(parent, bg=bg)
    tk.Label(f, text=str(number),
             bg=accent, fg="white",
             font=("Segoe UI", 8, "bold"),
             width=2, padx=4, pady=1,
             relief="flat").pack(side="left", padx=(0, 8))
    tk.Label(f, text=title,
             bg=bg, fg=P["fg2"],
             font=LABEL_FONT).pack(side="left")
    return f

def _entry(parent, **kw):
    return tk.Entry(parent,
                    bg=P["input"], fg=P["fg"],
                    insertbackground=P["fg"],
                    relief="flat", font=UI_FONT,
                    highlightthickness=1,
                    highlightbackground=P["border2"],
                    highlightcolor=P["blue"], **kw)

# ══════════════════════════════════════════════════════════════════════════════
# Toast
# ══════════════════════════════════════════════════════════════════════════════

class Toast:
    _COL = {"ok": P["ok"], "err": P["err"], "warn": P["warn"], "info": P["info"]}
    _ICO = {"ok": "✔", "err": "✖", "warn": "⚠", "info": "ℹ"}

    def __init__(self, parent):
        self._f = tk.Frame(parent, bg=P["card"], height=34)
        self._f.pack_propagate(False)
        self._lbl = tk.Label(self._f, text="", bg=P["card"],
                             fg=P["info"], font=("Segoe UI", 9, "bold"),
                             anchor="w", padx=12)
        self._lbl.pack(fill="both", expand=True)
        self._job = None

    @property
    def widget(self):
        return self._f

    def show(self, msg: str, kind: str = "info", ms: int = 6000):
        if self._job:
            try:
                self._lbl.after_cancel(self._job)
            except Exception:
                pass
        col = self._COL.get(kind, P["info"])
        ico = self._ICO.get(kind, "")
        self._lbl.config(text=f"{ico}  {msg}", fg=col)
        self._job = self._lbl.after(ms, lambda: self._lbl.config(text=""))

# ══════════════════════════════════════════════════════════════════════════════
# Code editor
# ══════════════════════════════════════════════════════════════════════════════

class CodeEditor(tk.Frame):
    """Full-height code editor: line numbers, syntax highlight, find bar."""

    _SYN = [
        (r"\b(def|import|from|with|for|yield|return|if|elif|else|"
         r"True|False|None|assert|class|try|except|finally|raise|"
         r"as|pass|break|continue|in|not|and|or|is|lambda|while|"
         r"async|await|global|nonlocal)\b",          "kw"),
        (r"\bpage\.[A-Za-z_]+\(",                    "page"),
        (r"\bexpect\(|\bfind\(",                     "spec"),
        (r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()",      "fn"),
        (r'"""[\s\S]*?"""',                          "str_"),
        (r"'''[\s\S]*?'''",                          "str_"),
        (r'"[^"\n]*"',                               "str_"),
        (r"'[^'\n]*'",                               "str_"),
        (r"#[^\n]*",                                 "cmt"),
        (r"\b\d+(?:\.\d+)?\b",                      "num"),
    ]
    _COLS = {
        "kw":   P["s_kw"],  "fn":   P["s_fn"],
        "str_": P["s_str"], "cmt":  P["s_cmt"],
        "num":  P["s_num"], "page": P["s_page"],
        "spec": P["s_spec"],
    }

    def __init__(self, parent, toast: Toast):
        super().__init__(parent, bg=P["panel"])
        self._toast = toast
        self._find_open = False
        self._build()

    def _build(self):
        # Toolbar
        tb = tk.Frame(self, bg=P["card"], height=38)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self._file_lbl = tk.Label(tb, text="  No active session",
                                  bg=P["card"], fg=P["fg3"],
                                  font=("Segoe UI", 9, "bold"), anchor="w")
        self._file_lbl.pack(side="left", padx=4)

        for txt, cmd in [("Save", self._save),
                         ("Clear", self._clear),
                         ("Copy", self._copy)]:
            tk.Button(tb, text=txt, bg=P["card"], fg=P["fg3"],
                      relief="flat", bd=0, font=SMALL_FONT,
                      padx=10, pady=4, cursor="hand2",
                      activebackground=P["hover"], activeforeground=P["fg"],
                      command=cmd).pack(side="right", pady=4, padx=2)

        _sep(self).pack(fill="x")

        # Find bar (hidden)
        self._find_bar = tk.Frame(self, bg=P["hover"])
        fb = tk.Frame(self._find_bar, bg=P["hover"])
        fb.pack(fill="x", padx=8, pady=4)
        tk.Label(fb, text="Find:", bg=P["hover"],
                 fg=P["fg2"], font=SMALL_FONT).pack(side="left", padx=(0, 4))
        self._find_var = tk.StringVar()
        self._find_var.trace_add("write", lambda *_: self._hl_all())
        fe = tk.Entry(fb, textvariable=self._find_var,
                      bg=P["input"], fg=P["fg"],
                      insertbackground=P["fg"],
                      relief="flat", font=UI_FONT, width=26,
                      highlightthickness=1,
                      highlightbackground=P["border2"])
        fe.pack(side="left")
        self._find_entry = fe
        fe.bind("<Return>", lambda _: self._find_next())
        fe.bind("<Escape>", lambda _: self.hide_find())
        for t, c in [("↓", self._find_next), ("↑", self._find_prev),
                     ("✕", self.hide_find)]:
            tk.Button(fb, text=t, bg=P["hover"], fg=P["fg2"],
                      relief="flat", bd=0, font=("Segoe UI", 9),
                      padx=6, cursor="hand2",
                      activebackground=P["active"],
                      command=c).pack(side="left", padx=2)
        self._find_count = tk.Label(fb, text="",
                                    bg=P["hover"], fg=P["fg3"],
                                    font=SMALL_FONT)
        self._find_count.pack(side="left", padx=6)

        # Editor area
        ea = tk.Frame(self, bg=P["ed_bg"])
        ea.pack(fill="both", expand=True)

        self._ln = tk.Text(ea, width=4, padx=6,
                           bg=P["ln_bg"], fg=P["ln_fg"],
                           font=CODE_FONT, state="disabled",
                           relief="flat", cursor="arrow",
                           selectbackground=P["ln_bg"], bd=0)
        self._ln.pack(side="left", fill="y")
        tk.Frame(ea, bg=P["border"], width=1).pack(side="left", fill="y")

        self.text = tk.Text(ea,
                            bg=P["ed_bg"], fg=P["fg"],
                            insertbackground=P["fg"],
                            font=CODE_FONT, relief="flat",
                            wrap="none", undo=True, maxundo=200,
                            selectbackground="#264f78",
                            selectforeground=P["fg"],
                            bd=0, spacing1=1, spacing3=1)
        self.text.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(ea, orient="vertical", command=self._vsync)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(ea, orient="horizontal", command=self.text.xview)
        hsb.pack(side="bottom", fill="x")

        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._ln.configure(yscrollcommand=vsb.set)

        for tag, col in self._COLS.items():
            self.text.tag_configure(tag, foreground=col)
        self.text.tag_configure("find_hl",  background="#3d3200", foreground="#ffff00")
        self.text.tag_configure("find_cur", background="#6d5000", foreground="#ffffff")
        self.text.tag_configure("cur_line", background="#1c2128")

        self.text.bind("<KeyRelease>",    self._on_change)
        self.text.bind("<ButtonRelease>", self._on_change)
        self.text.bind("<MouseWheel>",    self._on_change)

        # Status bar
        sb = tk.Frame(self, bg=P["card"], height=20)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._pos_lbl = tk.Label(sb, text="Ln 1, Col 1",
                                 bg=P["card"], fg=P["fg3"], font=SMALL_FONT)
        self._pos_lbl.pack(side="right", padx=10)
        self._lines_lbl = tk.Label(sb, text="0 lines",
                                   bg=P["card"], fg=P["fg3"], font=SMALL_FONT)
        self._lines_lbl.pack(side="right", padx=10)

        self._refresh_ln()

    # ── Public ────────────────────────────────────────────────────────────────

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set(self, content: str):
        self.text.delete("1.0", "end")
        if content:
            self.text.insert("1.0", content)
        self._post_change()

    def clear(self, confirm=False):
        if confirm and self.get():
            if not messagebox.askyesno("Clear", "Clear all code in the editor?"):
                return
        self.text.delete("1.0", "end")
        self._post_change()

    def load_file(self, path: str):
        with open(path, encoding="utf-8", errors="replace") as f:
            self.set(f.read())
        self.set_filename(os.path.basename(path))

    def set_filename(self, name: str):
        col = P["fg2"] if name else P["fg3"]
        self._file_lbl.config(text=f"  {name or 'No active session'}", fg=col)

    def show_find(self):
        if not self._find_open:
            self._find_bar.pack(fill="x", before=self.text.master)
            self._find_open = True
        self._find_entry.focus_set()
        try:
            sel = self.text.get("sel.first", "sel.last")
            if sel and "\n" not in sel:
                self._find_var.set(sel)
        except tk.TclError:
            pass

    def hide_find(self):
        self._find_bar.pack_forget()
        self._find_open = False
        self.text.tag_remove("find_hl",  "1.0", "end")
        self.text.tag_remove("find_cur", "1.0", "end")
        self._find_count.config(text="")
        self.text.focus_set()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _vsync(self, *args):
        self.text.yview(*args)
        self._ln.yview(*args)

    def _on_change(self, _=None):
        self._highlight()
        self._refresh_ln()
        self._update_pos()
        self._cur_line()

    def _post_change(self):
        self._highlight()
        self._refresh_ln()
        self._update_pos()

    def _refresh_ln(self):
        self._ln.config(state="normal")
        self._ln.delete("1.0", "end")
        n = int(self.text.index("end-1c").split(".")[0])
        self._ln.insert("1.0", "\n".join(str(i) for i in range(1, n + 1)))
        self._ln.config(state="disabled")
        self._lines_lbl.config(text=f"{n} line{'s' if n != 1 else ''}")

    def _update_pos(self):
        try:
            ln, col = self.text.index("insert").split(".")
            self._pos_lbl.config(text=f"Ln {ln}, Col {int(col)+1}")
        except Exception:
            pass

    def _cur_line(self):
        self.text.tag_remove("cur_line", "1.0", "end")
        try:
            ln = self.text.index("insert").split(".")[0]
            self.text.tag_add("cur_line", f"{ln}.0", f"{ln}.end+1c")
            self.text.tag_lower("cur_line")
        except Exception:
            pass

    def _highlight(self):
        for _, t in self._SYN:
            self.text.tag_remove(t, "1.0", "end")
        src = self.text.get("1.0", "end")
        for pat, tag in self._SYN:
            try:
                for m in re.finditer(pat, src, re.DOTALL):
                    self.text.tag_add(tag,
                                      f"1.0+{m.start()}c",
                                      f"1.0+{m.end()}c")
            except re.error:
                pass

    def _hl_all(self):
        self.text.tag_remove("find_hl",  "1.0", "end")
        self.text.tag_remove("find_cur", "1.0", "end")
        q = self._find_var.get()
        if not q:
            self._find_count.config(text="")
            return
        src = self.text.get("1.0", "end")
        ms  = list(re.finditer(re.escape(q), src, re.I))
        for m in ms:
            self.text.tag_add("find_hl",
                              f"1.0+{m.start()}c",
                              f"1.0+{m.end()}c")
        n = len(ms)
        self._find_count.config(text=f"{n} match{'es' if n != 1 else ''}")

    def _find_next(self):
        q = self._find_var.get()
        if not q: return
        src = self.text.get("1.0", "end")
        cur = len(self.text.get("1.0", self.text.index("insert")))
        ms  = list(re.finditer(re.escape(q), src, re.I))
        if not ms: return
        nxt = next((m for m in ms if m.start() > cur), ms[0])
        self.text.tag_remove("find_cur", "1.0", "end")
        self.text.tag_add("find_cur", f"1.0+{nxt.start()}c", f"1.0+{nxt.end()}c")
        self.text.mark_set("insert", f"1.0+{nxt.end()}c")
        self.text.see(f"1.0+{nxt.start()}c")

    def _find_prev(self):
        q = self._find_var.get()
        if not q: return
        src = self.text.get("1.0", "end")
        cur = len(self.text.get("1.0", self.text.index("insert")))
        ms  = list(re.finditer(re.escape(q), src, re.I))
        if not ms: return
        prv = next((m for m in reversed(ms) if m.end() < cur), ms[-1])
        self.text.tag_remove("find_cur", "1.0", "end")
        self.text.tag_add("find_cur", f"1.0+{prv.start()}c", f"1.0+{prv.end()}c")
        self.text.mark_set("insert", f"1.0+{prv.end()}c")
        self.text.see(f"1.0+{prv.start()}c")

    def _copy(self):
        c = self.get()
        if not c:
            self._toast.show("Nothing to copy", "warn"); return
        self.text.clipboard_clear()
        self.text.clipboard_append(c)
        self._toast.show("Copied to clipboard", "ok", ms=2500)

    def _clear(self):
        self.clear(confirm=True)

    def _save(self):
        c = self.get()
        if not c:
            self._toast.show("Nothing to save", "warn"); return
        p = filedialog.asksaveasfilename(
            title="Save generated code",
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All", "*.*")],
            initialdir=WEB_DIR)
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(c)
            add_recent(p)
            self._toast.show(f"Saved → {os.path.basename(p)}", "ok")

# ══════════════════════════════════════════════════════════════════════════════
# Recent Files panel
# ══════════════════════════════════════════════════════════════════════════════

class RecentPanel(tk.Frame):
    def __init__(self, parent, on_open):
        super().__init__(parent, bg=P["card"])
        self._on_open = on_open
        hdr = tk.Frame(self, bg=P["card"])
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(hdr, text="Recent Files", bg=P["card"],
                 fg=P["fg3"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(hdr, text="↺", bg=P["card"], fg=P["fg3"],
                  relief="flat", bd=0, cursor="hand2",
                  font=("Segoe UI", 9),
                  activebackground=P["hover"],
                  command=self.refresh).pack(side="right")
        self._list = tk.Frame(self, bg=P["card"])
        self._list.pack(fill="x", padx=4, pady=(0, 6))
        self.refresh()

    def refresh(self):
        for w in self._list.winfo_children():
            w.destroy()
        files = get_recent()
        if not files:
            tk.Label(self._list, text="  No recent files",
                     bg=P["card"], fg=P["fg3"],
                     font=SMALL_FONT).pack(anchor="w", pady=2)
            return
        for path in files[:6]:
            row = tk.Frame(self._list, bg=P["card"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text="●", bg=P["card"], fg=P["blue"],
                     font=("Segoe UI", 8), width=2).pack(side="left")
            tk.Button(row, text=os.path.basename(path),
                      bg=P["card"], fg=P["fg2"],
                      relief="flat", bd=0, font=SMALL_FONT,
                      padx=4, pady=2, anchor="w", cursor="hand2",
                      activebackground=P["hover"],
                      command=lambda p=path: self._on_open(p)
                      ).pack(side="left", fill="x", expand=True)

# ══════════════════════════════════════════════════════════════════════════════
# Web Panel
# ══════════════════════════════════════════════════════════════════════════════

class WebPanel:
    """Left panel — all web recording controls."""

    def __init__(self, container: tk.Frame, app: "AutoCraft"):
        self._app         = app
        self.frame        = tk.Frame(container, bg=P["panel"])
        self.srs_file     = None
        self.is_recording = False
        self._build()

    @property
    def editor(self) -> CodeEditor:
        return self._app.editor

    @property
    def toast(self) -> Toast:
        return self._app.toast

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        p   = self.frame
        acc = P["blue"]

        # Sticky control bar — always visible at top
        ctrl = tk.Frame(p, bg=P["card"])
        ctrl.pack(fill="x")
        tk.Frame(ctrl, bg=acc, height=2).pack(fill="x", side="bottom")

        inner = tk.Frame(ctrl, bg=P["card"])
        inner.pack(fill="x", padx=10, pady=8)

        self._btn_start = _btn(inner, "▶  Start Codegen",
                               self.start_codegen, bg=acc)
        self._btn_start.pack(side="left", padx=(0, 6))

        self._btn_stop = _btn(inner, "■  Stop",
                              self.stop_codegen, bg=P["active"], fg=P["fg2"])
        self._btn_stop.pack(side="left", padx=(0, 12))

        sf = tk.Frame(inner, bg=P["card"])
        sf.pack(side="left")
        self._status_dot = tk.Label(sf, text="●", bg=P["card"],
                                    fg=P["fg3"], font=("Segoe UI", 11))
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(sf, text="Idle",
                                    bg=P["card"], fg=P["fg3"],
                                    font=("Segoe UI", 9, "bold"))
        self._status_lbl.pack(side="left", padx=(3, 0))

        tk.Label(inner, text="Ctrl+Enter / Ctrl+W",
                 bg=P["card"], fg=P["fg3"],
                 font=SMALL_FONT).pack(side="right")

        _sep(p).pack(fill="x")

        # Scrollable content
        canvas = tk.Canvas(p, bg=P["panel"], highlightthickness=0)
        vsb    = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        sc = tk.Frame(canvas, bg=P["panel"])
        wid = canvas.create_window((0, 0), window=sc, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(wid, width=e.width))
        sc.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._build_content(sc)

    def _build_content(self, p):
        acc = P["blue"]

        def padded(w, py=(4, 0)):
            w.pack(fill="x", padx=14, pady=py)

        # STEP 1 — URL
        c1o, c1 = _card(p, bg=P["web_bg"], bd_col=P["web_bd"])
        padded(c1o, (12, 0))
        _step_row(c1, 1, "Target URL", acc, bg=P["web_bg"]).pack(
            anchor="w", padx=12, pady=(10, 6))

        url_row = tk.Frame(c1, bg=P["web_bg"])
        url_row.pack(fill="x", padx=12, pady=(0, 10))
        self._url_var = tk.StringVar()
        url_e = tk.Entry(url_row, textvariable=self._url_var,
                         bg=P["input"], fg=P["fg"],
                         insertbackground=P["fg"],
                         relief="flat", font=("Segoe UI", 11),
                         highlightthickness=1,
                         highlightbackground=P["web_bd"],
                         highlightcolor=acc)
        url_e.pack(fill="x", expand=True, ipady=5, )

        # STEP 2 — Test Identity
        c2o, c2 = _card(p)
        padded(c2o, (8, 0))
        _step_row(c2, 2, "Test Identity", acc).pack(
            anchor="w", padx=12, pady=(10, 6))
        self._build_identity(c2)

        # STEP 3 — Playwright Options
        c3o, c3 = _card(p)
        padded(c3o, (8, 0))
        _step_row(c3, 3, "Playwright Options  (optional)", acc).pack(
            anchor="w", padx=12, pady=(10, 6))
        self._build_pw_options(c3)

        # STEP 4 — Save
        c4o, c4 = _card(p)
        padded(c4o, (8, 0))
        _step_row(c4, 4, "Save Test Case", acc).pack(
            anchor="w", padx=12, pady=(10, 6))
        _btn(c4, "✔  TC Complete",
             self.tc_complete, bg=P["green"],
             pad_y=8).pack(fill="x", padx=14, pady=(0, 6))
        _btn(c4, "🔒  SRS Complete",
             self.srs_complete, bg=P["teal"],
             pad_y=6).pack(fill="x", padx=14, pady=(0, 12))

        tk.Frame(p, bg=P["panel"], height=10).pack()

    # ── Playwright Options ────────────────────────────────────────────────────

    def _build_pw_options(self, parent):
        bg = P["card"]

        def chk_row(var, label, hint):
            row = tk.Frame(parent, bg=bg)
            row.pack(fill="x", padx=14, pady=(4, 0))
            tk.Checkbutton(row, text=label, variable=var,
                           bg=bg, fg=P["fg2"], selectcolor=P["input"],
                           activebackground=bg, activeforeground=P["fg"],
                           font=UI_FONT).pack(side="left")
            tk.Label(row, text=hint, bg=bg, fg=P["fg3"],
                     font=SMALL_FONT).pack(side="left", padx=(6, 0))

        self._opt_screenshot = tk.BooleanVar(value=False)
        self._opt_trace      = tk.BooleanVar(value=False)
        self._opt_storage    = tk.BooleanVar(value=False)

        chk_row(self._opt_screenshot,
                "Screenshot on failure",
                "saves PNG per test  →  screenshots/")
        chk_row(self._opt_trace,
                "Capture trace",
                "saves .zip per test  →  traces/")

        # Storage state row + collapsible path field
        ss_row = tk.Frame(parent, bg=bg)
        ss_row.pack(fill="x", padx=14, pady=(4, 0))
        tk.Checkbutton(ss_row, text="Use storage state",
                       variable=self._opt_storage,
                       bg=bg, fg=P["fg2"], selectcolor=P["input"],
                       activebackground=bg, activeforeground=P["fg"],
                       font=UI_FONT,
                       command=self._toggle_storage).pack(side="left")
        tk.Label(ss_row, text="load cookies + localStorage from JSON",
                 bg=bg, fg=P["fg3"], font=SMALL_FONT).pack(side="left", padx=(6, 0))

        self._storage_path_frame = tk.Frame(parent, bg=bg)
        # ↑ packed/unpacked by _toggle_storage
        path_row = tk.Frame(self._storage_path_frame, bg=bg)
        path_row.pack(fill="x", padx=14, pady=(2, 0))
        tk.Label(path_row, text="Path:", bg=bg,
                 fg=P["fg3"], font=SMALL_FONT).pack(side="left", padx=(0, 6))
        self._storage_path_var = tk.StringVar()
        _entry(path_row, textvariable=self._storage_path_var,
               width=28).pack(side="left", fill="x", expand=True, ipady=3)
        tk.Button(path_row, text="Browse",
                  bg=P["active"], fg=P["fg2"], relief="flat", bd=0,
                  font=SMALL_FONT, padx=8, pady=3, cursor="hand2",
                  activebackground=P["hover"],
                  command=self._browse_storage).pack(side="left", padx=(6, 0))

        # Info note
        note_f = tk.Frame(parent, bg=P["input"])
        note_f.pack(fill="x", padx=14, pady=(8, 10))
        tk.Label(note_f,
                 text="  conftest.py is auto-created in the output folder"
                      " when any option is enabled.",
                 bg=P["input"], fg=P["fg3"], font=SMALL_FONT,
                 anchor="w", pady=5).pack(fill="x")

    def _toggle_storage(self):
        if self._opt_storage.get():
            self._storage_path_frame.pack(fill="x")
        else:
            self._storage_path_frame.pack_forget()
            self._storage_path_var.set("")

    def _browse_storage(self):
        p = filedialog.askopenfilename(
            title="Select storage state JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=WEB_DIR)
        if p:
            self._storage_path_var.set(p)

    def _pw_options(self) -> tuple:
        """Return (screenshot, trace, storage_path) from the option widgets."""
        ss = self._opt_screenshot.get()
        tr = self._opt_trace.get()
        sp = self._storage_path_var.get().strip() if self._opt_storage.get() else ""
        return ss, tr, sp

    # ── Identity fields ───────────────────────────────────────────────────────

    def _build_identity(self, parent):
        bg = P["panel"]

        # SRS ID
        tk.Label(parent, text="SRS ID *", bg=P["card"],
                 fg=P["fg2"], font=LABEL_FONT).pack(anchor="w", padx=14, pady=(8, 2))
        self._srs_var = tk.StringVar()
        self._srs_e   = _entry(parent, textvariable=self._srs_var)
        self._srs_e.pack(fill="x", padx=14, pady=(0, 2), ipady=4)
        self._srs_hint = tk.Label(parent, text="", bg=P["card"],
                                  fg=P["err"], font=SMALL_FONT, anchor="w")
        self._srs_hint.pack(anchor="w", padx=14)
        self._srs_var.trace_add("write", lambda *_: self._live_validate())

        # TC ID
        tk.Label(parent, text="TC ID *", bg=P["card"],
                 fg=P["fg2"], font=LABEL_FONT).pack(anchor="w", padx=14, pady=(6, 2))
        self._tc_var = tk.StringVar()
        self._tc_e   = _entry(parent, textvariable=self._tc_var)
        self._tc_e.pack(fill="x", padx=14, pady=(0, 2), ipady=4)
        self._tc_hint = tk.Label(parent, text="", bg=P["card"],
                                 fg=P["err"], font=SMALL_FONT, anchor="w")
        self._tc_hint.pack(anchor="w", padx=14)
        self._tc_var.trace_add("write", lambda *_: self._live_validate())

        # Type + Description row
        row = tk.Frame(parent, bg=P["card"])
        row.pack(fill="x", padx=14, pady=(6, 0))

        # Type
        tc_f = tk.Frame(row, bg=P["card"])
        tc_f.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(tc_f, text="Type *", bg=P["card"],
                 fg=P["fg2"], font=LABEL_FONT).pack(anchor="w", pady=(0, 2))
        self._type_var = tk.StringVar(value="UI")
        type_cb = ttk.Combobox(tc_f, textvariable=self._type_var,
                               values=["UI", "Backend", "Database"],
                               state="readonly", width=10, font=UI_FONT)
        type_cb.pack(fill="x", ipady=3)
        self._type_var.trace_add("write", lambda *_: self._live_validate())

        # Description
        dc_f = tk.Frame(row, bg=P["card"])
        dc_f.pack(side="left", fill="x", expand=True)
        dlf = tk.Frame(dc_f, bg=P["card"])
        dlf.pack(fill="x")
        tk.Label(dlf, text="Description *", bg=P["card"],
                 fg=P["fg2"], font=LABEL_FONT).pack(side="left", pady=(0, 2))
        self._desc_ctr = tk.Label(dlf, text="0/20",
                                  bg=P["card"], fg=P["fg3"], font=SMALL_FONT)
        self._desc_ctr.pack(side="right", pady=(0, 2))
        self._desc_var = tk.StringVar()
        self._desc_e   = _entry(dc_f, textvariable=self._desc_var)
        self._desc_e.pack(fill="x", ipady=4)
        self._desc_var.trace_add("write", lambda *_: self._on_desc())

        # fn preview
        fn_outer = tk.Frame(parent, bg=P["border"], padx=1, pady=1)
        fn_outer.pack(fill="x", padx=14, pady=(8, 4))
        fn_inner = tk.Frame(fn_outer, bg=P["card"])
        fn_inner.pack(fill="x", padx=8, pady=6)
        tk.Label(fn_inner, text="fn →", bg=P["card"],
                 fg=P["blue"], font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        self._fn_lbl = tk.Label(fn_inner, text="—",
                                bg=P["card"], fg=P["info"],
                                font=("Consolas", 9), anchor="w")
        self._fn_lbl.pack(side="left", fill="x", expand=True)

        # TC counter
        tc_cnt_f = tk.Frame(parent, bg=P["card"])
        tc_cnt_f.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(tc_cnt_f, text="TCs saved in file:",
                 bg=P["card"], fg=P["fg3"], font=SMALL_FONT).pack(side="left", padx=8)
        self._tc_count_lbl = tk.Label(tc_cnt_f, text="0",
                                      bg=P["card"], fg=P["blue"],
                                      font=("Segoe UI", 11, "bold"))
        self._tc_count_lbl.pack(side="left")

    # ── Live validation ───────────────────────────────────────────────────────

    def _on_desc(self):
        val = self._desc_var.get()
        if len(val) > 20:
            self._desc_var.set(val[:20])
            val = val[:20]
        if val and not DESC_RE.match(val):
            self._desc_var.set(val[:-1])
            val = val[:-1]
        n   = len(val)
        col = P["err"] if n >= 20 else P["warn"] if n >= 16 else P["fg3"]
        self._desc_ctr.config(text=f"{n}/20", fg=col)
        self._live_validate()

    def _live_validate(self):
        srs  = self._srs_var.get().strip()
        tc   = self._tc_var.get().strip()
        desc = self._desc_var.get().strip()
        tt   = self._type_var.get()

        # SRS border feedback
        if srs and not TC_RE.match(srs):
            self._srs_hint.config(text="letters, digits, _ only")
            self._srs_e.config(highlightbackground=P["err"])
        else:
            self._srs_hint.config(text="")
            self._srs_e.config(highlightbackground=P["ok"] if srs else P["border2"])

        # TC border feedback
        if tc and not TC_RE.match(tc):
            self._tc_hint.config(text="letters, digits, _ only")
            self._tc_e.config(highlightbackground=P["err"])
        else:
            self._tc_hint.config(text="")
            self._tc_e.config(highlightbackground=P["ok"] if tc else P["border2"])

        # fn preview
        if srs and tc and tt and desc:
            self._fn_lbl.config(text=build_fn_name(srs, tc, tt, desc),
                                fg=P["info"])
        else:
            missing = [n for n, v in
                       [("SRS", srs), ("TC", tc), ("Desc", desc)] if not v]
            self._fn_lbl.config(
                text="— fill: " + ", ".join(missing) if missing else "—",
                fg=P["fg3"])

    def _get_fields(self):
        return (self._srs_var.get().strip(),
                self._tc_var.get().strip(),
                self._type_var.get(),
                self._desc_var.get().strip())

    def _validate(self) -> bool:
        ok, msg = validate_fields(*self._get_fields())
        if not ok:
            self.toast.show(msg, "err")
        return ok

    def _current_fn(self) -> str:
        return build_fn_name(*self._get_fields())

    def _set_status(self, text: str, col: str):
        self._status_dot.config(fg=col)
        self._status_lbl.config(text=text, fg=col)

    # ── TC Complete ───────────────────────────────────────────────────────────

    def tc_complete(self):
        if self.is_recording:
            self.toast.show("Stop recording first", "warn"); return
        if not self.srs_file:
            self.toast.show("Start a recording session first", "err"); return
        code = self.editor.get().strip()
        if not code:
            self.toast.show("No recorded steps in editor", "err"); return
        if not self._validate(): return
        fn = self._current_fn()
        if is_duplicate_tc(self.srs_file, fn):
            self.toast.show(f"'{fn}' already exists — change TC ID or Desc",
                            "err"); return
        if not messagebox.askyesno("Confirm TC",
                                   f"Save test function?\n\n  {fn}(page)\n\n"
                                   "Yes → save   No → redo"):
            self.toast.show("TC redo — update steps and try again", "info"); return
        append_test_fn(self.srs_file, fn, self.editor.get())
        # Write/update conftest.py when any Playwright option is enabled
        ss, tr, sp = self._pw_options()
        if ss or tr or sp:
            write_conftest(WEB_DIR, screenshot=ss, trace=tr, storage_state=sp)
        add_recent(self.srs_file)
        self.editor.load_file(self.srs_file)
        self._tc_var.set("")
        self._desc_var.set("")
        self._desc_ctr.config(text="0/20", fg=P["fg3"])
        n = count_tcs(self.srs_file)
        self._tc_count_lbl.config(text=str(n))
        self._live_validate()
        self.toast.show(f"TC saved → {fn}  ({n} total)", "ok")

    # ── SRS Complete ──────────────────────────────────────────────────────────

    def srs_complete(self):
        if not self.srs_file:
            self.toast.show("No active SRS session", "warn"); return
        if self.is_recording:
            self.toast.show("Stop recording before completing SRS", "warn"); return
        fname = os.path.basename(self.srs_file)
        n     = count_tcs(self.srs_file)
        if not messagebox.askyesno("Complete SRS",
                                   f"Mark SRS complete?\n\nFile: {fname}\nTCs: {n}\n\n"
                                   "This resets all fields."):
            return
        for v in (self._srs_var, self._tc_var, self._desc_var):
            v.set("")
        self._type_var.set("UI")
        self.editor.clear()
        self.editor.set_filename("")
        self._tc_count_lbl.config(text="0")
        self.srs_file = None
        self._set_status("Idle", P["fg3"])
        self._live_validate()
        self.toast.show(f"SRS complete — {fname}", "ok")

    # ── Codegen ───────────────────────────────────────────────────────────────

    def start_codegen(self):
        if self.is_recording:
            self.toast.show("Already recording — click ■ Stop first", "warn"); return
        raw = self._url_var.get().strip()
        if not raw:
            self.toast.show("Enter a URL first (Step 1)", "err"); return
        url = safe_url(raw)
        if url != raw:
            self._url_var.set(url)
        if not self._validate(): return
        srs, tc, tt, desc = self._get_fields()
        pfile = os.path.join(WEB_DIR, f"{srs}.py")
        fn    = self._current_fn()
        if is_duplicate_tc(pfile, fn):
            self.toast.show(f"'{fn}' already exists — change TC ID or Desc",
                            "err", ms=8000); return
        self.srs_file = pfile
        write_web_fixture(self.srs_file)
        if os.path.exists(TEMP_CODEGEN):
            try: os.remove(TEMP_CODEGEN)
            except OSError: pass
        self.is_recording = True
        self.editor.clear()
        self.editor.set_filename(f"{srs}.py  [recording...]")
        self._set_status("Recording...", P["err"])
        self._btn_start.config(bg=P["red"], text="● Recording...")
        self._btn_stop.config(bg=P["orange"], fg="white")
        save_cfg(last_web_url=url, last_web_srs=srs)
        self.toast.show("Browser opened — interact then click ■ Stop",
                        "info", ms=20000)
        _, _, sp = self._pw_options()
        cmd = ["python", "-m", "playwright", "codegen",
               url, "--output", TEMP_CODEGEN]
        if sp and os.path.exists(sp):
            cmd += ["--load-storage", sp]
        subprocess.Popen(cmd, shell=True)

    def stop_codegen(self):
        if not self.is_recording:
            self.toast.show("No active recording", "warn"); return
        self.is_recording = False
        self._set_status("Idle", P["fg3"])
        self._btn_start.config(bg=P["blue"], text="▶  Start Codegen")
        self._btn_stop.config(bg=P["active"], fg=P["fg2"], text="■  Stop")
        if not os.path.exists(TEMP_CODEGEN):
            self.toast.show("No recording file found", "warn"); return
        if os.path.getsize(TEMP_CODEGEN) == 0:
            self.toast.show("Empty recording — no actions captured", "warn"); return
        steps = []
        with open(TEMP_CODEGEN, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s.startswith("page.") or s.startswith("expect("):
                    steps.append(s)
        if not steps:
            self.toast.show("No page.* / expect() steps found", "warn"); return
        self.editor.set("\n".join(steps))
        self.editor.set_filename(f"{self._srs_var.get()}.py  [review]")
        self.toast.show(
            f"{len(steps)} step(s) captured — review then ✔ TC Complete", "ok")

# ══════════════════════════════════════════════════════════════════════════════
# Main application window
# ══════════════════════════════════════════════════════════════════════════════

class AutoCraft(tk.Tk):

    def __init__(self):
        super().__init__()
        _init_fonts()
        self.title(f"{APP_NAME}  {APP_VERSION}")
        self.geometry("1440x880")
        self.minsize(960, 660)
        self.configure(bg=P["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TScrollbar",
                        background=P["border2"], troughcolor=P["panel"],
                        relief="flat", width=8)
        style.configure("TCombobox",
                        fieldbackground=P["input"],
                        background=P["input"],
                        foreground=P["fg"],
                        selectbackground=P["blue"],
                        selectforeground="white",
                        arrowcolor=P["fg3"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", P["input"])],
                  foreground=[("readonly", P["fg"])])
        self.option_add("*TCombobox*Listbox.background",       P["card"])
        self.option_add("*TCombobox*Listbox.foreground",       P["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", P["blue"])
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

        self._build()
        self._bind_shortcuts()
        self._restore_session()

    def _build(self):
        self._build_titlebar()
        self._build_body()
        self._build_footer()

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=P["panel"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=P["border"], height=1).pack(side="bottom", fill="x")
        tk.Frame(bar, bg=P["blue"], height=2).pack(side="bottom", fill="x")

        tk.Label(bar, text="⚡", bg=P["panel"],
                 fg=P["blue"], font=("Segoe UI", 16)).pack(side="left", padx=(16, 0))
        tk.Label(bar, text="AutoCraft", bg=P["panel"],
                 fg=P["fg"], font=("Segoe UI", 13, "bold")).pack(side="left", padx=(4, 2))
        tk.Label(bar, text=APP_VERSION, bg=P["panel"],
                 fg=P["fg3"], font=("Segoe UI", 8)).pack(side="left", padx=(0, 4),
                                                          anchor="s", pady=(0, 4))
        tk.Label(bar, text="Web Automation",
                 bg=P["panel"], fg=P["fg3"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 0), anchor="s",
                                             pady=(0, 5))

        tk.Label(bar,
                 text="Ctrl+Enter=Start  ·  Ctrl+W=Stop  ·  Ctrl+S=Save TC  ·  Ctrl+F=Find",
                 bg=P["panel"], fg=P["fg3"],
                 font=("Segoe UI", 8)).pack(side="right", padx=14)

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self):
        body = tk.Frame(self, bg=P["bg"])
        body.pack(fill="both", expand=True)

        # Left panel
        left = tk.Frame(body, bg=P["panel"], width=400)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(body, bg=P["border"], width=1).pack(side="left", fill="y")

        # Toast pinned at bottom
        self.toast = Toast(left)
        self.toast.widget.pack(side="bottom", fill="x")

        # Recent files above toast
        self._recent = RecentPanel(left, self._open_recent)
        self._recent.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        tk.Frame(left, bg=P["border"], height=1).pack(side="bottom", fill="x")

        # Panel
        self._panel_frame = tk.Frame(left, bg=P["panel"])
        self._panel_frame.pack(fill="both", expand=True)

        # Right: code editor
        right = tk.Frame(body, bg=P["bg"])
        right.pack(side="left", fill="both", expand=True)
        self.editor = CodeEditor(right, self.toast)
        self.editor.pack(fill="both", expand=True)

        # Build panel
        self.web_panel = WebPanel(self._panel_frame, self)
        self.web_panel.frame.pack(fill="both", expand=True)

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        foot = tk.Frame(self, bg="#0a0a0a", height=22)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        tk.Button(foot, text="📁 Open Output Folder",
                  bg="#0a0a0a", fg=P["fg3"],
                  relief="flat", bd=0, font=("Segoe UI", 8),
                  cursor="hand2", padx=8,
                  activebackground=P["panel"],
                  command=lambda: self._open_folder(WEB_DIR)
                  ).pack(side="left", pady=2)

        tk.Label(foot,
                 text=f"{APP_NAME} {APP_VERSION}   ·   Output: {WEB_DIR}",
                 bg="#0a0a0a", fg=P["fg3"],
                 font=("Segoe UI", 8)).pack(side="right", padx=12)

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind_all("<Control-Return>", lambda _: self.web_panel.start_codegen())
        self.bind_all("<Control-w>",      lambda _: self.web_panel.stop_codegen())
        self.bind_all("<Control-s>",      lambda _: self.web_panel.tc_complete())
        self.bind_all("<Control-f>",      lambda _: self.editor.show_find())
        self.bind_all("<Escape>",         lambda _: self.editor.hide_find())

    # ── Session ───────────────────────────────────────────────────────────────

    def _restore_session(self):
        url = load_cfg().get("last_web_url", "")
        if url:
            self.web_panel._url_var.set(url)

    def _open_recent(self, path: str):
        if not os.path.exists(path):
            self.toast.show(f"File not found: {path}", "err")
            self._recent.refresh()
            return
        self.web_panel.srs_file = path
        self.editor.load_file(path)
        self.web_panel._tc_count_lbl.config(text=str(count_tcs(path)))
        srs = os.path.splitext(os.path.basename(path))[0]
        self.web_panel._srs_var.set(srs)
        self.web_panel._live_validate()
        self.toast.show(f"Opened {os.path.basename(path)} — {count_tcs(path)} TC(s)",
                        "ok")

    def _open_folder(self, path: str):
        if os.path.exists(path):
            os.startfile(path)
        else:
            self.toast.show(f"Folder not found: {path}", "warn")

    def _on_close(self):
        if self.web_panel.is_recording:
            if not messagebox.askyesno("Recording active",
                                       "Recording is still running. Quit anyway?"):
                return
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
# Scenario tests   python autocraft.py --test
# ══════════════════════════════════════════════════════════════════════════════

def _run_tests():
    passed = failed = 0

    def ok(name):
        nonlocal passed; print(f"  \u2714  {name}"); passed += 1

    def fail(name, reason):
        nonlocal failed; print(f"  \u2716  {name}: {reason}"); failed += 1

    def check(name, cond, reason="assertion failed"):
        (ok if cond else lambda n: fail(n, reason))(name)

    print(f"\n{APP_NAME} {APP_VERSION} \u2014 Tests\n" + "\u2500" * 50)

    print("\n[safe_url]")
    check("bare domain",       safe_url("x.com")         == "https://x.com")
    check("https untouched",   safe_url("https://x.com") == "https://x.com")
    check("http untouched",    safe_url("http://local")   == "http://local")
    check("strips whitespace", safe_url("  x.com  ")     == "https://x.com")
    check("empty passthrough", safe_url("")              == "")
    check("subdomain ok",      safe_url("a.b.com")       == "https://a.b.com")

    print("\n[validate_fields]")
    V  = lambda s,t,tt,d: validate_fields(s,t,tt,d)[0]
    VM = lambda s,t,tt,d: validate_fields(s,t,tt,d)[1]
    check("valid",             V("S","T","UI","d"))
    check("empty SRS",         not V("","T","UI","d"))
    check("empty TC",          not V("S","","UI","d"))
    check("empty Desc",        not V("S","T","UI",""))
    check("space in SRS",      not V("S 1","T","UI","d"))
    check("hyphen in TC",      not V("S","T-1","UI","d"))
    check("space in Desc",     not V("S","T","UI","h s"))
    check("desc 20 ok",        V("S","T","UI","a"*20))
    check("desc 21 fail",      not V("S","T","UI","a"*21))
    check("underscore ok",     V("S","T","UI","lo_gin"))
    check("empty type fail",   not V("S","T","","d"))
    check("Database type ok",  V("S","T","Database","d"))
    check("SRS in error msg",  "SRS" in VM("","T","UI","d"))

    print("\n[build_fn_name]")
    check("standard",    build_fn_name("S","T","UI","d")       == "test_S_T_UI_d")
    check("backend",     build_fn_name("A","B","Backend","x")  == "test_A_B_Backend_x")
    check("database",    build_fn_name("A","B","Database","x") == "test_A_B_Database_x")
    check("underscores", build_fn_name("S_1","T_1","UI","f")   == "test_S_1_T_1_UI_f")

    print("\n[count_tcs]")
    import tempfile as _tf
    with _tf.NamedTemporaryFile(mode="w", suffix=".py",
                                delete=False, encoding="utf-8") as f:
        f.write("def test_A(page):\n    pass\ndef test_B(page):\n    pass\n")
        tmp = f.name
    try:
        check("counts 2",      count_tcs(tmp) == 2)
        check("none→0",        count_tcs(None) == 0)
        check("missing→0",     count_tcs("/no.py") == 0)
    finally:
        os.unlink(tmp)

    print("\n[is_duplicate_tc]")
    with _tf.NamedTemporaryFile(mode="w", suffix=".py",
                                delete=False, encoding="utf-8") as f:
        f.write("def test_A_B_UI_c(page):\n    pass\n")
        tmp = f.name
    try:
        check("match→True",    is_duplicate_tc(tmp, "test_A_B_UI_c"))
        check("no match→False",not is_duplicate_tc(tmp, "test_A_B_UI_d"))
        check("missing→False", not is_duplicate_tc("/no.py", "x"))
        check("None→False",    not is_duplicate_tc(None, "x"))
    finally:
        os.unlink(tmp)

    print("\n[write_web_fixture]")
    with _tf.NamedTemporaryFile(suffix=".py", delete=False) as f:
        tmp2 = f.name
    os.unlink(tmp2)
    try:
        write_web_fixture(tmp2)
        c = open(tmp2).read()
        check("file created",  os.path.exists(tmp2))
        check("pytest import", "import pytest" in c)
        check("playwright",    "playwright" in c)
        check("page fixture",  "def page()" in c)
        write_web_fixture(tmp2)
        check("no dup",        open(tmp2).read().count("def page()") == 1)
    finally:
        if os.path.exists(tmp2): os.unlink(tmp2)

    print("\n[append_test_fn]")
    with _tf.NamedTemporaryFile(mode="w", suffix=".py",
                                delete=False, encoding="utf-8") as f:
        f.write("# fixture\n")
        tmp3 = f.name
    try:
        append_test_fn(tmp3, "test_S_T_UI_d",
                       "page.click('#btn')\n\nexpect(page).to_have_url('/')")
        fc = open(tmp3).read()
        check("fn header",     "def test_S_T_UI_d(page):" in fc)
        check("indented",      "    page.click" in fc)
        check("blank skipped", "    expect" in fc)
        check("one def",       fc.count("def test_") == 1)
    finally:
        os.unlink(tmp3)

    print("\n[write_conftest]")
    import tempfile as _tfd
    with _tfd.TemporaryDirectory() as _td:
        # No options — minimal conftest, just fixture
        write_conftest(_td)
        _c = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("created",                  os.path.exists(os.path.join(_td, "conftest.py")))
        check("has page fixture",         "def page(" in _c)
        check("has sync_playwright",      "sync_playwright" in _c)
        check("no screenshot by default", "SCREENSHOT_DIR" not in _c)
        check("no trace by default",      "TRACE_DIR" not in _c)
        check("no storage by default",    "storage_state=" not in _c)

        # Screenshot=True
        write_conftest(_td, screenshot=True)
        _cs = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("ss: SCREENSHOT_DIR",       "SCREENSHOT_DIR" in _cs)
        check("ss: page.screenshot",      "page.screenshot" in _cs)
        check("ss: hook present",         "pytest_runtest_makereport" in _cs)
        check("ss: no trace artefact",    "TRACE_DIR" not in _cs)

        # Trace=True
        write_conftest(_td, trace=True)
        _ct = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("tr: TRACE_DIR",            "TRACE_DIR" in _ct)
        check("tr: tracing.start",        "tracing.start" in _ct)
        check("tr: tracing.stop",         "tracing.stop" in _ct)
        check("tr: no screenshot",        "SCREENSHOT_DIR" not in _ct)

        # storage_state
        write_conftest(_td, storage_state="/fake/auth.json")
        _cst = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("st: storage_state=",       "storage_state=" in _cst)
        check("st: path embedded",        "auth.json" in _cst)
        check("st: new_context used",     "new_context" in _cst)

        # All three together
        write_conftest(_td, screenshot=True, trace=True, storage_state="/fake/s.json")
        _call = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("all: screenshot",          "SCREENSHOT_DIR" in _call)
        check("all: trace",               "tracing.start" in _call)
        check("all: storage",             "storage_state=" in _call)

        # Overwrite — turn off screenshot, confirm it disappears
        write_conftest(_td, screenshot=False, trace=True)
        _cov = open(os.path.join(_td, "conftest.py"), encoding="utf-8").read()
        check("overwrite: no screenshot", "SCREENSHOT_DIR" not in _cov)
        check("overwrite: trace kept",    "TRACE_DIR" in _cov)

    print("\n[config]")
    _orig = CONFIG_FILE
    with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp4 = f.name
    os.unlink(tmp4)
    globals()["CONFIG_FILE"] = tmp4
    try:
        save_cfg(foo="bar", num=42)
        d = load_cfg()
        check("save/load",         d.get("foo") == "bar")
        check("numeric",           d.get("num") == 42)
        save_cfg(foo="updated")
        d2 = load_cfg()
        check("update preserves",  d2.get("num") == 42)
        check("update changes",    d2.get("foo") == "updated")
        add_recent("/fake/a.py"); add_recent("/fake/b.py")
        r = load_cfg().get("recent", [])
        check("recent tracked",    "/fake/b.py" in r)
        check("most recent first", r[0] == "/fake/b.py")
    finally:
        globals()["CONFIG_FILE"] = _orig
        if os.path.exists(tmp4): os.unlink(tmp4)

    total = passed + failed
    print(f"\n{'─'*50}")
    print(f"  {passed}/{total} passed",
          "  \u2714 All good!" if not failed else f"  \u2716 {failed} failed")
    return failed == 0

# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        sys.exit(0 if _run_tests() else 1)
    app = AutoCraft()
    app.mainloop()