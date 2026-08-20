"""Aplicativo visual unificado das ferramentas do FIXATOOLS."""

import tkinter as tk
from tkinter import ttk

from erroForo import BotReprocessamento
from resettools import ResetTool
from ui_helpers import aplicar_tema


def main():
    root = tk.Tk()
    root.title("FIXATOOLS")
    root.geometry("1280x820")
    root.minsize(1000, 650)

    aplicar_tema(root)

    cabecalho = ttk.Frame(
        root,
        style="App.TFrame",
        padding=(16, 14, 16, 4),
    )
    cabecalho.pack(fill="x")
    ttk.Label(
        cabecalho,
        text="FIXATOOLS",
        style="Title.TLabel",
    ).pack(side="left")
    ttk.Label(
        cabecalho,
        text="Ferramentas de reprocessamento e reset",
        style="Subtitle.TLabel",
        padding=(12, 4, 0, 0),
    ).pack(side="left")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=(4, 8))

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
        style="Status.TLabel",
        padding=(12, 0, 12, 6),
    ).pack(anchor="w")

    root.mainloop()


if __name__ == "__main__":
    main()
