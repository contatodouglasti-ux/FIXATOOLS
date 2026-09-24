"""Bot isolado para criação de agentes e reprocessamento no MPSP."""

import queue
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from connectionSP import conectar as conectar_mpsp
from ui_helpers import aplicar_tema


INTERVALO_AUTO_MS = 60 * 60 * 1000
INTERVALO_STATUS_SEGUNDOS = 15
LIMITE_ACOMPANHAMENTO_SEGUNDOS = 30 * 60


SQL_REGISTROS_ALVO = """
SELECT nuseqintimacao, *
FROM saj.efmptjlotecargait e
WHERE e.deobservacao LIKE '%efmptjagente%'
  AND e.dtusuinclusao >= current_date
  AND e.dtusuinclusao < current_date + interval '1 day';
"""

SQL_GERAR_INSERTS_AGENTES = """
SELECT format(
  'INSERT INTO saj.efmptjagente (cdorigem, cdforo, cdagente, nmagente, cdtipoagente, floficializado, flforauso, tpsexo, cdusuinclusao, dtusuinclusao) VALUES (%s, %s, %s, %L, %s, %L, %L, %L, %L, NOW());',
  1,
  e2.cdforo,
  e2.cdagente,
  e2.nmagente,
  e2.cdtipoagente,
  e2.floficializado,
  e2.flforauso,
  e2.tpsexo,
  e2.cdusuinclusao
) AS sql_insert
FROM saj.efmptjagente e2
WHERE e2.cdorigem = 2
  AND e2.dtusuinclusao >= current_date
  AND e2.dtusuinclusao < current_date + interval '1 day'
  AND NOT EXISTS (
    SELECT 1
    FROM saj.efmptjagente e1
    WHERE e1.cdorigem = 1
      AND e1.cdforo = e2.cdforo
      AND e1.cdagente = e2.cdagente
  );
"""

SQL_REPROCESSAR = """
UPDATE saj.efmptjlotecargait
SET nucontarobo = 0,
    flstatusrobo = 'F',
    dtexpirarobo = NULL,
    cdsituacaoitem = 1,
    flstatus = 177
WHERE nuseqintimacao = ANY(%s);
"""

SQL_ACOMPANHAR = """
SELECT nuseqintimacao,
       cdprocesso,
       nuprocessoexterno,
       nucontarobo,
       flstatusrobo,
       dtexpirarobo,
       cdsituacaoitem,
       flstatus,
       deobservacao,
       cdlocaldestino,
       cdusuciencia,
       cdlocalizadorws
FROM saj.efmptjlotecargait
WHERE nuseqintimacao = ANY(%s);
"""


def _base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


LOG_PATH = _base_dir() / "mpsp_agente.log"
_LOG_LOCK = threading.Lock()


def _gravar_log(mensagem, nivel="INFO"):
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{nivel}] {mensagem}"
    with _LOG_LOCK:
        with LOG_PATH.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")
    return linha


