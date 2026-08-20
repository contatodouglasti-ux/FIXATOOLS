"""Estilos compartilhados da interface do FIXATOOLS."""

import tkinter as tk
from tkinter import ttk


COLORS = {
    "background": "#f4f6f8",
    "surface": "#ffffff",
    "border": "#d9e0e8",
    "text": "#172033",
    "muted": "#64748b",
    "primary": "#2563eb",
    "primary_active": "#1d4ed8",
    "success_bg": "#ecfdf5",
    "success_text": "#047857",
    "warning_bg": "#fffbeb",
    "warning_text": "#b45309",
}


def aplicar_tema(root):
    """Configura o tema comum, inclusive quando uma ferramenta é aberta sozinha."""
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("App.TFrame", background=COLORS["background"])
    style.configure("Toolbar.TFrame", background="#eaf0f7")
    style.configure("Card.TFrame", background=COLORS["surface"])
    style.configure(
        "Card.TLabelframe",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=("Segoe UI", 10, "bold"),
    )
    style.configure(
        "Title.TLabel",
        background=COLORS["background"],
        foreground=COLORS["text"],
        font=("Segoe UI", 15, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=COLORS["background"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Hint.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 9),
    )
    style.configure(
        "Stat.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=("Segoe UI", 10, "bold"),
        padding=(12, 10),
    )
    style.configure(
        "Success.Stat.TLabel",
        background=COLORS["success_bg"],
        foreground=COLORS["success_text"],
        font=("Segoe UI", 10, "bold"),
        padding=(12, 10),
    )
    style.configure(
        "Warning.Stat.TLabel",
        background=COLORS["warning_bg"],
        foreground=COLORS["warning_text"],
        font=("Segoe UI", 10, "bold"),
        padding=(12, 10),
    )
    style.configure(
        "Primary.TButton",
        padding=(14, 8),
        font=("Segoe UI", 10, "bold"),
        foreground="#ffffff",
        background=COLORS["primary"],
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLORS["primary_active"]), ("disabled", "#b8c4d4")],
        foreground=[("disabled", "#f8fafc")],
    )
    style.configure(
        "Secondary.TButton",
        padding=(12, 7),
        font=("Segoe UI", 9),
    )
    style.configure(
        "Schedule.TButton",
        padding=(12, 7),
        font=("Segoe UI", 9, "bold"),
    )
    style.configure(
        "TNotebook",
        background=COLORS["background"],
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )
    style.configure(
        "TNotebook.Tab",
        padding=(18, 9),
        font=("Segoe UI", 10, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=COLORS["background"],
        foreground=COLORS["muted"],
        font=("Segoe UI", 8),
    )

    root.configure(background=COLORS["background"])
    return style
