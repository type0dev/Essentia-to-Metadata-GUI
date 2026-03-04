#!/usr/bin/env python3
"""
Essentia Music Tagger GUI  v3  —  Linux Edition
Full GPU (CUDA) support via essentia-tensorflow.

Place in your Essentia-to-Metadata folder and run:
    python essentia_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import sys
import os
import queue
import re
import urllib.request

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#0e1117"
SURFACE  = "#161b27"
CARD     = "#1e2436"
BORDER   = "#2d3450"
ACCENT   = "#6c63ff"
ACCENT_H = "#9d97ff"
GREEN    = "#22d3a5"
RED      = "#ff5f72"
YELLOW   = "#f5c542"
PURPLE   = "#c084fc"
TEXT     = "#dce4f5"
SUBTEXT  = "#8892a4"
SEL_BG   = "#2d3a6b"
GPU_COL  = "#f97316"

FONT       = ("DejaVu Sans", 10)
FONT_B     = ("DejaVu Sans", 10, "bold")
FONT_SMALL = ("DejaVu Sans", 9)
FONT_TITLE = ("DejaVu Sans", 17, "bold")
MONO       = ("Monospace", 9)

AUDIO_EXTS = {".flac", ".mp3", ".ogg", ".opus", ".m4a", ".aac",
              ".wav", ".wv", ".ape"}

HERE       = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR  = os.path.join(HERE, "models")
LOGS_DIR    = os.path.join(HERE, "logs")
TAGGER_LOGS = os.path.join(LOGS_DIR, "tagger")
GUI_LOGS    = os.path.join(LOGS_DIR, "gui")

REQUIRED_MODELS = [
    {
        "filename": "discogs-effnet-bs64-1.pb",
        "url": "https://essentia.upf.edu/models/music-style-classification/discogs-effnet/discogs-effnet-bs64-1.pb",
        "desc": "Embedding model  (Discogs EffNet, ~18 MB)",
    },
    {
        "filename": "genre_discogs400-discogs-effnet-1.pb",
        "url": "https://essentia.upf.edu/models/classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.pb",
        "desc": "Genre classifier  (Discogs 400, ~1 MB)",
    },
    {
        "filename": "genre_discogs400-discogs-effnet-1.json",
        "url": "https://essentia.upf.edu/models/classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.json",
        "desc": "Genre classifier metadata  (<1 MB)",
    },
    {
        "filename": "mtg_jamendo_moodtheme-discogs-effnet-1.pb",
        "url": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.pb",
        "desc": "Mood classifier  (MTG-Jamendo, ~3 MB)",
    },
    {
        "filename": "mtg_jamendo_moodtheme-discogs-effnet-1.json",
        "url": "https://essentia.upf.edu/models/classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1.json",
        "desc": "Mood classifier metadata  (<1 MB)",
    },
]


# ── Native dialog helpers ─────────────────────────────────────────────────────
def _has_cmd(cmd):
    try:
        subprocess.check_output(["which", cmd], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def ask_directory(title="Choose Folder", initialdir=None):
    """Try kdialog → zenity → Tk fallback."""
    start = initialdir or os.path.expanduser("~")
    if _has_cmd("kdialog"):
        try:
            out = subprocess.check_output(
                ["kdialog", "--getexistingdirectory", start, "--title", title],
                text=True).strip()
            return out if out and os.path.isdir(out) else None
        except Exception:
            pass
    if _has_cmd("zenity"):
        try:
            out = subprocess.check_output(
                ["zenity", "--file-selection", "--directory",
                 "--title", title, f"--filename={start}/"],
                text=True).strip()
            return out if out and os.path.isdir(out) else None
        except Exception:
            pass
    # Tk fallback
    from tkinter import filedialog as _fd
    return _fd.askdirectory(title=title, initialdir=start, mustexist=True) or None

def ask_openfile(title="Choose File", initialdir=None, filetypes=None):
    """Try kdialog → zenity → Tk fallback."""
    start = initialdir or os.path.expanduser("~")
    if _has_cmd("kdialog"):
        try:
            out = subprocess.check_output(
                ["kdialog", "--getopenfilename", start, "--title", title],
                text=True).strip()
            return out if out and os.path.isfile(out) else None
        except Exception:
            pass
    if _has_cmd("zenity"):
        try:
            cmd = ["zenity", "--file-selection", "--title", title,
                   f"--filename={start}/"]
            if filetypes:
                # zenity uses simple glob patterns
                patterns = []
                for label, exts in filetypes:
                    patterns += exts.split()
                if patterns:
                    cmd += ["--file-filter", " ".join(patterns)]
            out = subprocess.check_output(cmd, text=True).strip()
            return out if out and os.path.isfile(out) else None
        except Exception:
            pass
    # Tk fallback
    from tkinter import filedialog as _fd
    return _fd.askopenfilename(
        title=title, initialdir=start,
        filetypes=filetypes or [("All", "*.*")]) or None


# ── Helpers ────────────────────────────────────────────────────────────────────
def find_script():
    p = os.path.join(HERE, "tag_music.py")
    return p if os.path.isfile(p) else ""


def is_audio(name):
    return os.path.splitext(name)[1].lower() in AUDIO_EXTS


# Friendly ID3 frame name mapping
_ID3_NAMES = {
    "TIT2": "title",    "TPE1": "artist",    "TPE2": "albumartist",
    "TALB": "album",    "TDRC": "date",      "TRCK": "tracknumber",
    "TPOS": "discnumber","TCON": "genre",     "TMOO": "mood",
    "TBPM": "bpm",      "TKEY": "key",       "TCOM": "composer",
    "TLAN": "language", "TPUB": "publisher", "TCOP": "copyright",
    "TSRC": "isrc",     "TMED": "media",     "TDOR": "originaldate",
    "TOWN": "owner",    "TOPE": "origartist","TSST": "subtitle",
}

def read_tags(filepath):
    if not HAS_MUTAGEN:
        return {}
    try:
        # Try easy=True first for clean key names
        f = MutagenFile(filepath, easy=True)
        if f is None:
            return {}
        out = {}
        if f.tags:
            for k, v in f.tags.items():
                out[k] = [str(x) for x in v] if isinstance(v, list) else [str(v)]

        # Also read raw tags to catch MOOD/TMOO and COMM frames
        f2 = MutagenFile(filepath, easy=False)
        if f2 and f2.tags:
            for k, v in f2.tags.items():
                # Map ID3 frame codes to friendly names
                friendly = _ID3_NAMES.get(k, None)
                # Handle COMM:desc frames
                if k.startswith("COMM:Essentia"):
                    friendly = k.replace("COMM:", "").replace("EssentiaGenre", "essentia_genre").replace("EssentiaMood", "essentia_mood")
                elif k.startswith("COMM:"):
                    friendly = "comment"
                elif k.startswith("APIC"):
                    continue  # skip album art
                elif k.startswith("TXXX:"):
                    friendly = k[5:].lower()
                if friendly and friendly not in out:
                    if hasattr(v, "text"):
                        out[friendly] = [str(x) for x in v.text]
                    elif hasattr(v, "strings"):
                        out[friendly] = list(v.strings)
                    elif isinstance(v, list):
                        out[friendly] = [str(x) for x in v]
                    else:
                        out[friendly] = [str(v)]
        return out
    except Exception:
        return {}


def models_present():
    return [m["filename"] for m in REQUIRED_MODELS
            if not os.path.isfile(os.path.join(MODELS_DIR, m["filename"]))]


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def detect_gpus():
    """Return list of (index, name) for available NVIDIA GPUs."""
    # Try nvidia-smi first — fastest, no TF import needed
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,name",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, text=True, timeout=5)
        gpus = []
        for line in out.strip().splitlines():
            parts = line.split(",", 1)
            if len(parts) == 2:
                gpus.append((parts[0].strip(), parts[1].strip()))
        if gpus:
            return gpus
    except Exception:
        pass
    # Fallback: TensorFlow
    try:
        import tensorflow as tf
        devs = tf.config.list_physical_devices("GPU")
        return [(str(i), d.name) for i, d in enumerate(devs)]
    except Exception:
        pass
    return []


# ── Styled widgets ─────────────────────────────────────────────────────────────
class FlatBtn(tk.Button):
    def __init__(self, master, text="", command=None,
                 color=ACCENT, fg=TEXT, hover=ACCENT_H, **kw):
        kw.setdefault("padx", 14)
        kw.setdefault("pady", 6)
        super().__init__(master, text=text, command=command,
                         bg=color, fg=fg, activebackground=hover,
                         activeforeground=fg, relief="flat", bd=0,
                         cursor="hand2", font=FONT_B, **kw)
        self._n, self._h = color, hover
        self.bind("<Enter>", lambda _: self.config(bg=self._h))
        self.bind("<Leave>", lambda _: self.config(bg=self._n))


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tw = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tw, text=self.text, bg="#1a1f2e", fg=TEXT,
                 font=FONT_SMALL, padx=8, pady=4, relief="flat", bd=1).pack()

    def hide(self, _=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None


class StyledList(tk.Frame):
    def __init__(self, master, title="", **kw):
        super().__init__(master, bg=CARD, **kw)

        hdr = tk.Frame(self, bg=BORDER, pady=5)
        hdr.pack(fill="x")
        self._title_lbl = tk.Label(hdr, text=title, bg=BORDER, fg=ACCENT_H,
                 font=FONT_B, padx=8)
        self._title_lbl.pack(side="left")
        self.count_lbl = tk.Label(hdr, text="", bg=BORDER,
                                  fg=SUBTEXT, font=FONT_SMALL, padx=6)
        self.count_lbl.pack(side="right")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filter)
        tk.Entry(self, textvariable=self.search_var,
                 bg=SURFACE, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", font=FONT_SMALL,
                 highlightthickness=1,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(fill="x", padx=4, pady=4)

        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self.lb = tk.Listbox(inner, bg=CARD, fg=TEXT,
                             selectbackground=SEL_BG,
                             selectforeground=ACCENT_H,
                             activestyle="none", relief="flat",
                             bd=0, highlightthickness=0,
                             font=FONT, exportselection=False)
        sb = tk.Scrollbar(inner, command=self.lb.yview,
                          bg=CARD, troughcolor=BG,
                          activebackground=ACCENT, relief="flat")
        self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._all = []

    def set_items(self, items):
        self._all = list(items)
        self._render(self._all)

    def _render(self, items):
        sel = self.get_selected()
        self.lb.delete(0, "end")
        for it in items:
            self.lb.insert("end", it)
        self.count_lbl.config(text=str(len(items)))
        if sel and sel in items:
            idx = items.index(sel)
            self.lb.selection_set(idx)
            self.lb.see(idx)

    def _filter(self, *_):
        q = self.search_var.get().lower()
        self._render([i for i in self._all if q in i.lower()] if q else self._all)

    def set_title(self, title):
        self._title_lbl.config(text=title)

    def clear(self):
        self._all = []
        self.lb.delete(0, "end")
        self.count_lbl.config(text="")
        self.search_var.set("")

    def get_selected(self):
        s = self.lb.curselection()
        return self.lb.get(s[0]) if s else None

    def bind_select(self, fn):
        self.lb.bind("<<ListboxSelect>>", fn)


class TagPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=CARD, **kw)

        hdr = tk.Frame(self, bg=BORDER, pady=5)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🏷  Tags", bg=BORDER,
                 fg=ACCENT_H, font=FONT_B, padx=8).pack(side="left")
        self.file_lbl = tk.Label(hdr, text="", bg=BORDER,
                                 fg=SUBTEXT, font=FONT_SMALL, padx=6)
        self.file_lbl.pack(side="right")

        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        style = ttk.Style()
        style.configure("Tag.Treeview",
                        background=CARD, foreground=TEXT,
                        fieldbackground=CARD, rowheight=23,
                        font=FONT_SMALL, borderwidth=0)
        style.configure("Tag.Treeview.Heading",
                        background=BORDER, foreground=SUBTEXT,
                        font=FONT_B, relief="flat")
        style.map("Tag.Treeview",
                  background=[("selected", SEL_BG)],
                  foreground=[("selected", ACCENT_H)])

        self.tree = ttk.Treeview(inner, columns=("val",),
                                 show="tree headings",
                                 style="Tag.Treeview",
                                 selectmode="browse")
        self.tree.heading("#0",  text="Tag",   anchor="w")
        self.tree.heading("val", text="Value", anchor="w")
        self.tree.column("#0",  width=130, minwidth=80, stretch=False)
        self.tree.column("val", width=400, minwidth=200, stretch=True)

        tsb = tk.Scrollbar(inner, command=self.tree.yview,
                           bg=CARD, troughcolor=BG,
                           activebackground=ACCENT, relief="flat")
        self.tree.config(yscrollcommand=tsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")

        self.tree.tag_configure("genre", foreground=PURPLE)
        self.tree.tag_configure("mood",  foreground=PURPLE)
        self.tree.tag_configure("basic", foreground=TEXT)
        self.tree.tag_configure("other", foreground=SUBTEXT)

        if not HAS_MUTAGEN:
            tk.Label(self, text="⚠  pip install mutagen  to read tags",
                     bg=CARD, fg=YELLOW, font=FONT_SMALL,
                     padx=8, pady=4).pack(anchor="nw")

    def load(self, filepath):
        self.tree.delete(*self.tree.get_children())
        if not filepath:
            self.file_lbl.config(text="")
            return
        self.file_lbl.config(text=os.path.basename(filepath))
        tags = read_tags(filepath)
        if not tags:
            self.tree.insert("", "end", text="(no tags)", values=("",))
            return
        priority = ["title", "artist", "albumartist", "album",
                    "date", "tracknumber", "discnumber",
                    "genre", "GENRE", "mood", "MOOD",
                    "ESSENTIA_GENRE", "ESSENTIA_MOOD"]
        # Build a case-insensitive lookup
        tags_lower = {k.lower(): k for k in tags}
        shown = set()
        for p in priority:
            actual = tags.get(p) or tags.get(tags_lower.get(p.lower(), ""))
            if actual is not None:
                real_key = p if p in tags else tags_lower.get(p.lower(), p)
                if real_key not in shown:
                    self._row(real_key, actual)
                    shown.add(real_key)
        for k, v in sorted(tags.items()):
            if k not in shown:
                self._row(k, v)

    def _row(self, key, values):
        kl = key.lower()
        if "genre" in kl:  rt = "genre"
        elif "mood" in kl: rt = "mood"
        elif kl in ("title", "artist", "album", "date",
                    "tracknumber", "albumartist", "discnumber"):
            rt = "basic"
        else:
            rt = "other"
        self.tree.insert("", "end", text=key,
                         values=(" | ".join(values),), tags=(rt,))

    def clear(self, msg=""):
        self.tree.delete(*self.tree.get_children())
        self.file_lbl.config(text=msg)


# ══════════════════════════════════════════════════════════════════════════════
#  Model Download Dialog
# ══════════════════════════════════════════════════════════════════════════════
class ModelDownloadDialog(tk.Toplevel):
    def __init__(self, master, missing):
        super().__init__(master)
        self.title("Download ML Models")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._cancelled = False
        self._done      = False
        self._q         = queue.Queue()
        self._missing   = missing

        pad = dict(padx=24, pady=10)
        tk.Label(self, text="🎵  ML Models Required",
                 bg=BG, fg=ACCENT, font=FONT_TITLE, **pad).pack(anchor="w")
        tk.Label(self,
                 text=("The following model files are missing from models/\n"
                       "and are required for genre & mood analysis (~22 MB total)."),
                 bg=BG, fg=TEXT, font=FONT, justify="left", **pad
                 ).pack(anchor="w")

        fbox = tk.Frame(self, bg=CARD, padx=14, pady=10)
        fbox.pack(fill="x", padx=24, pady=(0, 6))
        for fn in missing:
            row = next((m for m in REQUIRED_MODELS if m["filename"] == fn), None)
            desc = row["desc"] if row else fn
            tk.Label(fbox, text=f"  •  {fn}",
                     bg=CARD, fg=ACCENT_H, font=FONT_SMALL).pack(anchor="w")
            tk.Label(fbox, text=f"     {desc}",
                     bg=CARD, fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")

        self._bars = {}
        pb_frame = tk.Frame(self, bg=BG)
        pb_frame.pack(fill="x", padx=24, pady=(4, 0))

        for m in REQUIRED_MODELS:
            if m["filename"] not in missing:
                continue
            rf = tk.Frame(pb_frame, bg=BG)
            rf.pack(fill="x", pady=4)
            tk.Label(rf, text=m["filename"], bg=BG, fg=TEXT,
                     font=FONT_SMALL, anchor="w", width=50).pack(side="left")
            sl = tk.Label(rf, text="Waiting…", bg=BG, fg=SUBTEXT,
                          font=FONT_SMALL, width=20, anchor="e")
            sl.pack(side="right")
            bar = ttk.Progressbar(pb_frame, mode="determinate",

                                  length=480, maximum=100)
            bar.pack(fill="x", pady=(0, 2))
            self._bars[m["filename"]] = {"bar": bar, "status": sl}

        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var,
                 bg=BG, fg=SUBTEXT, font=FONT_SMALL,
                 padx=24).pack(anchor="w", pady=(4, 0))

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=16)
        self.btn_dl   = FlatBtn(btn_row, text="⬇  Download Now",
                                command=self._start_download,
                                color=ACCENT, hover=ACCENT_H)
        self.btn_dl.pack(side="left", padx=(0, 10))
        self.btn_skip = FlatBtn(btn_row, text="Skip (tagger won't work)",
                                command=self._skip,
                                color=CARD, hover=BORDER,
                                fg=SUBTEXT, padx=12)
        self.btn_skip.pack(side="left")

        self.update_idletasks()
        pw, ph = master.winfo_width(), master.winfo_height()
        px, py = master.winfo_x(), master.winfo_y()
        dw = self.winfo_reqwidth()
        dh = self.winfo_reqheight()
        self.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")
        self._poll()

    def _start_download(self):
        self.btn_dl.config(state="disabled", text="Downloading…")
        self.btn_skip.config(state="disabled")
        os.makedirs(MODELS_DIR, exist_ok=True)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        for m in REQUIRED_MODELS:
            if m["filename"] not in self._missing or self._cancelled:
                continue
            fn   = m["filename"]
            dest = os.path.join(MODELS_DIR, fn)
            self._q.put(("status", fn, "Connecting…"))
            try:
                # Use wget directly — same as:
                # wget -c --tries=10 --timeout=20 --waitretry=5 -O dest url
                cmd = [
                    "wget", "-c", "--tries=10", "--timeout=20",
                    "--waitretry=5", "--progress=dot:mega",
                    "-O", dest, m["url"]
                ]
                proc = subprocess.Popen(
                    cmd, stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL, text=True,
                    bufsize=1)
                total_size = None
                downloaded = 0
                for line in proc.stderr:
                    if self._cancelled:
                        proc.terminate()
                        break
                    line = line.strip()
                    # dot:mega format: "...K" lines and "saved (X MB)"
                    # Also catch "Length: 12345678 (12M)"
                    if "Length:" in line and total_size is None:
                        import re as _re
                        lm = _re.search(r"Length:\s*(\d+)", line)
                        if lm:
                            total_size = int(lm.group(1))
                    if line.endswith("K") or "K " in line:
                        # each dot = 102400 bytes in dot:mega
                        dots = line.count(".")
                        downloaded = dots * 102400
                        if total_size and total_size > 0:
                            pct = min(downloaded / total_size * 100, 99)
                            self._q.put(("progress", fn, pct,
                                         f"{fmt_bytes(downloaded)} / {fmt_bytes(total_size)}"))
                        else:
                            self._q.put(("progress", fn, 0,
                                         fmt_bytes(downloaded)))
                proc.wait()
                if proc.returncode != 0 and not self._cancelled:
                    raise Exception(f"wget failed (exit {proc.returncode})")
                if not self._cancelled:
                    size = os.path.getsize(dest) if os.path.exists(dest) else 0
                    self._q.put(("progress", fn, 100, fmt_bytes(size)))
                    self._q.put(("done", fn, f"✓  {fmt_bytes(size)}"))
            except Exception as e:
                if os.path.exists(dest):
                    os.remove(dest)
                if not self._cancelled:
                    self._q.put(("error", fn, str(e)))
                return
        if not self._cancelled:
            self._q.put(("all_done", "", ""))

    def _poll(self):
        try:
            while True:
                msg  = self._q.get_nowait()
                kind, fn = msg[0], msg[1]
                if kind == "progress":
                    pct, label = msg[2], msg[3]
                    if fn in self._bars:
                        self._bars[fn]["bar"]["value"] = pct
                        self._bars[fn]["status"].config(text=label, fg=TEXT)
                elif kind == "status":
                    if fn in self._bars:
                        self._bars[fn]["status"].config(
                            text=msg[2], fg=SUBTEXT)
                elif kind == "done":
                    if fn in self._bars:
                        self._bars[fn]["bar"]["value"] = 100
                        self._bars[fn]["status"].config(
                            text=msg[2], fg=GREEN)
                elif kind == "error":
                    if fn in self._bars:
                        self._bars[fn]["status"].config(
                            text=f"✗ {msg[2][:30]}", fg=RED)
                    self._status_var.set(f"⚠  Error: {msg[2]}")
                    self.btn_dl.config(state="normal", text="⬇  Retry")
                    self.btn_skip.config(state="normal")
                    return
                elif kind == "all_done":
                    self._done = True
                    self._status_var.set("✅  All models downloaded!")
                    self.btn_dl.config(state="disabled", text="✓  Done")
                    self.btn_skip.config(state="normal",
                                        text="Continue →",
                                        command=self.destroy)
                    return
        except queue.Empty:
            pass
        if not self._done and not self._cancelled:
            self.after(20, self._poll)

    def _skip(self):
        self._cancelled = True
        self.destroy()

    def _on_close(self):
        self._cancelled = True
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  Main App
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Essentia Music Tagger")
        self.geometry("1560x900")
        self.minsize(1100, 680)
        self.configure(bg=BG)

        # ── state vars ─────────────────────────────────────────────────────
        self.v_script       = tk.StringVar(value=find_script())
        self.v_music_dir    = tk.StringVar(value="")
        self.v_single_file  = tk.StringVar(value="")
        self.v_single       = tk.BooleanVar(value=False)
        self.v_dry_run      = tk.BooleanVar(value=True)
        self.v_overwrite    = tk.BooleanVar(value=False)
        self.v_mood         = tk.BooleanVar(value=True)
        self.v_genres       = tk.IntVar(value=3)
        self.v_genre_thresh = tk.DoubleVar(value=15.0)
        self.v_mood_thresh  = tk.DoubleVar(value=0.5)
        self.v_format       = tk.StringVar(value="parent_child")
        self.v_use_gpu      = tk.BooleanVar(value=False)
        self.v_gpu_index    = tk.StringVar(value="0")

        self._proc           = None
        self._log_q          = queue.Queue()
        self._running        = False
        self._lib            = {}
        self._track_files    = []
        self._detected_gpus  = []

        self._build()
        self._poll()
        self.v_music_dir.trace_add("write",
                                   lambda *_: self.after(200, self._scan))
        # Create log directories
        for d in (TAGGER_LOGS, GUI_LOGS):
            os.makedirs(d, exist_ok=True)

        self.after(300,  self._check_models)
        self.after(800,  self._auto_detect_gpu)

    # ── startup ────────────────────────────────────────────────────────────
    def _check_models(self):
        missing = models_present()
        if missing:
            self.status_var.set(
                f"⚠  {len(missing)} model file(s) missing — download required")
            dlg = ModelDownloadDialog(self, missing)
            self.wait_window(dlg)
            self.status_var.set(
                "✅  Models ready" if not models_present()
                else "⚠  Models missing — tagger will not run")
        else:
            self.status_var.set("✅  Models ready")

    def _auto_detect_gpu(self):
        """Silent GPU scan on startup — updates header badge."""
        def worker():
            gpus = detect_gpus()
            self.after(0, lambda: self._apply_gpu_result(gpus, silent=True))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_gpu_result(self, gpus, silent=False):
        self._detected_gpus = gpus
        if gpus:
            names = "  |  ".join(f"[{i}] {n}" for i, n in gpus)
            self._badge_var.set(f"⚡  {names}")
            self._badge_lbl.config(fg=GPU_COL)
            if not silent:
                self.gpu_info_var.set(f"✅  Found: {names}")
                self.gpu_info_lbl.config(fg=GREEN)
        else:
            self._badge_var.set("🖥  No GPU detected")
            self._badge_lbl.config(fg=SUBTEXT)
            if not silent:
                self.gpu_info_var.set(
                    "⚠  No NVIDIA GPU found — "
                    "check nvidia-smi and your driver install")
                self.gpu_info_lbl.config(fg=RED)

    # ── layout ─────────────────────────────────────────────────────────────
    def _build(self):
        # header
        hdr = tk.Frame(self, bg=SURFACE, pady=10)
        hdr.pack(fill="x")
        lf = tk.Frame(hdr, bg=SURFACE)
        lf.pack(side="left", padx=20)
        tk.Label(lf, text="♫  Essentia Music Tagger",
                 bg=SURFACE, fg=ACCENT, font=FONT_TITLE).pack(side="left")
        tk.Label(lf, text="AI-powered genre & mood tagging",
                 bg=SURFACE, fg=SUBTEXT, font=FONT
                 ).pack(side="left", padx=10)

        # GPU badge — updated after auto-detect
        self._badge_var = tk.StringVar(value="⚡  Detecting GPU…")
        self._badge_lbl = tk.Label(hdr, textvariable=self._badge_var,
                                   bg=SURFACE, fg=SUBTEXT,
                                   font=FONT_B, padx=18)
        self._badge_lbl.pack(side="right")

        # notebook
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("App.TNotebook",
                        background=BG, borderwidth=0, tabmargins=0)
        style.configure("App.TNotebook.Tab",
                        background=SURFACE, foreground=SUBTEXT,
                        font=FONT_B, padding=(20, 6), borderwidth=0)
        style.map("App.TNotebook.Tab",
                  background=[("selected", CARD)],
                  foreground=[("selected", ACCENT_H)],
                  padding=[("selected", (20, 10))])

        nb = ttk.Notebook(self, style="App.TNotebook")
        nb.pack(fill="both", expand=True)

        lib_tab    = tk.Frame(nb, bg=BG)
        tagger_tab = tk.Frame(nb, bg=BG)
        nb.add(lib_tab,    text="  📚  Library Browser  ")
        nb.add(tagger_tab, text="  🎸  Tagger  ")

        self._build_library(lib_tab)
        self._build_tagger(tagger_tab)

        # status bar
        self.status_var = tk.StringVar(value="Starting…")
        tk.Label(self, textvariable=self.status_var,
                 bg=SURFACE, fg=SUBTEXT, font=FONT_SMALL,
                 anchor="w", padx=16, pady=4
                 ).pack(fill="x", side="bottom")

    # ─────────────────────────────────────────────────────────────────────────
    #  LIBRARY BROWSER
    # ─────────────────────────────────────────────────────────────────────────
    def _build_library(self, parent):
        tb = tk.Frame(parent, bg=SURFACE, pady=7)
        tb.pack(fill="x")
        tk.Label(tb, text="Music folder:", bg=SURFACE,
                 fg=SUBTEXT, font=FONT, padx=12).pack(side="left")
        tk.Entry(tb, textvariable=self.v_music_dir,
                 bg=BG, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT,
                 font=FONT, width=52
                 ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        def pick():
            initial = self.v_music_dir.get().strip()
            if not initial or not os.path.isdir(initial):
                initial = os.path.expanduser("~")
            p = ask_directory(title="Choose Music Folder", initialdir=initial)
            if p:
                self.v_music_dir.set(p)

        FlatBtn(tb, text="📂  Browse", command=pick,
                color=ACCENT, hover=ACCENT_H,
                padx=10, pady=4).pack(side="left")
        FlatBtn(tb, text="↺  Refresh", command=self._scan,
                color=CARD, hover=BORDER,
                padx=10, pady=4).pack(side="left", padx=(6, 0))

        self._info = tk.StringVar(value="No folder selected")
        tk.Label(parent, textvariable=self._info,
                 bg=BG, fg=SUBTEXT, font=FONT_SMALL,
                 anchor="w", padx=16, pady=3).pack(fill="x")

        panels = tk.Frame(parent, bg=BG)
        panels.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        panels.columnconfigure(0, weight=0, minsize=160)  # artists fixed
        panels.columnconfigure(1, weight=1)               # albums stretches
        panels.columnconfigure(2, weight=2)               # tracks stretches more
        panels.columnconfigure(3, weight=0, minsize=500)  # tags fixed
        panels.rowconfigure(0, weight=1)

        self.lst_artist = StyledList(panels, title="🎤  Artists")
        self.lst_album  = StyledList(panels, title="💿  Albums")
        self.lst_track  = StyledList(panels, title="🎵  Tracks")
        self.pnl_tags   = TagPanel(panels)

        for col, w in enumerate([self.lst_artist, self.lst_album,
                                  self.lst_track, self.pnl_tags]):
            w.grid(row=0, column=col, sticky="nsew",
                   padx=(0 if col == 0 else 4, 0))

        self.lst_artist.bind_select(self._on_artist)
        self.lst_album.bind_select(self._on_album)
        self.lst_track.bind_select(self._on_track)

    def _detect_depth(self, folder):
        """
        Scan up to 200 audio-containing folders and measure their depth
        relative to the root. Returns:
          3 → Artist/Album/Track  (depth >= 2)
          2 → Artist/Track        (depth == 1)
          1 → flat                (depth == 0, files in root)
        """
        depths = []
        count  = 0
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            if any(is_audio(f) for f in files):
                rel   = os.path.relpath(root, folder)
                depth = 0 if rel == "." else len(rel.split(os.sep))
                depths.append(depth)
                count += 1
                if count >= 200:
                    break
        if not depths:
            return 1
        avg = sum(depths) / len(depths)
        if avg >= 1.5:
            return 3   # Artist / Album / Track
        elif avg >= 0.5:
            return 2   # Artist / Track
        else:
            return 1   # flat

    def _scan(self):
        folder = self.v_music_dir.get().strip()
        if not folder or not os.path.isdir(folder):
            return
        self._info.set("Scanning…")
        self.lst_artist.clear()
        self.lst_album.clear()
        self.lst_track.clear()
        self.pnl_tags.clear()

        def _read_tag(filepath, key):
            """Safely read a single tag from a file, returns None on failure."""
            if not HAS_MUTAGEN:
                return None
            try:
                f = MutagenFile(filepath, easy=True)
                if f and f.tags:
                    v = f.tags.get(key)
                    if v:
                        return str(v[0]).strip() if isinstance(v, list) else str(v).strip()
            except Exception:
                pass
            return None

        def _folder_guess(parts, depth):
            """
            Try to parse artist/album from folder names.
            Handles: 'Artist - Album', 'Artist_Album', or raw folder names.
            """
            raw = parts[-1] if parts else "(unknown)"
            for sep in [" - ", " – ", " _ ", "_-_"]:
                if sep in raw:
                    a, b = raw.split(sep, 1)
                    return a.strip(), b.strip()
            # If only one folder deep, can't split — return as album, unknown artist
            if len(parts) == 1:
                return "(unknown)", raw
            return parts[0], parts[1] if len(parts) > 1 else raw

        def worker():
            depth = self._detect_depth(folder)
            lib   = {}  # artist -> album -> [files]

            for root, dirs, files in os.walk(folder):
                dirs.sort()
                audio = [f for f in sorted(files) if is_audio(f)]
                if not audio:
                    continue
                rel   = os.path.relpath(root, folder)
                parts = [] if rel == "." else rel.split(os.sep)

                artist = None
                album  = None

                if depth == 3 and len(parts) >= 2:
                    # Clear Artist/Album/Track structure — use folders directly
                    artist = parts[0]
                    album  = parts[1]

                elif depth == 2 and len(parts) >= 1:
                    # Artist/Track — try tags on first file, then folder name
                    first = os.path.join(root, audio[0])
                    artist = _read_tag(first, "artist") or _read_tag(first, "albumartist")
                    album  = _read_tag(first, "album")
                    if not artist:
                        # Try splitting folder name e.g. "2Pac - All Eyez On Me"
                        artist, album = _folder_guess(parts, depth)
                    elif not album:
                        album = parts[0]  # use folder name as album

                else:
                    # Flat or ambiguous — read tags from first file in folder
                    first = os.path.join(root, audio[0])
                    artist = _read_tag(first, "artist") or _read_tag(first, "albumartist")
                    album  = _read_tag(first, "album")
                    if not artist and not album:
                        # Last resort: try to parse folder name
                        artist, album = _folder_guess(parts, depth) if parts else ("(library)", rel or "(root)")
                    elif not artist:
                        artist = "(unknown artist)"
                    elif not album:
                        album = parts[-1] if parts else "(unknown album)"

                # Final safety fallbacks — never show None or empty
                artist = (artist or "").strip() or "(unknown artist)"
                album  = (album  or "").strip() or "(unknown album)"

                lib.setdefault(artist, {}).setdefault(album, [])
                lib[artist][album].extend(
                    os.path.join(root, f) for f in audio)

            total = sum(len(tl) for al in lib.values()
                        for tl in al.values())
            self.after(0, lambda: self._apply_scan(lib, total, depth))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_scan(self, lib, total, depth=3):
        self._lib   = lib
        self._depth = depth
        artists     = sorted(lib.keys())

        # Relabel columns to match detected structure
        if depth == 3:
            self.lst_artist.set_title("🎤  Artists")
            self.lst_album.set_title("💿  Albums")
        elif depth == 2:
            self.lst_artist.set_title("🎤  Artists")
            self.lst_album.set_title("💿  Albums")
        else:
            self.lst_artist.set_title("📁  Library")
            self.lst_album.set_title("💿  Albums")

        self.lst_artist.set_items(artists)
        albums_n = sum(len(al) for al in lib.values())
        depth_str = {3: "Artist/Album/Track", 2: "Artist/Track", 1: "Flat"}[depth]
        self._info.set(
            f"  {len(artists)} artist(s)   {albums_n} album(s)"
            f"   {total} track(s)  —  structure: {depth_str}")
        self.lst_album.clear()
        self.lst_track.clear()
        self.pnl_tags.clear()

    def _on_artist(self, _=None):
        artist = self.lst_artist.get_selected()
        if not artist:
            return
        albums = sorted(self._lib.get(artist, {}).keys())
        self.lst_album.set_items(albums)
        self.lst_track.clear()
        self.pnl_tags.clear("Select an album")
        self._info.set(f"  Artist: {artist}  —  {len(albums)} album(s)")

    def _on_album(self, _=None):
        artist = self.lst_artist.get_selected()
        album  = self.lst_album.get_selected()
        if not artist or not album:
            return
        files = self._lib.get(artist, {}).get(album, [])
        self._track_files = files
        self.lst_track.set_items([os.path.basename(f) for f in files])
        self.pnl_tags.clear("Select a track")
        self._info.set(f"  Album: {album}  —  {len(files)} track(s)")

    def _on_track(self, _=None):
        idx = self.lst_track.lb.curselection()
        if not idx:
            return
        fp = self._track_files[idx[0]]
        self.pnl_tags.load(fp)
        self._info.set(f"📄  {fp}")
        self.v_single_file.set(fp)

    # ─────────────────────────────────────────────────────────────────────────
    #  TAGGER TAB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tagger(self, parent):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, bd=0)
        vsb    = tk.Scrollbar(parent, orient="vertical",
                               command=canvas.yview, bg=CARD,
                               troughcolor=BG, activebackground=ACCENT,
                               relief="flat")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        wid   = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(wid, width=e.width))
        # Linux scroll
        canvas.bind_all("<Button-4>",
                        lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>",
                        lambda e: canvas.yview_scroll( 1, "units"))

        body = tk.Frame(inner, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=16)

        self._sec(body, "⚙  Configuration")
        self._cfg_card(body)
        self._hsep(body)
        self._sec(body, "▶  Run")
        self._run_card(body)
        self._hsep(body)
        self._sec(body, "📋  Output")
        self._log_card(body)

    def _sec(self, parent, title):
        tk.Label(parent, text=title, bg=BG, fg=ACCENT,
                 font=FONT_B, anchor="w").pack(fill="x", pady=(6, 2))

    def _hsep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=10)

    def _cfg_card(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=18, pady=14)
        card.pack(fill="x", pady=(2, 0))
        card.columnconfigure(1, weight=1)

        def lrow(label, row, tip=""):
            lbl = tk.Label(card, text=label, bg=CARD, fg=SUBTEXT,
                           font=FONT, anchor="w", width=22)
            lbl.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
            if tip:
                Tooltip(lbl, tip)

        def prow(var, label, row, mode="dir", tip=""):
            lrow(label, row, tip)
            e = tk.Entry(card, textvariable=var, bg=BG, fg=TEXT,
                         insertbackground=ACCENT, relief="flat",
                         highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=ACCENT, font=FONT)
            e.grid(row=row, column=1, sticky="ew", pady=5)
            def browse(var=var, mode=mode, label=label):
                current = var.get().strip()
                if mode == "dir":
                    initial = current if os.path.isdir(current) else os.path.expanduser("~")
                    p = ask_directory(title=label, initialdir=initial)
                else:
                    initial = os.path.dirname(current) if current else os.path.expanduser("~")
                    p = ask_openfile(title=label, initialdir=initial,
                                     filetypes=[("Python", "*.py"), ("All", "*.*")])
                if p:
                    var.set(p)
            FlatBtn(card, text="📂", command=browse,
                    color=CARD, hover=BORDER, padx=8, pady=3
                    ).grid(row=row, column=2, padx=(6, 0))

        prow(self.v_script,    "tag_music.py script", 0, "file",
             "Path to tag_music.py in the cloned repo")
        prow(self.v_music_dir, "Music folder", 1, "dir",
             "Root music folder")

        # target toggle
        lrow("Tag target", 2)
        tgl    = tk.Frame(card, bg=CARD)
        tgl.grid(row=2, column=1, sticky="w")
        sf_row = tk.Frame(card, bg=CARD)
        sf_row.columnconfigure(1, weight=1)

        def _toggle():
            sf_row.grid() if self.v_single.get() else sf_row.grid_remove()

        for txt, val in [("Whole folder", False), ("Single file", True)]:
            tk.Radiobutton(tgl, text=txt, variable=self.v_single,
                           value=val, command=_toggle,
                           bg=CARD, fg=TEXT, selectcolor=BG,
                           activebackground=CARD, font=FONT
                           ).pack(side="left", padx=(0, 12))

        tk.Label(sf_row, text="Audio file", bg=CARD, fg=SUBTEXT,
                 font=FONT, anchor="w", width=22
                 ).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(sf_row, textvariable=self.v_single_file,
                 bg=BG, fg=TEXT, insertbackground=ACCENT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, font=FONT
                 ).grid(row=0, column=1, sticky="ew", pady=5)

        def _pick_sf():
            current = self.v_single_file.get().strip()
            initial = (os.path.dirname(current)
                       if current and os.path.exists(os.path.dirname(current))
                       else self.v_music_dir.get().strip()
                       or os.path.expanduser("~"))
            p = ask_openfile(
                title="Choose audio file",
                initialdir=initial,
                filetypes=[("Audio", "*.flac *.mp3 *.ogg *.m4a *.wav *.opus"),
                           ("All", "*.*")])
            if p:
                self.v_single_file.set(p)

        FlatBtn(sf_row, text="📂", command=_pick_sf,
                color=CARD, hover=BORDER, padx=8, pady=3
                ).grid(row=0, column=2, padx=(6, 0))
        sf_row.grid(row=3, column=0, columnspan=3, sticky="ew")
        sf_row.grid_remove()

        # ── genre ──
        tk.Frame(card, bg=BORDER, height=1).grid(
            row=9, column=0, columnspan=3, sticky="ew", pady=8)
        tk.Label(card, text="🎸  Genre Settings", bg=CARD, fg=TEXT,
                 font=FONT_B, anchor="w"
                 ).grid(row=10, column=0, columnspan=3,
                        sticky="w", pady=(4, 2))

        lrow("Genres to write", 11,
             "How many top genre tags to write per track (1–10)")
        tk.Spinbox(card, from_=1, to=10, textvariable=self.v_genres,
                   width=5, bg=BG, fg=TEXT, buttonbackground=BORDER,
                   insertbackground=ACCENT, relief="flat", font=FONT
                   ).grid(row=11, column=1, sticky="w", pady=5)

        lrow("Genre threshold (%)", 12,
             "Min ML confidence % for a genre tag to be saved")
        gf = tk.Frame(card, bg=CARD)
        gf.grid(row=12, column=1, columnspan=2, sticky="ew")
        self.lbl_gt = tk.Label(gf,
                               text=f"{self.v_genre_thresh.get():.0f}%",
                               bg=CARD, fg=ACCENT, font=FONT_B, width=5)
        self.lbl_gt.pack(side="right")
        tk.Scale(gf, variable=self.v_genre_thresh, from_=1, to=100,
                 orient="horizontal", resolution=1, showvalue=False,
                 bg=CARD, fg=TEXT, troughcolor=BG,
                 activebackground=ACCENT, highlightthickness=0,
                 command=lambda v: self.lbl_gt.config(
                     text=f"{float(v):.0f}%")
                 ).pack(fill="x", expand=True, side="left")

        lrow("Genre format", 13, "How genre tags are formatted")
        fmtf = tk.Frame(card, bg=CARD)
        fmtf.grid(row=13, column=1, columnspan=2, sticky="w")
        for label, val in [
            ("parent_child  →  Rock - Indie Rock",  "parent_child"),
            ("child_parent  →  Indie Rock - Rock",  "child_parent"),
            ("child_only    →  Indie Rock",          "child_only"),
            ("raw           →  Rock---Indie Rock",   "raw"),
        ]:
            tk.Radiobutton(fmtf, text=label, variable=self.v_format,
                           value=val, bg=CARD, fg=TEXT,
                           selectcolor=BG, activebackground=CARD,
                           font=FONT).pack(anchor="w")

        # ── mood ──
        tk.Frame(card, bg=BORDER, height=1).grid(
            row=19, column=0, columnspan=3, sticky="ew", pady=8)
        mhdr = tk.Frame(card, bg=CARD)
        mhdr.grid(row=20, column=0, columnspan=3, sticky="w", pady=(4, 2))
        tk.Label(mhdr, text="😊  Mood Analysis",
                 bg=CARD, fg=TEXT, font=FONT_B).pack(side="left")
        tk.Checkbutton(mhdr, text="Enable", variable=self.v_mood,
                       bg=CARD, fg=SUBTEXT, selectcolor=BG,
                       activebackground=CARD, font=FONT
                       ).pack(side="left", padx=(12, 0))

        lrow("Mood threshold (%)", 21,
             "Min confidence % for a mood tag to be saved")
        mf = tk.Frame(card, bg=CARD)
        mf.grid(row=21, column=1, columnspan=2, sticky="ew")
        self.lbl_mt = tk.Label(mf,
                               text=f"{self.v_mood_thresh.get():.1f}%",
                               bg=CARD, fg=ACCENT, font=FONT_B, width=5)
        self.lbl_mt.pack(side="right")
        tk.Scale(mf, variable=self.v_mood_thresh, from_=0.1, to=10,
                 orient="horizontal", resolution=0.1, showvalue=False,
                 bg=CARD, fg=TEXT, troughcolor=BG,
                 activebackground=ACCENT, highlightthickness=0,
                 command=lambda v: self.lbl_mt.config(
                     text=f"{float(v):.1f}%")
                 ).pack(fill="x", expand=True, side="left")

        # ── options ──
        tk.Frame(card, bg=BORDER, height=1).grid(
            row=29, column=0, columnspan=3, sticky="ew", pady=8)
        tk.Label(card, text="🔧  Options", bg=CARD, fg=TEXT,
                 font=FONT_B, anchor="w"
                 ).grid(row=30, column=0, columnspan=3,
                        sticky="w", pady=(4, 2))
        opts = tk.Frame(card, bg=CARD)
        opts.grid(row=31, column=0, columnspan=3, sticky="w")
        # Radio-style write mode: clicking one instantly selects it
        self.v_write_mode = tk.StringVar(value="dry")

        def _on_mode(*_):
            m = self.v_write_mode.get()
            self.v_dry_run.set(m == "dry")
            self.v_overwrite.set(m == "overwrite")

        self.v_write_mode.trace_add("write", _on_mode)

        for text, val, tip in [
            ("🧪  Dry run — preview only, don't write tags", "dry",
             "Simulate without writing. Recommended for first run."),
            ("✏️  Normal — write tags, skip already-tagged files", "normal",
             "Write genre/mood tags only to files that don't already have them."),
            ("🔁  Overwrite — write tags, replace existing ones", "overwrite",
             "Re-tag all files, replacing any existing genre or mood tags."),
        ]:
            rb = tk.Radiobutton(opts, text=text, variable=self.v_write_mode,
                                value=val, bg=CARD, fg=TEXT, selectcolor=BG,
                                activebackground=CARD, font=FONT)
            rb.pack(anchor="w")
            Tooltip(rb, tip)

        # ══════════════════════════════════════════════════════════════════
        #  GPU / CPU SECTION
        # ══════════════════════════════════════════════════════════════════
        tk.Frame(card, bg=BORDER, height=1).grid(
            row=39, column=0, columnspan=3, sticky="ew", pady=8)

        gpu_hdr = tk.Frame(card, bg=CARD)
        gpu_hdr.grid(row=40, column=0, columnspan=3, sticky="w", pady=(4, 6))
        tk.Label(gpu_hdr, text="⚡  Compute Device",
                 bg=CARD, fg=TEXT, font=FONT_B).pack(side="left")
        tk.Label(gpu_hdr,
                 text="(sets CUDA_VISIBLE_DEVICES before running tag_music.py)",
                 bg=CARD, fg=SUBTEXT, font=FONT_SMALL,
                 ).pack(side="left", padx=(10, 0))

        # ── CPU / GPU radio ─────────────────────────────────────────────
        device_row = tk.Frame(card, bg=CARD)
        device_row.grid(row=41, column=0, columnspan=3, sticky="w")

        self._gpu_widgets = []

        def _on_device_toggle(*_):
            state = "normal" if self.v_use_gpu.get() else "disabled"
            for w in self._gpu_widgets:
                try:
                    w.config(state=state)
                except Exception:
                    pass
            _update_badge()

        cpu_rb = tk.Radiobutton(device_row, text="🖥  CPU",
                                variable=self.v_use_gpu, value=False,
                                command=_on_device_toggle,
                                bg=CARD, fg=TEXT, selectcolor=BG,
                                activebackground=CARD, font=FONT)
        cpu_rb.pack(side="left", padx=(0, 18))
        Tooltip(cpu_rb, "CPU inference — always works, no CUDA needed")

        gpu_rb = tk.Radiobutton(device_row, text="🎮  GPU  (CUDA)",
                                variable=self.v_use_gpu, value=True,
                                command=_on_device_toggle,
                                bg=CARD, fg=GPU_COL, selectcolor=BG,
                                activebackground=CARD, font=FONT_B)
        gpu_rb.pack(side="left")
        Tooltip(gpu_rb,
                "GPU inference via CUDA.\n"
                "Requires: NVIDIA driver + CUDA + cuDNN\n"
                "and essentia-tensorflow installed.\n"
                "Typically 2–5× faster than CPU for large libraries.")

        # ── GPU sub-row ─────────────────────────────────────────────────
        gpu_sub = tk.Frame(card, bg=CARD)
        gpu_sub.grid(row=42, column=0, columnspan=3, sticky="w", pady=(4, 2))

        tk.Label(gpu_sub, text="   GPU index:",
                 bg=CARD, fg=SUBTEXT, font=FONT).pack(side="left")

        self.gpu_spin = tk.Spinbox(
            gpu_sub, from_=0, to=7,
            textvariable=self.v_gpu_index,
            width=3, bg=BG, fg=TEXT,
            buttonbackground=BORDER,
            insertbackground=ACCENT,
            relief="flat", font=FONT,
            state="disabled")
        self.gpu_spin.pack(side="left", padx=(6, 14))
        self._gpu_widgets.append(self.gpu_spin)
        Tooltip(self.gpu_spin,
                "GPU index to use (0 = first GPU).\n"
                "With multiple GPUs, set this to the one you want.")

        self.btn_detect = FlatBtn(gpu_sub, text="🔍  Detect GPUs",
                                  command=self._detect_gpus,
                                  color=BORDER, hover=SURFACE,
                                  padx=10, pady=3, state="disabled")
        self.btn_detect.pack(side="left")
        self._gpu_widgets.append(self.btn_detect)
        Tooltip(self.btn_detect,
                "Scan for NVIDIA GPUs via nvidia-smi.\n"
                "Auto-detects on startup too.")

        # ── GPU info label ───────────────────────────────────────────────
        self.gpu_info_var = tk.StringVar(value="Detecting GPUs…")
        self.gpu_info_lbl = tk.Label(card,
                                     textvariable=self.gpu_info_var,
                                     bg=CARD, fg=SUBTEXT,
                                     font=FONT_SMALL, anchor="w")
        self.gpu_info_lbl.grid(row=43, column=0, columnspan=3,
                               sticky="w", padx=(4, 0), pady=(0, 4))

        def _update_badge(*_):
            if self.v_use_gpu.get():
                idx = self.v_gpu_index.get().strip() or "0"
                gpu_name = next((n for i, n in self._detected_gpus
                                 if i == idx), "")
                label = f"GPU mode — CUDA_VISIBLE_DEVICES={idx}"
                if gpu_name:
                    label += f"  ({gpu_name})"
                self.gpu_info_var.set(label)
                self.gpu_info_lbl.config(fg=GPU_COL)
            else:
                self.gpu_info_var.set(
                    "CPU mode — CUDA_VISIBLE_DEVICES=-1  (GPU hidden from TF)")
                self.gpu_info_lbl.config(fg=SUBTEXT)

        self.v_gpu_index.trace_add("write", _update_badge)
        _update_badge()

    def _run_card(self, parent):
        rf = tk.Frame(parent, bg=BG)
        rf.pack(fill="x")

        self.btn_run = FlatBtn(rf, text="▶  Start Tagging",
                               command=self._start,
                               color=GREEN, fg="#0e1117",
                               hover="#6ee7b7")
        self.btn_run.pack(side="left")

        self.btn_stop = FlatBtn(rf, text="■  Stop",
                                command=self._stop,
                                color=RED, fg="white",
                                hover="#fca5a5")
        self.btn_stop.pack(side="left", padx=(10, 0))
        self.btn_stop.config(state="disabled")

        self.progress = ttk.Progressbar(rf, mode="indeterminate",
                                        length=160)
        self.progress.pack(side="left", padx=(14, 0))

    def _log_card(self, parent):
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x")
        FlatBtn(hdr, text="Clear", command=self._clear_log,
                color=CARD, hover=BORDER, padx=10, pady=3
                ).pack(side="right")

        lf = tk.Frame(parent, bg=BG)
        lf.pack(fill="both", expand=True)

        self.log = tk.Text(lf, bg=SURFACE, fg=TEXT,
                           insertbackground=ACCENT, relief="flat",
                           font=MONO, wrap="word", state="disabled",
                           padx=10, pady=8, height=18,
                           highlightthickness=1,
                           highlightbackground=BORDER)
        sb = tk.Scrollbar(lf, command=self.log.yview,
                          bg=CARD, troughcolor=BG,
                          activebackground=ACCENT)
        self.log.config(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for tag, col in [
            ("genre", PURPLE), ("mood", GREEN),  ("ok",    GREEN),
            ("warn",  YELLOW),  ("err",  RED),    ("dim",   SUBTEXT),
            ("track", ACCENT_H),("dry",  YELLOW), ("gpu",   GPU_COL),
        ]:
            self.log.tag_config(tag, foreground=col)

    # ── GPU detect ─────────────────────────────────────────────────────────
    def _detect_gpus(self):
        self.gpu_info_var.set("Scanning…")
        self.gpu_info_lbl.config(fg=YELLOW)
        self.update_idletasks()

        def worker():
            gpus = detect_gpus()
            self.after(0, lambda: self._apply_gpu_result(gpus, silent=False))

        threading.Thread(target=worker, daemon=True).start()

    # ── Build command ──────────────────────────────────────────────────────
    def _build_cmd(self):
        script = self.v_script.get().strip()
        if not script or not os.path.isfile(script):
            return None, None, f"tag_music.py not found:\n{script or '(not set)'}"

        if self.v_single.get():
            target = self.v_single_file.get().strip()
            if not target or not os.path.isfile(target):
                return None, None, "Please select a valid audio file."
        else:
            target = self.v_music_dir.get().strip()
            if not target or not os.path.isdir(target):
                return None, None, "Please set a valid music folder."

        cmd = [sys.executable, script, target, "--auto",
               "--genres",          str(self.v_genres.get()),
               "--genre-threshold", str(int(self.v_genre_thresh.get())),
               "--mood-threshold",  str(self.v_mood_thresh.get()),
               "--genre-format",    self.v_format.get(),
               "--model-dir",       MODELS_DIR,
               "--log-dir",         TAGGER_LOGS]
        if self.v_dry_run.get():   cmd.append("--dry-run")
        if self.v_overwrite.get(): cmd.append("--overwrite")
        if not self.v_mood.get():  cmd.append("--no-moods")
        if self.v_single.get():    cmd.append("--single-file")

        env = os.environ.copy()
        # Suppress TensorFlow spam (WARNING and below)
        env["TF_CPP_MIN_LOG_LEVEL"] = "3"
        env["PYTHONUNBUFFERED"] = "1"
        # Auto-find ALL nvidia CUDA lib dirs inside the venv
        venv = os.path.dirname(os.path.dirname(sys.executable))
        nvidia_base = os.path.join(
            venv, "lib",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
            "site-packages", "nvidia")
        existing = []
        if os.path.isdir(nvidia_base):
            for pkg in os.listdir(nvidia_base):
                lib_dir = os.path.join(nvidia_base, pkg, "lib")
                if os.path.isdir(lib_dir):
                    existing.append(lib_dir)
        if existing:
            current = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = ":".join(existing + ([current] if current else []))
        if self.v_use_gpu.get():
            idx = self.v_gpu_index.get().strip() or "0"
            env["CUDA_VISIBLE_DEVICES"] = idx
        else:
            env["CUDA_VISIBLE_DEVICES"] = "-1"

        return cmd, env, None

    # ── Start / Stop ───────────────────────────────────────────────────────
    def _start(self):
        cmd, env, err = self._build_cmd()
        if err:
            self._append(f"[ERROR] {err}\n", "err")
            return

        self._running = True
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress.start(12)

        if self.v_use_gpu.get():
            idx      = env["CUDA_VISIBLE_DEVICES"]
            gpu_name = next((n for i, n in self._detected_gpus
                             if i == idx), "")
            suffix   = f"  ({gpu_name})" if gpu_name else ""
            self._append(
                f"⚡  GPU mode — CUDA_VISIBLE_DEVICES={idx}{suffix}\n",
                "gpu")
        else:
            self._append(
                "🖥  CPU mode — CUDA_VISIBLE_DEVICES=-1\n", "dim")

        # Open GUI session log file
        from datetime import datetime as _dt
        _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        self._gui_log_path = os.path.join(GUI_LOGS, f"gui_session_{_ts}.log")
        self._gui_log_file = open(self._gui_log_path, "w", encoding="utf-8")
        self._gui_log_file.write(f"GUI Session Log — {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._gui_log_file.write("=" * 80 + "\n\n")

        self._append(f"$ {' '.join(cmd)}\n", "dim")
        self.status_var.set("Running tagger…")

        # Quick GPU probe — run before the tagger so we can report GPU status
        if self.v_use_gpu.get():
            try:
                probe_env = env.copy()
                probe_env["TF_CPP_MIN_LOG_LEVEL"] = "0"
                probe_script = (
                    "import sys, subprocess\n"
                    "out = subprocess.check_output(['nvidia-smi', "
                    "'--query-gpu=name,memory.total', '--format=csv,noheader'], "
                    "text=True).strip()\n"
                    "print('GPU_OK:' + out)"
                )
                out = subprocess.check_output(
                    [sys.executable, "-c", probe_script],
                    env=probe_env, stderr=subprocess.DEVNULL,
                    text=True, timeout=10)
                if "GPU_OK:" in out:
                    gpu_info = out.split("GPU_OK:", 1)[1].strip()
                    self._append(f"✅  GPU confirmed via nvidia-smi: {gpu_info}\n", "ok")
                    # Now check if CUDA libs loaded OK
                    cuda_check = subprocess.check_output(
                        [sys.executable, "-c",
                         "import ctypes; ctypes.CDLL('libcudart.so.11.0'); print('CUDART_OK')"],
                        env=probe_env, stderr=subprocess.DEVNULL,
                        text=True, timeout=10)
                    if "CUDART_OK" in cuda_check:
                        self._append("✅  libcudart.so.11.0 loaded — CUDA active\n", "ok")
                    else:
                        self._append("⚠  libcudart not loaded — may fall back to CPU\n", "warn")
            except Exception as e:
                self._append(f"⚠  GPU probe failed: {e}\n", "warn")

        def worker():
            try:
                self._proc = subprocess.Popen(
                    args=cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, bufsize=1, env=env,
                    start_new_session=True)
                _current_track = [""]
                for line in iter(self._proc.stdout.readline, ""):
                    if not self._running:
                        break
                    # Suppress noisy Essentia internal warnings
                    if "No network created" in line or "last created network" in line:
                        continue
                    # Track current file progress
                    m = re.search(r"\[(\d+)/(\d+)\]", line)
                    if m:
                        _current_track[0] = f"[{m.group(1)}/{m.group(2)}]"
                        self.after(0, lambda t=_current_track[0]:
                                   self.status_var.set(f"Running tagger… {t}"))
                    self._log_q.put(line)
                self._proc.wait()
                rc = self._proc.returncode
                msg = f"\n✅  Finished (exit {rc})\n" if rc == 0 else f"\n⚠️   Exit code {rc}\n"
                self._log_q.put(msg)
                # Close GUI log
                if hasattr(self, "_gui_log_file") and self._gui_log_file and not self._gui_log_file.closed:
                    try:
                        self._gui_log_file.write(msg)
                        self._gui_log_file.close()
                    except Exception:
                        pass
            except Exception as ex:
                self._log_q.put(f"[ERROR] {ex}\n")
            finally:
                self._log_q.put(None)

        threading.Thread(target=worker, daemon=True).start()

    def _stop(self):
        self._running = False
        if self._proc and self._proc.poll() is None:
            try:
                import signal, os
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                self._proc.terminate()
            # Force kill after 2 seconds if still running
            def _force_kill():
                if self._proc and self._proc.poll() is None:
                    try:
                        import signal, os
                        os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                    except Exception:
                        self._proc.kill()
            self.after(2000, _force_kill)
            self._append("\n[Stopped by user]\n", "warn")
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress.stop()
        self.status_var.set("Stopped")

    # ── Poll log queue ─────────────────────────────────────────────────────
    def _poll(self):
        try:
            # Process max 50 lines per tick to keep GUI responsive
            for _ in range(50):
                item = self._log_q.get_nowait()
                if item is None:
                    self._running = False
                    self.btn_run.config(state="normal")
                    self.btn_stop.config(state="disabled")
                    self.progress.stop()
                    self.status_var.set("Done")
                    self.after(500, self._scan)
                    break
                else:
                    self._append_line(item)
        except queue.Empty:
            pass
        self.after(20, self._poll)

    # ── Log helpers ────────────────────────────────────────────────────────
    _ANSI = re.compile(r'\x1b\[[0-9;]*m')

    def _classify(self, line):
        l = line.lower()
        if "dry run" in l or "[dry run]" in l:                       return "dry"
        if any(x in l for x in ("🎸", "genre", "rock", "hip-hop",
                                   "jazz", "classical", "electronic")): return "genre"
        if any(x in l for x in ("😊", "mood", "energetic", "dark",
                                   "happy", "aggressive", "relaxed")):  return "mood"
        if any(x in l for x in ("✅", "success", "written", "saved")):  return "ok"
        if any(x in l for x in ("warning", "⚠", "skip")):              return "warn"
        if any(x in l for x in ("error", "failed", "❌")):              return "err"
        if re.search(r'\[\d+/\d+\]', line):                            return "track"
        if any(x in l for x in ("cuda", "gpu", "device")):             return "gpu"
        return None

    def _append_line(self, raw):
        self._append(self._ANSI.sub("", raw), self._classify(raw))

    def _append(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        self.log.see("end")
        self.log.config(state="disabled")
        # Mirror to GUI log file if open
        if hasattr(self, "_gui_log_file") and self._gui_log_file and not self._gui_log_file.closed:
            try:
                self._gui_log_file.write(text)
                self._gui_log_file.flush()
            except Exception:
                pass

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    import signal
    app = App()
    def _quit(sig=None, frame=None):
        try:
            app._stop()
        except Exception:
            pass
        app.destroy()
        sys.exit(0)
    signal.signal(signal.SIGINT,  _quit)
    signal.signal(signal.SIGTERM, _quit)
    app.protocol("WM_DELETE_WINDOW", _quit)
    app.mainloop()