def _buscar_dicts(conn, sql, parametros=None):
    with conn.cursor() as cur:
        if parametros is None:
            cur.execute(sql)
        else:
            cur.execute(sql, parametros)
        colunas = [desc[0] for desc in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def _emitir(log, mensagem, nivel="INFO"):
    linha = _gravar_log(mensagem, nivel)
    if log:
        log(linha)


def executar_fluxo(log=None, stop_event=None):
    """Executa uma rodada completa e retorna os totais da rodada."""
    stop_event = stop_event or threading.Event()
    conn = None
    tunnel = None
    inicio = datetime.now()
    resumo = {
        "encontrados": 0,
        "agentes_inseridos": 0,
        "reprocessados": 0,
        "ajustados": 0,
        "pendentes": 0,
        "cancelado": False,
        "duracao": None,
    }

    try:
        _emitir(log, "Iniciando rodada do bot MPSP.")
        conexao = conectar_mpsp()
        if not conexao or conexao[0] is None:
            raise RuntimeError("Não foi possível conectar à base MPSP via túnel SSH.")

        conn, tunnel = conexao
        _emitir(log, "Conexão com a base MPSP estabelecida.")

        registros = _buscar_dicts(conn, SQL_REGISTROS_ALVO)
        ids = list(dict.fromkeys(
            registro["nuseqintimacao"]
            for registro in registros
            if registro.get("nuseqintimacao") is not None
        ))
        resumo["encontrados"] = len(ids)
        _emitir(log, f"Registros encontrados na consulta: {len(ids)}.")

        if not ids:
            _emitir(log, "Nenhum registro para ajustar nesta rodada.")
            return resumo

        if stop_event.is_set():
            resumo["cancelado"] = True
            return resumo

        insert_rows = _buscar_dicts(conn, SQL_GERAR_INSERTS_AGENTES)
        comandos = [row["sql_insert"] for row in insert_rows if row.get("sql_insert")]
        if comandos:
            with conn.cursor() as cur:
                for comando in comandos:
                    cur.execute(comando)
            conn.commit()
        resumo["agentes_inseridos"] = len(comandos)
        _emitir(log, f"Agentes inseridos: {len(comandos)}.")

        if stop_event.is_set():
            resumo["cancelado"] = True
            return resumo

        with conn.cursor() as cur:
            cur.execute(SQL_REPROCESSAR, (ids,))
            resumo["reprocessados"] = cur.rowcount
        conn.commit()
        _emitir(log, f"Intimações reprocessadas: {resumo['reprocessados']}.")

        pendentes = {str(valor): valor for valor in ids}
        prazo = time.monotonic() + LIMITE_ACOMPANHAMENTO_SEGUNDOS
        while pendentes and time.monotonic() < prazo:
            if stop_event.is_set():
                resumo["cancelado"] = True
                break

            status_rows = _buscar_dicts(conn, SQL_ACOMPANHAR, (list(pendentes.values()),))
            concluidos = []
            for row in status_rows:
                if str(row.get("flstatus")) == "161":
                    chave = str(row.get("nuseqintimacao"))
                    if chave in pendentes:
                        concluidos.append(chave)

            for chave in concluidos:
                pendentes.pop(chave, None)
            resumo["ajustados"] = len(ids) - len(pendentes)
            _emitir(
                log,
                f"Acompanhamento: {resumo['ajustados']}/{len(ids)} com flstatus 161.",
            )

            if pendentes:
                stop_event.wait(INTERVALO_STATUS_SEGUNDOS)

        resumo["pendentes"] = len(pendentes)
        if resumo["cancelado"]:
            _emitir(log, "Rodada cancelada pelo usuário.", "AVISO")
        elif pendentes:
            _emitir(
                log,
                f"Prazo de acompanhamento encerrado. Pendentes: {len(pendentes)}.",
                "AVISO",
            )
        else:
            _emitir(log, f"Rodada concluída com sucesso. Total ajustado: {resumo['ajustados']}.")

        return resumo
    except Exception as exc:
        if conn:
            conn.rollback()
        _emitir(log, f"Erro na rodada: {exc}", "ERRO")
        _emitir(log, traceback.format_exc().rstrip(), "ERRO")
        raise
    finally:
        resumo["duracao"] = str(datetime.now() - inicio).split(".")[0]
        if conn:
            conn.close()
        if tunnel:
            tunnel.stop()
        _emitir(log, "Conexão MPSP encerrada.")


class AgenteMPSP(ttk.Frame):
    """Interface do projeto MPSP, isolada dos demais fluxos."""

    def __init__(self, parent):
        super().__init__(parent, style="App.TFrame")
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_lock = threading.Lock()
        self.worker_running = False
        self.auto_ativo = False
        self.auto_after_id = None

        self._criar_widgets()
        self.after(200, self._processar_fila)

    def _criar_widgets(self):
        container = ttk.Frame(self, style="App.TFrame", padding=(16, 14, 16, 12))
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Agente MPSP", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text="Criação de agentes, reprocessamento e acompanhamento do flstatus 161.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        ttk.Label(
            container,
            text="CLIENTE ATIVO: MPSP  •  BASE: sigsp  •  TÚNEL SSH",
            style="ClientSP.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        frame_acoes = ttk.LabelFrame(
            container,
            text="Execução",
            style="Card.TLabelframe",
            padding=10,
        )
        frame_acoes.pack(fill="x", pady=(0, 10))

        self.manual_btn = ttk.Button(
            frame_acoes,
            text="Executar agora",
            style="Primary.TButton",
            command=lambda: self._iniciar_worker("manual"),
        )
        self.manual_btn.grid(row=0, column=0, padx=(0, 12), sticky="w")

        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame_acoes,
            text="Ativar bot automático (a cada 1h)",
            variable=self.auto_var,
            command=self._alternar_automatico,
        ).grid(row=0, column=1, sticky="w")

        self.status_var = tk.StringVar(value="Aguardando execução manual.")
        self.proxima_var = tk.StringVar(value="Próxima execução automática: -")
        ttk.Label(frame_acoes, textvariable=self.status_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(frame_acoes, textvariable=self.proxima_var, style="Hint.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")

        frame_totais = ttk.LabelFrame(
            container,
            text="Resumo da última rodada",
            style="Card.TLabelframe",
            padding=8,
        )
        frame_totais.pack(fill="x", pady=(0, 10))
        for coluna in range(4):
            frame_totais.columnconfigure(coluna, weight=1)

        self.total_vars = []
        for coluna, (rotulo, valor) in enumerate((
            ("Encontrados", "0"),
            ("Agentes inseridos", "0"),
            ("Reprocessados", "0"),
            ("Total ajustado", "0"),
        )):
            bloco = ttk.Frame(frame_totais, style="Card.TFrame")
            bloco.grid(row=0, column=coluna, sticky="ew", padx=4)
            ttk.Label(bloco, text=rotulo, style="Hint.TLabel").pack(anchor="w")
            variavel = tk.StringVar(value=valor)
            self.total_vars.append(variavel)
            ttk.Label(bloco, textvariable=variavel, style="Stat.TLabel").pack(fill="x", pady=(3, 0))

        frame_log = ttk.LabelFrame(
            container,
            text="Log da execução",
            style="Card.TLabelframe",
            padding=8,
        )
        frame_log.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(
            frame_log,
            height=14,
            wrap=tk.WORD,
            state="disabled",
            font=("Consolas", 9),
            background="#0f172a",
            foreground="#dbeafe",
            insertbackground="#ffffff",
            relief="flat",
        )
        self.log_text.pack(fill="both", expand=True)

    def _adicionar_tela(self, linha):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, linha + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _alternar_automatico(self):
        self.auto_ativo = self.auto_var.get()
        if self.auto_ativo:
            self.status_var.set("Bot automático ativo.")
            self._agendar_proxima_execucao()
            self._adicionar_tela(_gravar_log("Bot automático ativado."))
        else:
            if self.auto_after_id:
                self.after_cancel(self.auto_after_id)
                self.auto_after_id = None
            self.proxima_var.set("Próxima execução automática: -")
            self.status_var.set("Bot automático desligado.")
            self._adicionar_tela(_gravar_log("Bot automático desativado."))

    def _agendar_proxima_execucao(self):
        agora = datetime.now()
        proxima = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        atraso = max(1000, int((proxima - agora).total_seconds() * 1000))
        self.proxima_var.set(f"Próxima execução automática: {proxima:%d/%m/%Y %H:%M}")
        self.auto_after_id = self.after(atraso, self._disparar_automatico)

    def _disparar_automatico(self):
        self.auto_after_id = None
        if self.auto_ativo:
            self._iniciar_worker("automatico")
            self._agendar_proxima_execucao()

    def _iniciar_worker(self, origem):
        with self.worker_lock:
            if self.worker_running:
                self._adicionar_tela(_gravar_log("Execução ignorada: já existe uma rodada em andamento.", "AVISO"))
                return
            self.worker_running = True

        self.stop_event.clear()
        self.manual_btn.configure(state="disabled")
        self.status_var.set(f"Executando rodada {origem}...")
        threading.Thread(target=self._rodar_worker, args=(origem,), daemon=True).start()

    def _rodar_worker(self, origem):
        try:
            resumo = executar_fluxo(log=lambda linha: self.queue.put(("log", linha)), stop_event=self.stop_event)
            self.queue.put(("resultado", origem, resumo, None))
        except Exception as exc:
            self.queue.put(("resultado", origem, None, exc))

    def _processar_fila(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if item[0] == "log":
                    self._adicionar_tela(item[1])
                elif item[0] == "resultado":
                    _, origem, resumo, erro = item
                    self._finalizar_worker(origem, resumo, erro)
        except queue.Empty:
            pass
        self.after(200, self._processar_fila)

    def _finalizar_worker(self, origem, resumo, erro):
        with self.worker_lock:
            self.worker_running = False
        self.manual_btn.configure(state="normal")

        if erro:
            self.status_var.set(f"Erro na execução {origem}: {erro}")
            messagebox.showerror("Agente MPSP", str(erro), parent=self.winfo_toplevel())
            return

        self.total_vars[0].set(str(resumo["encontrados"]))
        self.total_vars[1].set(str(resumo["agentes_inseridos"]))
        self.total_vars[2].set(str(resumo["reprocessados"]))
        self.total_vars[3].set(str(resumo["ajustados"]))
        if resumo["cancelado"]:
            self.status_var.set("Execução cancelada.")
        elif resumo["pendentes"]:
            self.status_var.set(f"Concluída com {resumo['pendentes']} pendência(s).")
        else:
            self.status_var.set(f"Concluída. Total ajustado: {resumo['ajustados']}.")

    def parar(self):
        self.auto_ativo = False
        self.auto_var.set(False)
        self.stop_event.set()
        if self.auto_after_id:
            self.after_cancel(self.auto_after_id)
            self.auto_after_id = None


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Agente MPSP")
    root.geometry("1050x720")
    root.minsize(850, 600)
    aplicar_tema(root)
    app = AgenteMPSP(root)
    app.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.parar(), root.destroy()))
    root.mainloop()
