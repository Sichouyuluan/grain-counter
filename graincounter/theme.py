"""主题定义 + 磨砂玻璃风格 widget 工厂"""
import tkinter as tk


class Theme:
    bg           = "#0d0f14"
    surface      = "#161a22"
    surface_alt  = "#1c212b"
    border       = "#262d3a"
    border_light = "#333d4d"
    text         = "#e4e8ee"
    text_dim     = "#8892a6"
    accent       = "#4ade80"
    accent_glow  = "#4ade8033"
    blue         = "#60a5fa"
    blue_glow    = "#60a5fa33"
    orange       = "#fb923c"
    red          = "#f87171"
    font         = "Microsoft YaHei"
    font_mono    = "Consolas"


def glass_frame(parent, **kw):
    kw.setdefault("bg", Theme.surface)
    kw.setdefault("highlightbackground", Theme.border)
    kw.setdefault("highlightthickness", 1)
    kw.setdefault("bd", 0)
    return tk.Frame(parent, **kw)


def glass_label(parent, text="", **kw):
    kw.setdefault("bg", Theme.surface)
    kw.setdefault("fg", Theme.text)
    kw.setdefault("font", (Theme.font, 10))
    return tk.Label(parent, text=text, **kw)


def glass_button(parent, text, color, command, **kw):
    kw.setdefault("font", (Theme.font, 10))
    kw.setdefault("relief", "flat")
    kw.setdefault("bd", 0)
    kw.setdefault("padx", 14)
    kw.setdefault("pady", 6)
    kw.setdefault("cursor", "hand2")
    kw.setdefault("activebackground", color)
    kw.setdefault("activeforeground", "#fff")
    kw.setdefault("fg", "#fff")
    return tk.Button(parent, text=text, bg=color, command=command, **kw)


def glass_entry(parent, var=None, **kw):
    kw.setdefault("bg", Theme.surface_alt)
    kw.setdefault("fg", Theme.text)
    kw.setdefault("insertbackground", Theme.text)
    kw.setdefault("font", (Theme.font_mono, 10))
    kw.setdefault("relief", "flat")
    kw.setdefault("bd", 0)
    kw.setdefault("highlightbackground", Theme.border)
    kw.setdefault("highlightthickness", 1)
    return tk.Entry(parent, textvariable=var, **kw)
