import logging
import queue
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from coleta_bi import processar


BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "logs.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS execucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL,
            status TEXT NOT NULL,
            detalhes TEXT,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def registrar_log(tipo, data_inicio, data_fim, status, detalhes):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO execucoes (tipo, data_inicio, data_fim, status, detalhes, criado_em) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            tipo,
            data_inicio.isoformat(sep=" "),
            data_fim.isoformat(sep=" "),
            status,
            detalhes,
            datetime.now().isoformat(sep=" "),
        ),
    )
    conn.commit()
    conn.close()


def formatar_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(texto):
    return datetime.strptime(texto.strip(), "%Y-%m-%d %H:%M:%S")


def inicio_fim_ultima_hora():
    agora = datetime.now()
    fim = agora.replace(minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(hours=1)
    return inicio, fim


def proxima_hora_cheia(dt):
    base = dt.replace(minute=0, second=0, microsecond=0)
    return base + timedelta(hours=1)


class AppBI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Coletor BI")
        self.geometry("1200x780")
        self.minsize(1100, 700)

        self.queue = queue.Queue()
        self.auto_stop = threading.Event()
        self.auto_thread = None
        self.auto_ativo = False
        self.ultimo_fim_auto = None

        init_db()
        self._criar_widgets()
        self.refresh_logs()
        self.after(200, self._processar_fila)

        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _criar_widgets(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        titulo = ttk.Label(container, text="Coletor BI", font=("Segoe UI", 18, "bold"))
        titulo.pack(anchor="w", pady=(0, 12))

        # ===== Consulta manual =====
        frame_manual = ttk.LabelFrame(container, text="Consulta manual", padding=10)
        frame_manual.pack(fill="x", pady=(0, 10))

        ttk.Label(frame_manual, text="Início (YYYY-MM-DD HH:MM:SS)").grid(row=0, column=0, sticky="w")
        ttk.Label(frame_manual, text="Fim (YYYY-MM-DD HH:MM:SS)").grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.inicio_var = tk.StringVar()
        self.fim_var = tk.StringVar()

        self.inicio_entry = ttk.Entry(frame_manual, textvariable=self.inicio_var, width=28)
        self.fim_entry = ttk.Entry(frame_manual, textvariable=self.fim_var, width=28)
        self.inicio_entry.grid(row=1, column=0, sticky="w", pady=(4, 8))
        self.fim_entry.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(4, 8))

        btns_manual = ttk.Frame(frame_manual)
        btns_manual.grid(row=1, column=2, padx=(15, 0), sticky="w")

        ttk.Button(btns_manual, text="Preencher última hora", command=self.preencher_ultima_hora).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(btns_manual, text="Executar manual", command=self.executar_manual).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(btns_manual, text="Executar última hora", command=self.executar_ultima_hora).grid(
            row=0, column=2
        )

        # ===== Automático =====
        frame_auto = ttk.LabelFrame(container, text="Modo automático", padding=10)
        frame_auto.pack(fill="x", pady=(0, 10))

        self.auto_var = tk.BooleanVar(value=False)
        self.auto_check = ttk.Checkbutton(
            frame_auto,
            text="Ativar modo automático",
            variable=self.auto_var,
            command=self.on_toggle_auto
        )
        self.auto_check.grid(row=0, column=0, sticky="w")

        self.status_auto_var = tk.StringVar(value="Automático: desligado")
        self.proxima_auto_var = tk.StringVar(value="Próxima execução: -")

        ttk.Label(frame_auto, textvariable=self.status_auto_var).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frame_auto, textvariable=self.proxima_auto_var).grid(row=2, column=0, sticky="w")

        # ===== Saída =====
        frame_saida = ttk.LabelFrame(container, text="Saída", padding=10)
        frame_saida.pack(fill="both", expand=False, pady=(0, 10))

        self.txt_saida = scrolledtext.ScrolledText(frame_saida, height=10, wrap="word")
        self.txt_saida.pack(fill="both", expand=True)

        # ===== Logs =====
        frame_logs = ttk.LabelFrame(container, text="Logs salvos em SQLite", padding=10)
        frame_logs.pack(fill="both", expand=True)

        colunas = ("id", "tipo", "inicio", "fim", "status", "detalhes", "criado_em")
        self.tree = ttk.Treeview(frame_logs, columns=colunas, show="headings", height=12)

        for col in colunas:
            self.tree.heading(col, text=col)

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("tipo", width=90, anchor="center")
        self.tree.column("inicio", width=160)
        self.tree.column("fim", width=160)
        self.tree.column("status", width=70, anchor="center")
        self.tree.column("detalhes", width=360)
        self.tree.column("criado_em", width=160)

        scrollbar = ttk.Scrollbar(frame_logs, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(container, text="Atualizar logs", command=self.refresh_logs).pack(anchor="e", pady=(8, 0))

    def escrever_saida(self, texto):
        self.txt_saida.insert("end", texto + "\n")
        self.txt_saida.see("end")

    def preencher_ultima_hora(self):
        inicio, fim = inicio_fim_ultima_hora()
        self.inicio_var.set(formatar_dt(inicio))
        self.fim_var.set(formatar_dt(fim))

    def executar_manual(self):
        try:
            inicio = parse_dt(self.inicio_var.get())
            fim = parse_dt(self.fim_var.get())
        except ValueError:
            messagebox.showerror(
                "Datas inválidas",
                "Use o formato: YYYY-MM-DD HH:MM:SS\nExemplo: 2026-08-10 14:00:00"
            )
            return

        if inicio >= fim:
            messagebox.showerror("Datas inválidas", "O início precisa ser antes do fim.")
            return

        threading.Thread(
            target=self._executar_job,
            args=("manual", inicio, fim, False),
            daemon=True
        ).start()

    def executar_ultima_hora(self):
        inicio, fim = inicio_fim_ultima_hora()
        threading.Thread(
            target=self._executar_job,
            args=("manual", inicio, fim, False),
            daemon=True
        ).start()

    def on_toggle_auto(self):
        if self.auto_var.get():
            self.iniciar_auto()
        else:
            self.parar_auto()

    def iniciar_auto(self):
        if self.auto_thread and self.auto_thread.is_alive():
            return

        agora = datetime.now()
        inicio = agora.replace(minute=0, second=0, microsecond=0)

        self.auto_stop.clear()
        self.auto_ativo = True
        self.ultimo_fim_auto = agora

        self.status_auto_var.set("Automático: ativo")
        self.proxima_auto_var.set(f"Próxima execução: {formatar_dt(proxima_hora_cheia(agora))}")

        # Roda imediatamente da hora corrente até agora
        threading.Thread(
            target=self._executar_job,
            args=("automatico", inicio, agora, True),
            daemon=True
        ).start()

        self.auto_thread = threading.Thread(target=self._loop_auto, daemon=True)
        self.auto_thread.start()

        self.escrever_saida("Modo automático ativado.")

    def parar_auto(self):
        self.auto_stop.set()
        self.auto_ativo = False
        self.status_auto_var.set("Automático: desligado")
        self.proxima_auto_var.set("Próxima execução: -")
        self.escrever_saida("Modo automático desativado.")

    def _loop_auto(self):
        while not self.auto_stop.is_set():
            ultimo_fim = self.ultimo_fim_auto or datetime.now()
            proxima_execucao = proxima_hora_cheia(ultimo_fim)

            while not self.auto_stop.is_set():
                restante = (proxima_execucao - datetime.now()).total_seconds()
                if restante <= 0:
                    break
                time.sleep(min(1, restante))

            if self.auto_stop.is_set():
                break

            inicio = self.ultimo_fim_auto
            fim = proxima_execucao

            if inicio and inicio < fim:
                self._executar_job("automatico", inicio, fim, True)

    def _executar_job(self, tipo, inicio, fim, atualizar_auto):
        try:
            self.queue.put(("saida", f"Iniciando {tipo}: {formatar_dt(inicio)} -> {formatar_dt(fim)}"))
            resultados = processar(inicio, fim)

            erros = [r for r in resultados if r[1] == "erro"]
            if erros:
                status = "erro"
                detalhes = "; ".join(f"{nome}: {erro}" for nome, _, _, erro in erros)
            else:
                status = "ok"
                detalhes = ", ".join(f"{nome}={qtd}" for nome, _, qtd, _ in resultados)

        except Exception as e:
            status = "erro"
            detalhes = str(e)
            logging.exception("Falha ao executar consulta")
        finally:
            try:
                registrar_log(tipo, inicio, fim, status, detalhes)
            except Exception as e:
                logging.exception("Falha ao registrar log no SQLite")
                self.queue.put(("saida", f"Erro ao salvar log local: {e}"))

            self.queue.put(("saida", f"[{status.upper()}] {tipo}: {detalhes}"))
            self.queue.put(("refresh_logs", None))

            if atualizar_auto:
                self.ultimo_fim_auto = fim
                self.queue.put(("auto_update", None))

    def _processar_fila(self):
        try:
            while True:
                acao, valor = self.queue.get_nowait()

                if acao == "saida":
                    self.escrever_saida(valor)

                elif acao == "refresh_logs":
                    self.refresh_logs()

                elif acao == "auto_update":
                    if self.auto_ativo and self.ultimo_fim_auto:
                        prox = proxima_hora_cheia(self.ultimo_fim_auto)
                        self.status_auto_var.set("Automático: ativo")
                        self.proxima_auto_var.set(f"Próxima execução: {formatar_dt(prox)}")

        except queue.Empty:
            pass

        self.after(200, self._processar_fila)

    def refresh_logs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        linhas = conn.execute(
            "SELECT * FROM execucoes ORDER BY id DESC LIMIT 100"
        ).fetchall()
        conn.close()

        for linha in linhas:
            self.tree.insert(
                "",
                "end",
                values=(
                    linha["id"],
                    linha["tipo"],
                    linha["data_inicio"],
                    linha["data_fim"],
                    linha["status"],
                    linha["detalhes"],
                    linha["criado_em"],
                )
            )

    def _fechar(self):
        self.auto_stop.set()
        self.destroy()


if __name__ == "__main__":
    app = AppBI()
    app.mainloop()