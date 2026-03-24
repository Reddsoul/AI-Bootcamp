#!/usr/bin/env python3
"""
AI Bootcamp –  Model Training Studio
Apple-inspired redesign with live system monitor.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import json
import os
import re
import time
import datetime
import urllib.request
import urllib.error
from pathlib import Path

# ─── Optional: system monitoring libs ────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# GPU monitoring — try pynvml first, fall back to nvidia-smi parsing
HAS_GPU = False
GPU_METHOD = None

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_GPU = True
    GPU_METHOD = "pynvml"
except Exception:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            HAS_GPU = True
            GPU_METHOD = "nvidia-smi"
    except Exception:
        pass


def _read_gpu():
    """Returns (gpu_percent, vram_used_mb, vram_total_mb) or None."""
    try:
        if GPU_METHOD == "pynvml":
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return (util.gpu, mem.used // (1024 * 1024), mem.total // (1024 * 1024))
        elif GPU_METHOD == "nvidia-smi":
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                parts = r.stdout.strip().split(",")
                return (int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip()))
    except Exception:
        pass
    return None


# ─── Apple-Inspired Palette ──────────────────────────────────────────────────
COLORS = {
    "bg_base":       "#1a1a1a",
    "bg_elevated":   "#222222",
    "bg_surface":    "#2a2a2a",
    "bg_input":      "#333333",
    "bg_hover":      "#3a3a3a",
    "bg_active":     "#444444",

    "border":        "#3a3a3a",
    "border_subtle": "#303030",

    "text_primary":  "#f5f5f7",
    "text_secondary":"#a1a1a6",
    "text_tertiary": "#6e6e73",

    "accent_blue":   "#0a84ff",
    "accent_green":  "#30d158",
    "accent_orange": "#ff9f0a",
    "accent_red":    "#ff453a",
    "accent_purple": "#bf5af2",
    "accent_teal":   "#64d2ff",

    "syn_keyword":   "#ff7eb3",
    "syn_string":    "#a8d8a8",
    "syn_param":     "#64d2ff",
    "syn_number":    "#ff9f0a",
    "syn_comment":   "#6e6e73",

    "gauge_bg":      "#2a2a2a",
    "gauge_cpu":     "#0a84ff",
    "gauge_ram":     "#30d158",
    "gauge_gpu":     "#bf5af2",
    "gauge_vram":    "#ff9f0a",
}

if os.name == "nt":
    FONT_BODY   = ("Segoe UI", 11)
    FONT_BODY_S = ("Segoe UI", 10)
    FONT_BOLD   = ("Segoe UI Semibold", 11)
    FONT_TITLE  = ("Segoe UI Semibold", 13)
    FONT_SMALL  = ("Segoe UI", 9)
    FONT_TINY   = ("Segoe UI", 8)
    FONT_MONO   = ("Cascadia Code", 12)
    FONT_MONO_S = ("Cascadia Code", 11)
else:
    FONT_BODY   = ("SF Pro Text", 11)
    FONT_BODY_S = ("SF Pro Text", 10)
    FONT_BOLD   = ("SF Pro Text", 11, "bold")
    FONT_TITLE  = ("SF Pro Display", 13)
    FONT_SMALL  = ("SF Pro Text", 9)
    FONT_TINY   = ("SF Pro Text", 8)
    FONT_MONO   = ("SF Mono", 12)
    FONT_MONO_S = ("SF Mono", 11)


DEFAULT_MODELFILE = '''FROM llama3.2:3b

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 2048

SYSTEM """
You are a helpful AI assistant.

