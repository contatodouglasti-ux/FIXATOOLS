"""Aplicativo visual unificado das ferramentas do FIXATOOLS."""

import tkinter as tk
from tkinter import ttk

from erroForo import BotReprocessamento
from resettools import ResetTool


def main():
    root = tk.Tk()
    root.title("FIXATOOLS")
    root.geometry("1280x820")
    root.minsize(1000, 650)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    cabecalho = ttk.Frame(root, padding=(12, 10, 12, 4))
    cabecalho.pack(fill="x")
    ttk.Label(
        cabecalho,
        text="FIXATOOLS",
        font=("Segoe UI", 16, "bold"),
    ).pack(side="left")
    ttk.Label(
        cabecalho,
        text="Ferramentas de reprocessamento e reset",
        padding=(12, 4, 0, 0),
    ).pack(side="left")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    aba_erro_foro = ttk.Frame(notebook)
    aba_reset = ttk.Frame(notebook)
    notebook.add(aba_erro_foro, text="Erro Foro")
    notebook.add(aba_reset, text="Reset em Lote")

    # Cada classe continua responsável pelo próprio fluxo, mas compartilha
    # a mesma janela, o mesmo arquivo de configuração e o mesmo processo.
    BotReprocessamento(root, aba_erro_foro)
    ResetTool(root, aba_reset)

    ttk.Label(
        root,
        text="As credenciais são compartilhadas entre as duas ferramentas.",
        padding=(12, 0, 12, 6),
    ).pack(anchor="w")

    root.mainloop()


if __name__ == "__main__":
    main()
