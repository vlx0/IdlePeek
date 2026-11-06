"""IdlePeek GUI."""

from __future__ import annotations

import ctypes
import threading
import tkinter as tk
from tkinter import ttk

from . import __version__
from .idle import Snap, format_span, leftover, overdue, sample
from .instance import WINDOW_TITLE
from .settings import INTERVALS, load_interval, save_interval

BG = "#111111"
FG = "#ffffff"
MUTED = "#999999"
CARD = "#1a1a1a"
BTN = "#333333"
ACCENT = "#93c5fd"
OK = "#86efac"
HOT = "#fde68a"
BAD = "#fca5a5"


def _headline(snap: Snap) -> tuple[str, str]:
    if snap.idle_sec is None:
        return snap.error or "время простоя не прочиталось.", BAD
    if snap.error and snap.sleep_sec is None and snap.display_sec is None:
        return snap.error, BAD
    idle = format_span(snap.idle_sec)
    if overdue(snap.idle_sec, snap.sleep_sec):
        return f"Простой {idle}. Сон уже должен был наступить.", BAD
    if overdue(snap.idle_sec, snap.display_sec):
        return f"Простой {idle}. Экран уже должен был погаснуть.", HOT
    if snap.sleep_sec == 0 and snap.display_sec == 0:
        return f"Простой {idle}. Сон и экран в схеме выключены.", HOT
    if snap.display_sec and snap.display_sec > 0:
        return f"Простой {idle}. Экран {leftover(snap.idle_sec, snap.display_sec)}.", OK
    if snap.sleep_sec and snap.sleep_sec > 0:
        return f"Простой {idle}. Сон {leftover(snap.idle_sec, snap.sleep_sec)}.", OK
    return f"Простой {idle}.", OK


class IdlePeekApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry("520x560")
        self.minsize(440, 420)
        self.configure(bg=BG)
        self._sec = load_interval()
        self._job: str | None = None
        self._busy = False
        self._layout: tuple | None = None
        self._boxes: dict[str, tuple[tk.Frame, tk.Label]] = {}

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Dark.TCombobox",
            fieldbackground=CARD, background=BTN, foreground=FG, arrowcolor=FG,
            darkcolor=CARD, lightcolor=CARD, bordercolor=BTN,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", CARD)],
            foreground=[("readonly", FG)],
            background=[("readonly", BTN)],
        )

        pad = tk.Frame(self, bg=BG)
        pad.pack(fill="both", expand=True, padx=22, pady=16)

        foot = tk.Frame(pad, bg=BG)
        foot.pack(fill="x", side="bottom", pady=(8, 0))
        tk.Label(foot, text="неделя 11 · день 75", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(foot, text=f"v{__version__} · darkshade", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
        labels = [lab for _, lab in INTERVALS]
        self._iv_var = tk.StringVar(value=next((lab for sec, lab in INTERVALS if sec == self._sec), "1 с"))
        self._iv = ttk.Combobox(
            foot, textvariable=self._iv_var, values=labels, state="readonly",
            width=6, style="Dark.TCombobox", font=("Segoe UI", 8),
        )
        self._iv.pack(side="right", padx=(0, 10))
        self._iv.bind("<<ComboboxSelected>>", lambda _e: self._on_interval())
        self._iv.bind("<MouseWheel>", lambda _e: "break")
        tk.Label(foot, text="обновление", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="right", padx=(0, 6))

        head = tk.Frame(pad, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="IdlePeek", bg=BG, fg=FG, font=("Segoe UI Semibold", 20)).pack(side="left")

        self._status = tk.Label(
            pad, text="читаю…", bg=BG, fg=FG, font=("Segoe UI", 12),
            wraplength=470, justify="left",
        )
        self._status.pack(anchor="w", pady=(8, 8))

        self._canvas = tk.Canvas(pad, bg=BG, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._list = tk.Frame(self._canvas, bg=BG)
        self._win = self._canvas.create_window((0, 0), window=self._list, anchor="nw")
        self._canvas.bind("<Configure>", self._on_canvas)
        self._list.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self.bind_all("<MouseWheel>", self._wheel)

        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(20, self._place)
        self._job = self.after(150, self._tick)

    def _on_canvas(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._win, width=event.width)

    def _wheel(self, event: tk.Event) -> str | None:
        widget = event.widget
        if isinstance(widget, str):
            return "break"
        while widget is not None:
            if widget in (self._canvas, self._list):
                self._canvas.yview_scroll(int(-event.delta / 120), "units")
                return None
            widget = getattr(widget, "master", None)
        return "break"

    def _on_interval(self) -> None:
        lab = self._iv_var.get()
        for sec, name in INTERVALS:
            if name == lab:
                self._sec = sec
                save_interval(sec)
                self._schedule(0)
                return

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._status.configure(wraplength=max(280, event.width - 48))

    def _place(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width() or 520, self.winfo_height() or 560
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 6}")

    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _close(self) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        self.destroy()

    def _schedule(self, delay_ms: int | None = None) -> None:
        if self._job:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        ms = int(self._sec * 1000) if delay_ms is None else delay_ms
        self._job = self.after(max(0, ms), self._tick)

    def _tick(self) -> None:
        if not self._alive():
            return
        if self._busy:
            self._schedule()
            return
        self._busy = True
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            snap = sample()
        except Exception:
            snap = Snap(error="Не удалось прочитать простой.")
        try:
            self.after(0, self._apply, snap)
        except tk.TclError:
            self._busy = False

    def _apply(self, snap: Snap) -> None:
        self._busy = False
        if not self._alive():
            return
        text, color = _headline(snap)
        self._status.configure(text=text, fg=color)
        if snap.idle_sec is None:
            layout = ("error", snap.error)
            if layout != self._layout or self._boxes:
                self._layout = layout
                self._render((), snap.error or "время простоя не прочиталось.")
            self._schedule()
            return
        source = "от сети" if snap.on_ac else "от батареи"
        scheme = snap.scheme or "без имени"
        if snap.away is None:
            away = "не прочитан"
        elif snap.away:
            away = "разрешён в схеме"
        else:
            away = "запрещён в схеме"
        idle = snap.idle_sec
        rows = (
            ("Простой", format_span(idle), _idle_border(snap)),
            (f"Схема «{scheme}»", f"питание {source}", MUTED),
            ("Экран", leftover(idle, snap.display_sec, "уже должен был погаснуть"), _row_border(idle, snap.display_sec)),
            ("Сон", leftover(idle, snap.sleep_sec, "уже должен был наступить"), _row_border(idle, snap.sleep_sec, sleep=True)),
            ("Гибернация", leftover(idle, snap.hibernate_sec, "уже должна была"), _row_border(idle, snap.hibernate_sec)),
            ("Режим отсутствия", away, MUTED),
        )
        layout = (scheme, source, snap.error)
        if layout != self._layout or not self._boxes:
            self._layout = layout
            self._render(rows, snap.error)
        else:
            self._paint(rows)
        self._schedule()

    def _render(self, rows: tuple, error: str) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        self._boxes = {}
        for title, body, color in rows:
            self._card(title, body, color)
        if error:
            self._muted(error)

    def _paint(self, rows: tuple) -> None:
        for title, body, color in rows:
            pair = self._boxes.get(title)
            if pair is None:
                continue
            box, lab = pair
            lab.configure(text=body, fg=color)
            box.configure(highlightbackground=color, highlightcolor=color)

    def _muted(self, text: str) -> None:
        tk.Label(
            self._list, text=text, bg=BG, fg=MUTED, font=("Segoe UI", 10),
            wraplength=440, justify="left",
        ).pack(anchor="w", pady=(0, 4))

    def _card(self, title: str, body: str, color: str) -> None:
        box = tk.Frame(
            self._list, bg=CARD, highlightthickness=2,
            highlightbackground=color, highlightcolor=color,
        )
        box.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(box, bg=CARD)
        inner.pack(fill="x", padx=12, pady=10)
        tk.Label(inner, text=title, bg=CARD, fg=FG, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
        lab = tk.Label(inner, text=body, bg=CARD, fg=color, font=("Segoe UI", 10), wraplength=440, justify="left", anchor="w")
        lab.pack(fill="x", pady=(2, 0))
        self._boxes[title] = (box, lab)


def _idle_border(snap: Snap) -> str:
    idle = snap.idle_sec or 0
    if overdue(idle, snap.sleep_sec):
        return BAD
    if overdue(idle, snap.display_sec):
        return HOT
    return OK


def _row_border(idle_sec: int, timeout_sec: int | None, sleep: bool = False) -> str:
    if overdue(idle_sec, timeout_sec):
        return BAD if sleep else HOT
    return MUTED


def run() -> None:
    IdlePeekApp().mainloop()