Describe your assistant's personality, role, and rules here.
"""
'''

AUTOSAVE_DIR = Path.home() / ".ai_bootcamp" / "modelfiles"


# ─── Gauge Widgets ───────────────────────────────────────────────────────────
class MiniGauge(tk.Frame):
    """Tiny horizontal bar gauge with label and percentage."""

    def __init__(self, parent, label, color, gauge_width=110):
        super().__init__(parent, bg=COLORS["bg_base"])
        self._label = label
        self._color = color
        self._gw = gauge_width
        self._value = 0.0
        self._target = 0.0
        self._ready = False

        self._canvas = tk.Canvas(self, width=gauge_width, height=28,
                                 bg=COLORS["bg_base"], highlightthickness=0,
                                 bd=0)
        self._canvas.pack()
        self._canvas.bind("<Map>", self._on_map)

    def _on_map(self, event=None):
        self._ready = True
        self._draw()

    def set_value(self, pct):
        self._target = max(0.0, min(100.0, pct))

    def animate_step(self):
        if not self._ready:
            return
        diff = self._target - self._value
        if abs(diff) > 0.3:
            self._value += diff * 0.25
        else:
            self._value = self._target
        self._draw()

    def _draw(self):
        if not self._ready:
            return
        c = self._canvas
        c.delete("all")
        pad = 4
        bar_w = self._gw - pad * 2
        fill_w = max(0, int(bar_w * self._value / 100.0))
        bar_y = 18
        bar_h = 6

        c.create_text(pad, 2, text=self._label, anchor="nw",
                       fill=COLORS["text_tertiary"], font=FONT_TINY)
        c.create_text(self._gw - pad, 2, text=f"{self._value:.0f}%",
                       anchor="ne", fill=COLORS["text_secondary"], font=FONT_TINY)

        c.create_rectangle(pad, bar_y, pad + bar_w, bar_y + bar_h,
                            fill=COLORS["gauge_bg"], outline="")
        if fill_w > 1:
            c.create_rectangle(pad, bar_y, pad + fill_w, bar_y + bar_h,
                                fill=self._color, outline="")


class MemGauge(tk.Frame):
    """Gauge showing used/total memory with bar."""

    def __init__(self, parent, label, color, gauge_width=130):
        super().__init__(parent, bg=COLORS["bg_base"])
        self._label = label
        self._color = color
        self._gw = gauge_width
        self._pct = 0.0
        self._target_pct = 0.0
        self._used_mb = 0
        self._total_mb = 0
        self._ready = False

        self._canvas = tk.Canvas(self, width=gauge_width, height=28,
                                 bg=COLORS["bg_base"], highlightthickness=0,
                                 bd=0)
        self._canvas.pack()
        self._canvas.bind("<Map>", self._on_map)

    def _on_map(self, event=None):
        self._ready = True
        self._draw()

    def set_value(self, used_mb, total_mb):
        self._used_mb = used_mb
        self._total_mb = total_mb
        self._target_pct = (used_mb / total_mb * 100) if total_mb > 0 else 0

    def animate_step(self):
        if not self._ready:
            return
        diff = self._target_pct - self._pct
        if abs(diff) > 0.3:
            self._pct += diff * 0.25
        else:
            self._pct = self._target_pct
        self._draw()

    def _draw(self):
        if not self._ready:
            return
        c = self._canvas
        c.delete("all")
        pad = 4
        bar_w = self._gw - pad * 2
        fill_w = max(0, int(bar_w * self._pct / 100.0))
        bar_y = 18
        bar_h = 6

        c.create_text(pad, 2, text=self._label, anchor="nw",
                       fill=COLORS["text_tertiary"], font=FONT_TINY)

        if self._total_mb > 0:
            def _fmt(mb):
                return f"{mb / 1024:.1f}G" if mb >= 1024 else f"{mb}M"
            val_text = f"{_fmt(self._used_mb)}/{_fmt(self._total_mb)}"
        else:
            val_text = "—"
        c.create_text(self._gw - pad, 2, text=val_text, anchor="ne",
                       fill=COLORS["text_secondary"], font=FONT_TINY)

        c.create_rectangle(pad, bar_y, pad + bar_w, bar_y + bar_h,
                            fill=COLORS["gauge_bg"], outline="")
        if fill_w > 1:
            c.create_rectangle(pad, bar_y, pad + fill_w, bar_y + bar_h,
                                fill=self._color, outline="")


# ─── App ─────────────────────────────────────────────────────────────────────
class AIBootcamp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Bootcamp")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(bg=COLORS["bg_base"])

        self.model_name = tk.StringVar(value="my-model")
        self.train_running = False
        self.chat_history = []
        self.response_log = []
        self.modelfile_path = None
        self.current_model_trained = False
        self._autosave_pending = None

        # Monitor state
        self._monitor_active = False
        self._peak_cpu = 0.0
        self._peak_ram = 0.0
        self._peak_gpu = 0.0

        AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)

        self._style_ttk()
        self._build_ui()
        self._apply_syntax()
        self.after(300, self._check_ollama)
        self._load_last_modelfile()
        self._animate_gauges()

    # ── ttk theming ───────────────────────────────────────────────────────────
    def _style_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame",       background=COLORS["bg_base"])
        s.configure("Surface.TFrame", background=COLORS["bg_elevated"])
        s.configure("TLabel",       background=COLORS["bg_base"],
                    foreground=COLORS["text_primary"], font=FONT_BODY)
        s.configure("Secondary.TLabel", background=COLORS["bg_elevated"],
                    foreground=COLORS["text_secondary"], font=FONT_BODY_S)
        s.configure("TEntry",
                    fieldbackground=COLORS["bg_input"],
                    background=COLORS["bg_input"],
                    foreground=COLORS["text_primary"],
                    insertcolor=COLORS["accent_blue"],
                    bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"],
                    darkcolor=COLORS["border"],
                    font=FONT_MONO_S, padding=6)
        s.configure("Vertical.TScrollbar",
                    background=COLORS["bg_elevated"],
                    troughcolor=COLORS["bg_base"],
                    bordercolor=COLORS["bg_elevated"],
                    arrowcolor=COLORS["text_tertiary"],
                    width=8)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()
        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=220)
        body.columnconfigure(1, weight=3)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)
        self._build_sidebar(body)
        self._build_editor_panel(body)
        self._build_chat_panel(body)
        self._build_statusbar()

    # ── toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=COLORS["bg_elevated"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="AI Bootcamp", bg=COLORS["bg_elevated"],
                 fg=COLORS["text_primary"],
                 font=(FONT_TITLE[0], 15, "bold"), padx=20).pack(side="left")
        tk.Label(bar, text="Ollama Studio", bg=COLORS["bg_elevated"],
                 fg=COLORS["text_tertiary"],
                 font=FONT_BODY_S, padx=4).pack(side="left")

        name_frame = tk.Frame(bar, bg=COLORS["bg_elevated"])
        name_frame.pack(side="left", padx=(40, 0))
        tk.Label(name_frame, text="Model", bg=COLORS["bg_elevated"],
                 fg=COLORS["text_tertiary"],
                 font=FONT_SMALL).pack(side="left", padx=(0, 6))
        ttk.Entry(name_frame, textvariable=self.model_name, width=16).pack(
            side="left", ipady=3)

        self.status_pill = tk.Label(bar, text="  Checking…",
                                    bg=COLORS["bg_elevated"],
                                    fg=COLORS["text_tertiary"],
                                    font=FONT_SMALL, padx=16)
        self.status_pill.pack(side="right")

        self._btn_run = self._make_toolbar_btn(bar, "Run",
                                               COLORS["accent_blue"], self._run_model)
        self._btn_run.pack(side="right", padx=(0, 8), pady=10)
        self._btn_train = self._make_toolbar_btn(bar, "Train",
                                                 COLORS["accent_green"], self._train_model)
        self._btn_train.pack(side="right", padx=(0, 4), pady=10)

    def _make_toolbar_btn(self, parent, text, color, cmd):
        btn = tk.Button(parent, text=text, bg=color, fg="white",
                        font=(FONT_BOLD[0], 10, "bold"),
                        relief="flat", cursor="hand2",
                        padx=20, pady=6,
                        activebackground=color, activeforeground="white",
                        command=cmd, highlightthickness=0, bd=0)
        darker = self._darken(color, 0.15)
        btn.bind("<Enter>", lambda e, b=btn, c=darker: b.config(bg=c))
        btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))
        return btn

    @staticmethod
    def _darken(hex_color, factor):
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r, g, b = [max(0, int(c * (1 - factor))) for c in (r, g, b)]
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        side = tk.Frame(parent, bg=COLORS["bg_base"], width=220)
        side.grid(row=0, column=0, sticky="nsew")
        side.pack_propagate(False)
        tk.Frame(side, bg=COLORS["border_subtle"], width=1).pack(side="right", fill="y")

        inner = tk.Frame(side, bg=COLORS["bg_base"])
        inner.pack(fill="both", expand=True, padx=0, pady=12)

        self._section_label(inner, "MODELFILE")
        self._sidebar_btn(inner, "Open…", self._open_modelfile)
        self._sidebar_btn(inner, "Save As…", self._save_modelfile)

        self._section_label(inner, "OLLAMA")
        self._sidebar_btn(inner, "List Models", self._list_models)
        self._sidebar_btn(inner, "Delete Model", self._delete_model)

        self._section_label(inner, "INSTALLED")
        self.models_frame = tk.Frame(inner, bg=COLORS["bg_base"])
        self.models_frame.pack(fill="x", padx=16)
        self.models_label = tk.Label(self.models_frame, text="loading…",
                                     bg=COLORS["bg_base"],
                                     fg=COLORS["text_tertiary"],
                                     font=FONT_SMALL, anchor="w")
        self.models_label.pack(anchor="w")

        # Capabilities at bottom
        tk.Frame(inner, bg=COLORS["bg_base"]).pack(fill="both", expand=True)
        cap = "CPU · RAM"
        if HAS_GPU:
            cap += " · GPU"
        if not HAS_PSUTIL:
            cap = "pip install psutil\nfor system monitoring"
        tk.Label(inner, text=cap, bg=COLORS["bg_base"],
                 fg=COLORS["text_tertiary"], font=FONT_TINY,
                 padx=16, pady=8, justify="left").pack(anchor="w")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=COLORS["bg_base"],
                 fg=COLORS["text_tertiary"],
                 font=(FONT_SMALL[0], 8, "bold"),
                 padx=16).pack(anchor="w", pady=(16, 4))

    def _sidebar_btn(self, parent, text, cmd):
        btn = tk.Label(parent, text=text, bg=COLORS["bg_base"],
                       fg=COLORS["text_secondary"], font=FONT_BODY_S,
                       padx=24, pady=5, cursor="hand2", anchor="w")
        btn.pack(fill="x")
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.config(bg=COLORS["bg_hover"],
                                                 fg=COLORS["text_primary"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=COLORS["bg_base"],
                                                 fg=COLORS["text_secondary"]))

    # ── editor panel ──────────────────────────────────────────────────────────
    def _build_editor_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["bg_elevated"])
        panel.grid(row=0, column=1, sticky="nsew")

        tab_bar = tk.Frame(panel, bg=COLORS["bg_base"], height=40)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._editor_tabs = {}
        self._active_tab = tk.StringVar(value="editor")
        for tab_id, label in [("editor", "Modelfile"), ("log", "Build Log")]:
            t = tk.Label(tab_bar, text=f"  {label}  ", bg=COLORS["bg_base"],
                         fg=COLORS["text_tertiary"], font=FONT_BODY_S,
                         pady=10, padx=8, cursor="hand2")
            t.pack(side="left")
            t.bind("<Button-1>", lambda e, tid=tab_id: self._switch_tab(tid))
            self._editor_tabs[tab_id] = t

        self.autosave_label = tk.Label(tab_bar, text="", bg=COLORS["bg_base"],
                                       fg=COLORS["text_tertiary"],
                                       font=FONT_SMALL, padx=12)
        self.autosave_label.pack(side="right")

        self._tab_frames = {}
        editor_frame = tk.Frame(panel, bg=COLORS["bg_base"])
        self._tab_frames["editor"] = editor_frame
        self._build_editor(editor_frame)

        log_frame = tk.Frame(panel, bg=COLORS["bg_base"])
        self._tab_frames["log"] = log_frame
        self._build_log(log_frame)
        self._switch_tab("editor")

    def _switch_tab(self, tab_id):
        self._active_tab.set(tab_id)
        for tid, frame in self._tab_frames.items():
            frame.pack_forget()
        self._tab_frames[tab_id].pack(fill="both", expand=True)
        for tid, label in self._editor_tabs.items():
            if tid == tab_id:
                label.config(bg=COLORS["bg_elevated"], fg=COLORS["accent_blue"])
            else:
                label.config(bg=COLORS["bg_base"], fg=COLORS["text_tertiary"])

    def _build_editor(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg_elevated"])
        frame.pack(fill="both", expand=True)
        self.line_numbers = tk.Text(frame, width=4, bg=COLORS["bg_elevated"],
                                    fg=COLORS["text_tertiary"], font=FONT_MONO_S,
                                    state="disabled", relief="flat", cursor="arrow",
                                    selectbackground=COLORS["bg_elevated"],
                                    padx=8, pady=12)
        self.line_numbers.pack(side="left", fill="y")

        vscroll = ttk.Scrollbar(frame, orient="vertical")
        vscroll.pack(side="right", fill="y")

        self.editor = tk.Text(frame, bg=COLORS["bg_elevated"],
                              fg=COLORS["text_primary"], font=FONT_MONO,
                              insertbackground=COLORS["accent_blue"],
                              selectbackground=COLORS["bg_active"],
                              relief="flat", wrap="none", undo=True,
                              yscrollcommand=lambda *a: (vscroll.set(*a),
                                                         self._update_linenos()),
                              padx=8, pady=12, tabs=("4c",), insertwidth=2)
        self.editor.pack(side="left", fill="both", expand=True)
        vscroll.config(command=self._editor_scroll)

        self.editor.insert("1.0", DEFAULT_MODELFILE)
        self.editor.bind("<KeyRelease>", self._on_editor_change)
        self.editor.bind("<MouseWheel>", lambda e: self._update_linenos())
        self._update_linenos()

    def _editor_scroll(self, *args):
        self.editor.yview(*args)
        self.line_numbers.yview(*args)

    def _update_linenos(self):
        content = self.editor.get("1.0", "end-1c")
        line_count = content.count("\n") + 1
        nums = "\n".join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", nums)
        self.line_numbers.config(state="disabled")

    def _on_editor_change(self, event=None):
        self._apply_syntax()
        self._update_linenos()
        self.current_model_trained = False
        self._schedule_autosave()

    def _build_log(self, parent):
        self.build_log = tk.Text(parent, bg=COLORS["bg_elevated"],
                                 fg=COLORS["text_primary"], font=FONT_MONO_S,
                                 relief="flat", state="disabled",
                                 padx=16, pady=12, wrap="word")
        self.build_log.pack(fill="both", expand=True)
        for tag, color in [("ok", "accent_green"), ("err", "accent_red"),
                           ("info", "accent_blue"), ("warn", "accent_orange"),
                           ("cmd", "accent_orange"), ("dim", "text_tertiary")]:
            self.build_log.tag_config(tag, foreground=COLORS[color])

    # ── chat panel ────────────────────────────────────────────────────────────
    def _build_chat_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["bg_base"])
        panel.grid(row=0, column=2, sticky="nsew", padx=(1, 0))

        # Header
        header = tk.Frame(panel, bg=COLORS["bg_base"], height=40)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="Chat", bg=COLORS["bg_base"],
                 fg=COLORS["text_primary"], font=FONT_TITLE,
                 padx=16).pack(side="left")
        self.chat_model_label = tk.Label(header, text="", bg=COLORS["bg_base"],
                                         fg=COLORS["text_tertiary"],
                                         font=FONT_SMALL)
        self.chat_model_label.pack(side="left", padx=4)

        session_frame = tk.Frame(header, bg=COLORS["bg_base"])
        session_frame.pack(side="right", padx=8)
        for text, cmd in [("Stats", self._show_stats),
                          ("Export", self._export_chat),
                          ("Clear", self._clear_chat)]:
            b = tk.Label(session_frame, text=text, bg=COLORS["bg_base"],
                         fg=COLORS["text_tertiary"], font=FONT_SMALL,
                         padx=8, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, l=b: l.config(fg=COLORS["accent_blue"]))
            b.bind("<Leave>", lambda e, l=b: l.config(fg=COLORS["text_tertiary"]))

        tk.Frame(panel, bg=COLORS["border_subtle"], height=1).pack(fill="x")

        # Messages
        self.chat_display = tk.Text(panel, bg=COLORS["bg_base"],
                                    fg=COLORS["text_primary"], font=FONT_MONO_S,
                                    relief="flat", state="disabled",
                                    padx=16, pady=12, wrap="word",
                                    spacing1=2, spacing3=2)
        self.chat_display.pack(fill="both", expand=True)
        self._setup_chat_tags()

        # ── System monitor strip ──────────────────────────────────────────────
        self.monitor_frame = tk.Frame(panel, bg=COLORS["bg_base"])
        self.monitor_frame.pack(fill="x", padx=12, pady=(4, 0))

        self._gauges = {}

        if HAS_PSUTIL:
            self._gauges["cpu"] = MiniGauge(self.monitor_frame, "CPU",
                                            COLORS["gauge_cpu"], gauge_width=110)
            self._gauges["cpu"].pack(side="left", padx=(0, 6))

            self._gauges["ram"] = MemGauge(self.monitor_frame, "RAM",
                                           COLORS["gauge_ram"], gauge_width=130)
            self._gauges["ram"].pack(side="left", padx=(0, 6))

        if HAS_GPU:
            self._gauges["gpu"] = MiniGauge(self.monitor_frame, "GPU",
                                            COLORS["gauge_gpu"], gauge_width=110)
            self._gauges["gpu"].pack(side="left", padx=(0, 6))

            self._gauges["vram"] = MemGauge(self.monitor_frame, "VRAM",
                                            COLORS["gauge_vram"], gauge_width=130)
            self._gauges["vram"].pack(side="left", padx=(0, 6))

        self.peak_label = tk.Label(self.monitor_frame, text="",
                                   bg=COLORS["bg_base"],
                                   fg=COLORS["text_tertiary"], font=FONT_TINY)
        self.peak_label.pack(side="right", padx=4)

        if not self._gauges:
            tk.Label(self.monitor_frame,
                     text="Install psutil for live system metrics",
                     bg=COLORS["bg_base"], fg=COLORS["text_tertiary"],
                     font=FONT_TINY).pack(side="left")

        # Input area
        input_wrapper = tk.Frame(panel, bg=COLORS["bg_base"])
        input_wrapper.pack(fill="x", padx=12, pady=(6, 12))

        input_bg = tk.Frame(input_wrapper, bg=COLORS["bg_surface"],
                            highlightbackground=COLORS["border"],
                            highlightthickness=1)
        input_bg.pack(fill="x")

        self.chat_input = tk.Text(input_bg, bg=COLORS["bg_surface"],
                                  fg=COLORS["text_primary"], font=FONT_MONO_S,
                                  insertbackground=COLORS["accent_blue"],
                                  relief="flat", height=3,
                                  padx=12, pady=10, wrap="word", insertwidth=2)
        self.chat_input.pack(fill="x", side="left", expand=True)
        self.chat_input.bind("<Return>", self._on_enter)
        self.chat_input.bind("<Shift-Return>", lambda e: None)

        tk.Button(input_bg, text="↑", bg=COLORS["accent_blue"], fg="white",
                  font=(FONT_BOLD[0], 14, "bold"), relief="flat",
                  cursor="hand2", width=3, height=1,
                  command=self._send_message,
                  activebackground=self._darken(COLORS["accent_blue"], 0.15),
                  activeforeground="white",
                  bd=0, highlightthickness=0).pack(side="right", padx=6, pady=6)

        self.metrics_label = tk.Label(panel, text="Send a message to test your model",
                                      bg=COLORS["bg_base"],
                                      fg=COLORS["text_tertiary"],
                                      font=FONT_SMALL, pady=4)
        self.metrics_label.pack()

    def _setup_chat_tags(self):
        d = self.chat_display
        d.tag_config("user_name",  foreground=COLORS["accent_blue"],
                     font=(FONT_MONO_S[0], FONT_MONO_S[1], "bold"))
        d.tag_config("user_text",  foreground=COLORS["text_primary"])
        d.tag_config("ai_name",    foreground=COLORS["accent_green"],
                     font=(FONT_MONO_S[0], FONT_MONO_S[1], "bold"))
        d.tag_config("ai_text",    foreground="#d1d1d6")
        d.tag_config("ts",         foreground=COLORS["text_tertiary"],
                     font=(FONT_SMALL[0], 9))
        d.tag_config("metrics",    foreground=COLORS["accent_orange"],
                     font=(FONT_SMALL[0], 9))
        d.tag_config("separator",  foreground=COLORS["border_subtle"])

    # ── status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=COLORS["bg_elevated"], height=26)
        bar.pack(fill="x", side="bottom")
        self.status_left = tk.Label(bar, text="Ready", bg=COLORS["bg_elevated"],
                                    fg=COLORS["text_tertiary"],
                                    font=FONT_SMALL, padx=12)
        self.status_left.pack(side="left")
        self.status_right = tk.Label(bar, text="", bg=COLORS["bg_elevated"],
                                     fg=COLORS["text_tertiary"],
                                     font=FONT_SMALL, padx=12)
        self.status_right.pack(side="right")

    # ── system monitor ────────────────────────────────────────────────────────
    def _start_monitor(self):
        if self._monitor_active:
            return
        self._monitor_active = True
        self._peak_cpu = 0.0
        self._peak_ram = 0.0
        self._peak_gpu = 0.0

        def poll():
            while self._monitor_active:
                try:
                    if HAS_PSUTIL:
                        cpu = psutil.cpu_percent(interval=0.3)
                        mem = psutil.virtual_memory()
                        self._peak_cpu = max(self._peak_cpu, cpu)
                        self._peak_ram = max(self._peak_ram, mem.percent)
                        self.after(0, lambda c=cpu, m=mem: self._update_cpu_ram(c, m))
                    else:
                        time.sleep(0.3)

                    if HAS_GPU:
                        gpu_data = _read_gpu()
                        if gpu_data:
                            self._peak_gpu = max(self._peak_gpu, gpu_data[0])
                            self.after(0, lambda g=gpu_data: self._update_gpu(g))
                except Exception:
                    time.sleep(0.5)

        threading.Thread(target=poll, daemon=True).start()

    def _stop_monitor(self):
        self._monitor_active = False
        parts = []
        if HAS_PSUTIL:
            parts.append(f"Peak CPU {self._peak_cpu:.0f}%")
            parts.append(f"RAM {self._peak_ram:.0f}%")
        if HAS_GPU and self._peak_gpu > 0:
            parts.append(f"GPU {self._peak_gpu:.0f}%")
        if parts:
            self.peak_label.config(text="  ".join(parts))

    def _update_cpu_ram(self, cpu, mem):
        if "cpu" in self._gauges:
            self._gauges["cpu"].set_value(cpu)
        if "ram" in self._gauges:
            self._gauges["ram"].set_value(
                int(mem.used / (1024 * 1024)),
                int(mem.total / (1024 * 1024)))

    def _update_gpu(self, gpu_data):
        gpu_pct, vram_used, vram_total = gpu_data
        if "gpu" in self._gauges:
            self._gauges["gpu"].set_value(gpu_pct)
        if "vram" in self._gauges:
            self._gauges["vram"].set_value(vram_used, vram_total)

    def _animate_gauges(self):
        for g in self._gauges.values():
            g.animate_step()
        self.after(33, self._animate_gauges)

    # ── syntax highlighting ───────────────────────────────────────────────────
    def _apply_syntax(self):
        e = self.editor
        for tag in ["kw_from", "kw_system", "kw_param", "str_val", "comment", "number"]:
            e.tag_remove(tag, "1.0", "end")
        e.tag_config("kw_from",   foreground=COLORS["syn_keyword"],
                     font=(FONT_MONO[0], FONT_MONO[1], "bold"))
        e.tag_config("kw_system", foreground=COLORS["syn_keyword"],
                     font=(FONT_MONO[0], FONT_MONO[1], "bold"))
        e.tag_config("kw_param",  foreground=COLORS["syn_param"])
        e.tag_config("str_val",   foreground=COLORS["syn_string"])
        e.tag_config("comment",   foreground=COLORS["syn_comment"])
        e.tag_config("number",    foreground=COLORS["syn_number"])

        content = e.get("1.0", "end")
        lines = content.split("\n")
        patterns = [
            ("kw_from",   r"^FROM\b"),
            ("kw_system", r"^SYSTEM\b"),
            ("kw_param",  r"^PARAMETER\b"),
            ("comment",   r"#.*$"),
            ("number",    r"\b\d+\.?\d*\b"),
        ]
        for lineno, line in enumerate(lines, start=1):
            for tag, pattern in patterns:
                for m in re.finditer(pattern, line,
                                     re.IGNORECASE if tag == "kw_from" else 0):
                    e.tag_add(tag, f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")
            for m in re.finditer(r'""".*?"""', line):
                e.tag_add("str_val", f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")

    # ── autosave ──────────────────────────────────────────────────────────────
    def _schedule_autosave(self):
        if self._autosave_pending:
            self.after_cancel(self._autosave_pending)
        self._autosave_pending = self.after(1500, self._do_autosave)
        self.autosave_label.config(text="Editing…", fg=COLORS["text_tertiary"])

    def _do_autosave(self):
        self._autosave_pending = None
        name = self.model_name.get().strip() or "untitled"
        safe_name = re.sub(r'[^\w\-.]', '_', name)
        path = AUTOSAVE_DIR / f"{safe_name}.md"
        content = self.editor.get("1.0", "end-1c")
        try:
            path.write_text(content, encoding="utf-8")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.autosave_label.config(text=f"Saved {ts}",
                                       fg=COLORS["accent_green"])
        except Exception:
            self.autosave_label.config(text="Save failed",
                                       fg=COLORS["accent_red"])

    def _load_last_modelfile(self):
        try:
            files = list(AUTOSAVE_DIR.glob("*.md"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                content = latest.read_text(encoding="utf-8")
                self.editor.delete("1.0", "end")
                self.editor.insert("1.0", content)
                self._apply_syntax()
                self._update_linenos()
                self.model_name.set(latest.stem)
                self._set_status(f"Loaded: {latest.name}", "ok")
        except Exception:
            pass

    # ── ollama ────────────────────────────────────────────────────────────────
    def _check_ollama(self):
        def run():
            try:
                r = subprocess.run(["ollama", "list"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    self.after(0, lambda: self.status_pill.config(
                        text="  Ollama running", fg=COLORS["accent_green"]))
                    lines = [l.strip() for l in r.stdout.strip().split("\n")[1:]
                             if l.strip()]
                    names = [l.split()[0] for l in lines if l]
                    self.after(0, lambda: self._update_models_list(names))
                else:
                    self.after(0, lambda: self.status_pill.config(
                        text="  Ollama not found", fg=COLORS["accent_red"]))
            except Exception:
                self.after(0, lambda: self.status_pill.config(
                    text="  Ollama unavailable", fg=COLORS["accent_red"]))
        threading.Thread(target=run, daemon=True).start()

    def _update_models_list(self, names):
        for w in self.models_frame.winfo_children():
            w.destroy()
        if not names:
            tk.Label(self.models_frame, text="none installed",
                     bg=COLORS["bg_base"], fg=COLORS["text_tertiary"],
                     font=FONT_SMALL).pack(anchor="w")
            return
        for n in names:
            lbl = tk.Label(self.models_frame, text=n, bg=COLORS["bg_base"],
                           fg=COLORS["text_secondary"], font=FONT_MONO_S,
                           anchor="w", cursor="hand2", padx=4, pady=1)
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda e, name=n: self.model_name.set(name))
            lbl.bind("<Enter>", lambda e, l=lbl: l.config(fg=COLORS["accent_blue"]))
            lbl.bind("<Leave>", lambda e, l=lbl: l.config(fg=COLORS["text_secondary"]))

    # ── train ─────────────────────────────────────────────────────────────────
    def _train_model(self):
        if self.train_running:
            return
        name = self.model_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a model name first.")
            return
        raw = self.editor.get("1.0", "end").strip()
        editor_content = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("#"))
        tmp_path = Path.home() / f".ai_bootcamp_{name}_Modelfile"
        tmp_path.write_text(editor_content, encoding="utf-8")
        self.modelfile_path = str(tmp_path)

        self.train_running = True
        self._btn_train.config(text="Training…", state="disabled")
        self._switch_tab("log")
        self._log("", "")
        self._log(f"Training model: {name}", "info")
        self._log(f"Modelfile: {tmp_path}", "dim")
        self._log("─" * 50, "dim")

        def run():
            try:
                cmd = ["ollama", "create", name, "-f", str(tmp_path)]
                self.after(0, lambda: self._log(f"$ {' '.join(cmd)}", "cmd"))
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    line = line.rstrip()
                    tag = "ok" if "success" in line.lower() else \
                          "err" if "error" in line.lower() else "info"
                    self.after(0, lambda l=line, t=tag: self._log(l, t))
                proc.wait()
                if proc.returncode == 0:
                    self.after(0, self._train_success)
                else:
                    self.after(0, lambda: self._train_error("Build failed."))
            except FileNotFoundError:
                self.after(0, lambda: self._train_error("ollama not found."))
            except Exception as ex:
                self.after(0, lambda: self._train_error(str(ex)))
        threading.Thread(target=run, daemon=True).start()

    def _train_success(self):
        name = self.model_name.get().strip()
        self._log("─" * 50, "dim")
        self._log(f"✓ Model '{name}' ready", "ok")
        self._btn_train.config(text="Train", state="normal")
        self.train_running = False
        self.current_model_trained = True
        self._set_status(f"Model '{name}' ready", "ok")
        self._check_ollama()
        self.chat_model_label.config(text=name, fg=COLORS["accent_green"])

    def _train_error(self, msg):
        self._log(f"✗ {msg}", "err")
        self._btn_train.config(text="Train", state="normal")
        self.train_running = False
        self._set_status(f"Failed: {msg}", "err")

    # ── run ───────────────────────────────────────────────────────────────────
    def _run_model(self):
        name = self.model_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a model name first.")
            return
        if not self.current_model_trained:
            if not messagebox.askyesno("Not trained",
                    f"Model '{name}' may not be current.\nRun anyway?"):
                return
        self._launch_terminal(name)

    def _launch_terminal(self, name):
        cmd_str = f"ollama run {name}"
        try:
            if os.name == "nt":
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", cmd_str])
            elif os.path.exists("/usr/bin/gnome-terminal"):
                subprocess.Popen(["gnome-terminal", "--", "bash", "-c",
                                  f"{cmd_str}; exec bash"])
            elif os.path.exists("/usr/bin/xterm"):
                subprocess.Popen(["xterm", "-e", f"{cmd_str}; bash"])
            elif os.path.exists("/usr/bin/osascript"):
                subprocess.Popen(["osascript", "-e",
                    f'tell app "Terminal" to do script "{cmd_str}"'])
            else:
                messagebox.showinfo("Run Model",
                    f"Open a terminal and run:\n\n{cmd_str}")
        except Exception as e:
            messagebox.showinfo("Run Model",
                f"Run manually:\n{cmd_str}\n\nError: {e}")

    # ── chat ──────────────────────────────────────────────────────────────────
    def _on_enter(self, event):
        if not (event.state & 0x1):
            self._send_message()
            return "break"

    def _send_message(self):
        msg = self.chat_input.get("1.0", "end").strip()
        if not msg:
            return
        name = self.model_name.get().strip()
        if not name:
            messagebox.showerror("Error", "No model name set.")
            return

        self.chat_input.delete("1.0", "end")
        self._append_chat("You", msg, "user_name", "user_text")
        self.chat_history.append({"role": "user", "content": msg})
        self.metrics_label.config(text="Waiting…")
        self.peak_label.config(text="")

        # Start monitoring
        self._start_monitor()

        def run():
            try:
                start = time.time()
                # Use Ollama REST API with full conversation history
                payload = json.dumps({
                    "model": name,
                    "messages": list(self.chat_history),
                    "stream": False
                }).encode("utf-8")
                req = urllib.request.Request(
                    "http://localhost:11434/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - start
                response = data.get("message", {}).get("content", "").strip()
                if not response:
                    response = "[Empty response from model]"
                words = len(response.split())
                wps = round(words / elapsed, 1) if elapsed > 0 else 0

                self.chat_history.append({"role": "assistant", "content": response})
                record = {
                    "ts": datetime.datetime.now().isoformat(),
                    "user": msg, "response": response,
                    "elapsed": round(elapsed, 2), "words": words,
                    "tok_per_sec": wps,
                    "peak_cpu": round(self._peak_cpu, 1),
                    "peak_ram": round(self._peak_ram, 1),
                    "peak_gpu": round(self._peak_gpu, 1),
                }
                self.response_log.append(record)
                self.after(0, lambda: self._on_response(response, elapsed,
                                                        words, wps))
            except urllib.error.URLError as ex:
                self.after(0, lambda: self._on_response(
                    f"[Can't reach Ollama at localhost:11434 — is it running?]",
                    0, 0, 0))
            except Exception as ex:
                self.after(0, lambda: self._on_response(f"[Error: {ex}]",
                                                        0, 0, 0))
        threading.Thread(target=run, daemon=True).start()

    def _on_response(self, text, elapsed, words, wps):
        self._stop_monitor()
        self._append_chat(self.model_name.get(), text, "ai_name", "ai_text",
                          metrics=f"  {elapsed:.1f}s · {words}w · ~{wps} w/s")
        self.metrics_label.config(
            text=f"{elapsed:.1f}s · {words} words · ~{wps} w/s")

    def _append_chat(self, name, text, name_tag, text_tag, metrics=None):
        d = self.chat_display
        d.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M")
        d.insert("end", f"\n{name}  ", name_tag)
        d.insert("end", f"{ts}\n", "ts")
        d.insert("end", text + "\n", text_tag)
        if metrics:
            d.insert("end", metrics + "\n", "metrics")
        d.insert("end", "\n", "separator")
        d.config(state="disabled")
        d.see("end")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _log(self, text, tag="info"):
        self.build_log.config(state="normal")
        self.build_log.insert("end", text + "\n", tag)
        self.build_log.config(state="disabled")
        self.build_log.see("end")

    def _set_status(self, msg, level="info"):
        colors = {"ok": COLORS["accent_green"], "err": COLORS["accent_red"],
                  "info": COLORS["accent_blue"], "warn": COLORS["accent_orange"]}
        self.status_left.config(text=msg,
                                fg=colors.get(level, COLORS["text_tertiary"]))

    def _save_modelfile(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialfile=f"{self.model_name.get().strip() or 'Modelfile'}.md",
            filetypes=[("Markdown", "*.md"), ("All Files", "*.*")])
        if path:
            Path(path).write_text(self.editor.get("1.0", "end-1c"),
                                  encoding="utf-8")
            self._set_status(f"Saved: {path}", "ok")

    def _open_modelfile(self):
        path = filedialog.askopenfilename(
            filetypes=[("Markdown", "*.md"), ("Modelfile", "*"),
                       ("All Files", "*.*")])
        if path:
            content = Path(path).read_text(encoding="utf-8")
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", content)
            self._apply_syntax()
            self._update_linenos()
            self._set_status(f"Opened: {path}", "ok")

    def _list_models(self):
        def run():
            try:
                r = subprocess.run(["ollama", "list"],
                                   capture_output=True, text=True, timeout=8)
                self.after(0, lambda: messagebox.showinfo("Installed Models",
                    r.stdout if r.stdout else "No models found."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _delete_model(self):
        name = self.model_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Set a model name first.")
            return
        if messagebox.askyesno("Delete Model",
                               f"Delete '{name}'? This can't be undone."):
            def run():
                try:
                    r = subprocess.run(["ollama", "rm", name],
                                       capture_output=True, text=True)
                    msg = r.stdout or r.stderr or f"Deleted {name}"
                    self.after(0, lambda: messagebox.showinfo("Deleted", msg))
                    self.after(0, self._check_ollama)
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Error", str(e)))
            threading.Thread(target=run, daemon=True).start()

    def _export_chat(self):
        if not self.response_log:
            messagebox.showinfo("Export", "No responses recorded yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile="chat_log.json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            Path(path).write_text(
                json.dumps(self.response_log, indent=2), encoding="utf-8")
            self._set_status(
                f"Exported {len(self.response_log)} records", "ok")

    def _clear_chat(self):
        if messagebox.askyesno("Clear Chat", "Clear all chat history?"):
            self.chat_history.clear()
            self.response_log.clear()
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.config(state="disabled")
            self.metrics_label.config(text="Send a message to test your model")
            self.peak_label.config(text="")
            for g in self._gauges.values():
                if isinstance(g, MemGauge):
                    g.set_value(0, 0)
                else:
                    g.set_value(0)

    def _show_stats(self):
        if not self.response_log:
            messagebox.showinfo("Stats", "No responses yet.")
            return
        n = len(self.response_log)
        avg_t = sum(r["elapsed"] for r in self.response_log) / n
        avg_w = sum(r["words"] for r in self.response_log) / n
        avg_s = sum(r["tok_per_sec"] for r in self.response_log) / n
        msg = (f"Responses:   {n}\n"
               f"Avg time:    {avg_t:.2f}s\n"
               f"Avg words:   {avg_w:.1f}\n"
               f"Avg speed:   {avg_s:.1f} w/s\n")
        peak_cpus = [r.get("peak_cpu", 0) for r in self.response_log]
        peak_rams = [r.get("peak_ram", 0) for r in self.response_log]
        peak_gpus = [r.get("peak_gpu", 0) for r in self.response_log]
        if any(peak_cpus):
            msg += f"\nAvg peak CPU:  {sum(peak_cpus)/n:.1f}%"
            msg += f"\nMax peak CPU:  {max(peak_cpus):.1f}%"
        if any(peak_rams):
            msg += f"\nAvg peak RAM:  {sum(peak_rams)/n:.1f}%"
        if any(peak_gpus):
            msg += f"\nAvg peak GPU:  {sum(peak_gpus)/n:.1f}%"
            msg += f"\nMax peak GPU:  {max(peak_gpus):.1f}%"
        messagebox.showinfo("Stats", msg)


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AIBootcamp()
    app.mainloop()