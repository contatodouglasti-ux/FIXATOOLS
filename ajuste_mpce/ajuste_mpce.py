"""Painel isolado para ajustar tarefas SAJ6 do MPCE."""

import json
import queue
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from connectionCE import conectar as conectar_mpce
from connectionCEunj import conectar as conectar_mpce_unj
from config_manager import obter_credenciais, salvar_mpce_unj
from ui_helpers import aplicar_tema


INTERVALO_AUTO_MS = 60 * 60 * 1000


SQL_CANDIDATOS = """
SELECT i.cdobjeto,
       i.cdpeticionamento,
       p.cdprocesso,
       p.dtprotocolizado
FROM saj.efmpintimacao i
INNER JOIN saj.efmppeticionamento p
        ON p.cdpeticionamento = i.cdpeticionamento
WHERE p.cdprocesso IN (
    SELECT processo.cdprocesso
    FROM saj.efmpprocesso processo
    WHERE processo.cdlocal IN (
        SELECT localidade.cdlocal
        FROM saj.esajlocal localidade
        WHERE localidade.flsaj6habilitado = 'S'
    )
)
AND p.flstatus = '2'
AND p.idcard IS NULL
AND p.dtusuinclusao >= %(inicio)s
AND p.dtusuinclusao < %(fim)s;
"""

SQL_TAREFAS_ATIVAS = """
SELECT idcard, *
FROM sajptf.eptftarefa
WHERE idcard = ANY(%s)
  AND idstatus <> 4;
"""

SQL_AJUSTAR_TAREFAS = """
UPDATE sajptf.eptftarefa
SET idstatus = 4,
    idgrupo = 15,
    dtconclusao = %s
WHERE idcard = %s
  AND idstatus <> 4;
"""


def _base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


LOG_PATH = _base_dir() / "mpce_ajuste_tarefa.log"
METRICAS_PATH = _base_dir() / "mpce_operacoes.json"
_LOG_LOCK = threading.Lock()
_METRICAS_LOCK = threading.Lock()


def _metricas_padrao():
    return {
        "consultas": 0,
        "inserts": 0,
        "updates": 0,
        "rodadas": 0,
    }


def _carregar_metricas():
    try:
        dados = json.loads(METRICAS_PATH.read_text(encoding="utf-8"))
        metricas = _metricas_padrao()
        for chave in metricas:
            metricas[chave] = int(dados.get(chave, 0) or 0)
        return metricas
    except (OSError, ValueError, TypeError):
        return _metricas_padrao()


def _registrar_metricas(resumo):
    with _METRICAS_LOCK:
        metricas = _carregar_metricas()
        metricas["consultas"] += int(resumo.get("consultas", 0) or 0)
        metricas["inserts"] += int(resumo.get("inserts", 0) or 0)
        metricas["updates"] += int(resumo.get("updates", 0) or 0)
        metricas["rodadas"] += 1
        METRICAS_PATH.write_text(
            json.dumps(metricas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return metricas


def inicio_fim_ultima_hora():
    agora = datetime.now()
    fim = agora.replace(minute=0, second=0, microsecond=0)
    return fim - timedelta(hours=1), fim


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


def _chave(valor):
    return str(valor).strip() if valor is not None else ""


def verificar_fluxo(data_inicio=None, data_fim=None, log=None, stop_event=None):
    """Consulta os candidatos sem alterar dados e lista o que seria ajustado."""
    padrao_inicio, padrao_fim = inicio_fim_ultima_hora()
    data_inicio = data_inicio or padrao_inicio
    data_fim = data_fim or padrao_fim
    stop_event = stop_event or threading.Event()
    conn_sigce = None
    conn_unj = None
    inicio_execucao = datetime.now()
    resumo = {
        "inicio": data_inicio,
        "fim": data_fim,
        "processos": 0,
        "candidatos": 0,
        "idcards": 0,
        "tarefas": 0,
        "consultas": 0,
        "inserts": 0,
        "updates": 0,
        "ajustados": 0,
        "ajustaveis": 0,
        "linhas": [],
        "cancelado": False,
        "duracao": None,
    }

    try:
        _emitir(log, f"Iniciando verificação MPCE: {data_inicio:%Y-%m-%d %H:%M} até {data_fim:%Y-%m-%d %H:%M}.")
        conn_sigce = conectar_mpce()
        if conn_sigce is None:
            raise RuntimeError("Não foi possível conectar à base MPCE.")
        _emitir(log, "Conexão com a base MPCE estabelecida para consulta.")

        resumo["consultas"] += 1
        candidatos = _buscar_dicts(conn_sigce, SQL_CANDIDATOS, {
            "inicio": data_inicio,
            "fim": data_fim,
        })
        resumo["candidatos"] = len(candidatos)
        resumo["processos"] = len({row.get("cdprocesso") for row in candidatos if row.get("cdprocesso") is not None})

        por_idcard = {}
        for row in candidatos:
            card = _chave(row.get("cdobjeto"))
            if card:
                por_idcard.setdefault(card, row)

        resumo["idcards"] = len(por_idcard)
        _emitir(
            log,
            f"Candidatos encontrados: {resumo['candidatos']}; "
            f"processos: {resumo['processos']}; idcards: {resumo['idcards']}."
        )

        if stop_event.is_set() or not por_idcard:
            resumo["cancelado"] = stop_event.is_set()
            _emitir(log, "Nenhum idcard disponível para verificação.")
            return resumo

        conn_unj = conectar_mpce_unj()
        if conn_unj is None:
            raise RuntimeError("Não foi possível conectar à base unj01ce do MPCE.")
        _emitir(log, "Conexão com a base de tarefas unj01ce estabelecida para consulta.")

        resumo["consultas"] += 1
        tarefas = _buscar_dicts(conn_unj, SQL_TAREFAS_ATIVAS, (list(por_idcard),))
        resumo["tarefas"] = len(tarefas)
        tarefas_por_idcard = {}
        for tarefa in tarefas:
            card = _chave(tarefa.get("idcard"))
            if card:
                tarefas_por_idcard[card] = tarefas_por_idcard.get(card, 0) + 1

        for card, quantidade in tarefas_por_idcard.items():
            candidato = por_idcard.get(card)
            if not candidato:
                continue
            linha = {
                "cdprocesso": candidato.get("cdprocesso"),
                "idcard": card,
                "dtprotocolizado": candidato.get("dtprotocolizado"),
                "tarefas": quantidade,
            }
            resumo["linhas"].append(linha)
            _emitir(
                log,
                f"Prévia | Processo {linha['cdprocesso']} | idcard {card} | "
                f"dtconclusao {linha['dtprotocolizado']} | tarefas ativas: {quantidade}."
            )

        resumo["ajustaveis"] = len(resumo["linhas"])
        _emitir(
            log,
            f"Verificação concluída: {resumo['ajustaveis']} idcard(s) com "
            f"{resumo['tarefas']} tarefa(s) ativa(s)."
        )
        return resumo
    except Exception as exc:
        _emitir(log, f"Erro na verificação: {exc}", "ERRO")
        _emitir(log, traceback.format_exc().rstrip(), "ERRO")
        raise
    finally:
        resumo["duracao"] = str(datetime.now() - inicio_execucao).split(".")[0]
        try:
            resumo["metricas"] = _registrar_metricas(resumo)
        except Exception as exc:
            _emitir(log, f"Não foi possível salvar as métricas da rodada: {exc}", "AVISO")
        if conn_unj:
            conn_unj.close()
        if conn_sigce:
            conn_sigce.close()
        _emitir(log, "Conexões MPCE encerradas após a verificação.")


def executar_fluxo(data_inicio=None, data_fim=None, log=None, stop_event=None):
    """Busca intimações SAJ6 e conclui as tarefas correspondentes."""
    padrao_inicio, padrao_fim = inicio_fim_ultima_hora()
    data_inicio = data_inicio or padrao_inicio
    data_fim = data_fim or padrao_fim
    stop_event = stop_event or threading.Event()
    conn_sigce = None
    conn_unj = None
    inicio_execucao = datetime.now()
    resumo = {
        "inicio": data_inicio,
        "fim": data_fim,
        "processos": 0,
        "candidatos": 0,
        "idcards": 0,
        "tarefas": 0,
        "consultas": 0,
        "inserts": 0,
        "updates": 0,
        "ajustados": 0,
        "cancelado": False,
        "duracao": None,
    }

    try:
        _emitir(log, f"Iniciando rodada MPCE: {data_inicio:%Y-%m-%d %H:%M} até {data_fim:%Y-%m-%d %H:%M}.")
        conn_sigce = conectar_mpce()
        if conn_sigce is None:
            raise RuntimeError("Não foi possível conectar à base MPCE.")
        _emitir(log, "Conexão com a base MPCE estabelecida.")

        resumo["consultas"] += 1
        candidatos = _buscar_dicts(conn_sigce, SQL_CANDIDATOS, {
            "inicio": data_inicio,
            "fim": data_fim,
        })
        resumo["candidatos"] = len(candidatos)
        resumo["processos"] = len({row.get("cdprocesso") for row in candidatos if row.get("cdprocesso") is not None})
        _emitir(log, f"Candidatos encontrados: {resumo['candidatos']}; processos: {resumo['processos']}.")

        por_idcard = {}
        for row in candidatos:
            card = _chave(row.get("cdobjeto"))
            if not card:
                _emitir(log, f"Registro ignorado sem cdobjeto. Processo: {row.get('cdprocesso')}.", "AVISO")
                continue
            anterior = por_idcard.get(card)
            if anterior and anterior.get("dtprotocolizado") != row.get("dtprotocolizado"):
                _emitir(log, f"idcard {card} possui mais de um dtprotocolizado; usando o primeiro encontrado.", "AVISO")
                continue
            por_idcard[card] = row

        resumo["idcards"] = len(por_idcard)
        if not por_idcard:
            _emitir(log, "Nenhum idcard para ajustar nesta rodada.")
            return resumo

        if stop_event.is_set():
            resumo["cancelado"] = True
            return resumo

        conn_unj = conectar_mpce_unj()
        if conn_unj is None:
            raise RuntimeError("NÃ£o foi possÃ­vel conectar Ã  base unj01ce do MPCE.")
        _emitir(log, "ConexÃ£o com a base de tarefas unj01ce estabelecida.")

        idcards = list(por_idcard)
        resumo["consultas"] += 1
        tarefas = _buscar_dicts(conn_unj, SQL_TAREFAS_ATIVAS, (idcards,))
        resumo["tarefas"] = len(tarefas)
        _emitir(log, f"Tarefas ativas encontradas: {len(tarefas)}.")

        if not tarefas:
            _emitir(log, "Nenhuma tarefa com idstatus diferente de 4 foi encontrada.")
            return resumo

        tarefas_por_idcard = {}
        for tarefa in tarefas:
            card = _chave(tarefa.get("idcard"))
            if card:
                tarefas_por_idcard[card] = tarefa

        with conn_unj.cursor() as cur:
            for card, tarefa in tarefas_por_idcard.items():
                if stop_event.is_set():
                    resumo["cancelado"] = True
                    break
                candidato = por_idcard[card]
                resumo["consultas"] += 1
                cur.execute(SQL_AJUSTAR_TAREFAS, (
                    candidato.get("dtprotocolizado"),
                    tarefa.get("idcard"),
                ))
                ajustados = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                resumo["ajustados"] += ajustados
                resumo["updates"] += ajustados
                _emitir(
                    log,
                    f"Processo {candidato.get('cdprocesso')} | idcard {card} | "
                    f"dtconclusao {candidato.get('dtprotocolizado')} | "
                    f"tarefas ajustadas: {ajustados}.",
                )
        conn_unj.commit()

        if resumo["cancelado"]:
            _emitir(log, "Rodada cancelada antes de concluir todos os ajustes.", "AVISO")
        else:
            _emitir(log, f"Rodada concluída. Total ajustado: {resumo['ajustados']}.")
        return resumo
    except Exception as exc:
        if conn_unj:
            conn_unj.rollback()
        _emitir(log, f"Erro na rodada: {exc}", "ERRO")
        _emitir(log, traceback.format_exc().rstrip(), "ERRO")
        raise
    finally:
        resumo["duracao"] = str(datetime.now() - inicio_execucao).split(".")[0]
        try:
            resumo["metricas"] = _registrar_metricas(resumo)
        except Exception as exc:
            _emitir(log, f"Não foi possível salvar as métricas da rodada: {exc}", "AVISO")
        if conn_unj:
            conn_unj.close()
        if conn_sigce:
            conn_sigce.close()
        _emitir(log, "Conexão MPCE encerrada.")


class AjusteMPCE(ttk.Frame):
    """Interface do projeto MPCE, sem compartilhar estado com os demais."""

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

        ttk.Label(container, text="Ajuste de Tarefas MPCE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text="Conclui tarefas SAJ6 usando o dtprotocolizado do peticionamento.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 10))
        ttk.Label(
            container,
            text="CLIENTE ATIVO: MPCE  •  BASE: sigce  •  ESCOPO: SAJ6",
            style="ClientSP.TLabel",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        frame_acoes = ttk.LabelFrame(container, text="Execução", style="Card.TLabelframe", padding=10)
        frame_acoes.pack(fill="x", pady=(0, 10))
        padrao_inicio, padrao_fim = inicio_fim_ultima_hora()
        self.hora_inicio_var = tk.StringVar(value=padrao_inicio.strftime("%H:%M"))
        self.hora_fim_var = tk.StringVar(value=padrao_fim.strftime("%H:%M"))
        self.manual_btn = ttk.Button(
            frame_acoes,
            text="Executar agora",
            style="Primary.TButton",
            command=lambda: self._iniciar_worker("manual"),
        )
        self.manual_btn.grid(row=0, column=0, padx=(0, 12), sticky="w")
        self.verificar_btn = ttk.Button(
            frame_acoes,
            text="Verificar idcards",
            command=lambda: self._iniciar_worker("verificacao"),
        )
        self.verificar_btn.grid(row=0, column=1, padx=(0, 12), sticky="w")
        self.auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame_acoes,
            text="Ativar bot automático (a cada 1h)",
            variable=self.auto_var,
            command=self._alternar_automatico,
        ).grid(row=0, column=2, sticky="w")
        ttk.Button(
            frame_acoes,
            text="Configurar banco UNJ01CE",
            command=self._configurar_banco_unj,
        ).grid(row=0, column=3, padx=(18, 0), sticky="w")
        self.status_var = tk.StringVar(value="Aguardando execução manual.")
        self.proxima_var = tk.StringVar(value="Próxima execução automática: -")
        frame_periodo = ttk.Frame(frame_acoes)
        frame_periodo.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Label(frame_periodo, text="Periodo manual de hoje:").pack(side="left")
        ttk.Label(frame_periodo, text="De").pack(side="left", padx=(12, 4))
        ttk.Entry(frame_periodo, textvariable=self.hora_inicio_var, width=7, justify="center").pack(side="left")
        ttk.Label(frame_periodo, text="Ate").pack(side="left", padx=(8, 4))
        ttk.Entry(frame_periodo, textvariable=self.hora_fim_var, width=7, justify="center").pack(side="left")
        ttk.Label(
            frame_periodo,
            text="(formato HH:MM; usado no manual e na verificacao)",
            style="Hint.TLabel",
        ).pack(side="left", padx=(10, 0))
        ttk.Label(frame_acoes, textvariable=self.status_var).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(frame_acoes, textvariable=self.proxima_var, style="Hint.TLabel").grid(row=3, column=0, columnspan=4, sticky="w")

        frame_totais = ttk.LabelFrame(container, text="Resumo da última rodada", style="Card.TLabelframe", padding=8)
        frame_totais.pack(fill="x", pady=(0, 10))
        for coluna in range(4):
            frame_totais.columnconfigure(coluna, weight=1)
        self.total_vars = []
        for coluna, rotulo in enumerate(("Processos", "Candidatos", "IDCards", "Total ajustado")):
            bloco = ttk.Frame(frame_totais, style="Card.TFrame")
            bloco.grid(row=0, column=coluna, sticky="ew", padx=4)
            ttk.Label(bloco, text=rotulo, style="Hint.TLabel").pack(anchor="w")
            variavel = tk.StringVar(value="0")
            self.total_vars.append(variavel)
            ttk.Label(bloco, textvariable=variavel, style="Stat.TLabel").pack(fill="x", pady=(3, 0))

        frame_operacoes = ttk.LabelFrame(
            container,
            text="Operacoes acumuladas",
            style="Card.TLabelframe",
            padding=8,
        )
        frame_operacoes.pack(fill="x", pady=(0, 10))
        for coluna in range(4):
            frame_operacoes.columnconfigure(coluna, weight=1)
        metricas = _carregar_metricas()
        self.operacao_vars = []
        for coluna, (rotulo, chave) in enumerate(
            (("Consultas", "consultas"), ("INSERT", "inserts"), ("UPDATE", "updates"), ("Rodadas", "rodadas"))
        ):
            bloco = ttk.Frame(frame_operacoes, style="Card.TFrame")
            bloco.grid(row=0, column=coluna, sticky="ew", padx=4)
            ttk.Label(bloco, text=rotulo, style="Hint.TLabel").pack(anchor="w")
            variavel = tk.StringVar(value=str(metricas[chave]))
            self.operacao_vars.append((chave, variavel))
            ttk.Label(bloco, textvariable=variavel, style="Stat.TLabel").pack(fill="x", pady=(3, 0))

        frame_preview = ttk.LabelFrame(
            container,
            text="Idcards encontrados - confira antes de executar o ajuste",
            style="Card.TLabelframe",
            padding=8,
        )
        frame_preview.pack(fill="x", pady=(0, 10))
        self.preview_tree = ttk.Treeview(
            frame_preview,
            columns=("processo", "idcard", "data", "tarefas"),
            show="headings",
            height=6,
        )
        self.preview_tree.heading("processo", text="Processo")
        self.preview_tree.heading("idcard", text="IDCard")
        self.preview_tree.heading("data", text="dtprotocolizado")
        self.preview_tree.heading("tarefas", text="Tarefas ativas")
        self.preview_tree.column("processo", width=150, anchor="w")
        self.preview_tree.column("idcard", width=260, anchor="w")
        self.preview_tree.column("data", width=170, anchor="center")
        self.preview_tree.column("tarefas", width=110, anchor="center")
        self.preview_tree.pack(side="left", fill="x", expand=True)
        preview_scroll = ttk.Scrollbar(frame_preview, orient="vertical", command=self.preview_tree.yview)
        preview_scroll.pack(side="right", fill="y")
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)

        frame_log = ttk.LabelFrame(container, text="Log da execução", style="Card.TLabelframe", padding=8)
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

    def _configurar_banco_unj(self):
        cred = obter_credenciais()
        janela = tk.Toplevel(self)
        janela.title("Configuração — MPCE UNJ01CE")
        janela.transient(self.winfo_toplevel())
        janela.grab_set()
        janela.resizable(False, False)

        corpo = ttk.Frame(janela, padding=16)
        corpo.pack(fill="both", expand=True)
        ttk.Label(
            corpo,
            text="Banco usado para consultar e atualizar sajptf.eptftarefa",
            style="Subtitle.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        campos = (
            ("Host", "mpce_host", cred.get("mpce_host", "")),
            ("Porta", "mpce_port", cred.get("mpce_port", 5432)),
            ("Banco", "mpce_db_unj", cred.get("mpce_db_unj", "unj01ce")),
            ("Usuário", "mpce_user", cred.get("mpce_user", "")),
            ("Senha", "mpce_password", cred.get("mpce_password", "")),
        )
        entradas = {}
        for linha, (rotulo, chave, valor) in enumerate(campos, start=1):
            ttk.Label(corpo, text=f"{rotulo}:").grid(row=linha, column=0, sticky="w", padx=(0, 10), pady=4)
            entrada = ttk.Entry(corpo, width=36, show="•" if chave == "mpce_password" else "")
            entrada.insert(0, str(valor or ""))
            entrada.grid(row=linha, column=1, sticky="ew", pady=4)
            entradas[chave] = entrada

        botoes = ttk.Frame(corpo)
        botoes.grid(row=len(campos) + 1, column=0, columnspan=2, sticky="e", pady=(14, 0))

        def salvar():
            valores = {chave: entrada.get().strip() for chave, entrada in entradas.items()}
            obrigatorios = ("mpce_host", "mpce_port", "mpce_db_unj", "mpce_user", "mpce_password")
            if any(not valores[chave] for chave in obrigatorios):
                messagebox.showwarning(
                    "Configuração incompleta",
                    "Preencha host, porta, banco, usuário e senha.",
                    parent=janela,
                )
                return
            try:
                int(valores["mpce_port"])
            except ValueError:
                messagebox.showwarning("Porta inválida", "A porta deve ser numérica.", parent=janela)
                return
            salvar_mpce_unj(
                valores["mpce_host"],
                valores["mpce_port"],
                valores["mpce_db_unj"],
                valores["mpce_user"],
                valores["mpce_password"],
            )
            self._adicionar_tela(_gravar_log("Configuração do banco MPCE UNJ01CE salva."))
            messagebox.showinfo("Configuração salva", "O banco UNJ01CE foi configurado.", parent=janela)
            janela.destroy()

        ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(botoes, text="Salvar", style="Primary.TButton", command=salvar).pack(side="right")
        janela.bind("<Return>", lambda _event: salvar())

    def _adicionar_tela(self, linha):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, linha + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _mostrar_preview(self, resumo):
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        for linha in resumo.get("linhas", []):
            data = linha.get("dtprotocolizado")
            if hasattr(data, "strftime"):
                data = data.strftime("%d/%m/%Y %H:%M:%S")
            self.preview_tree.insert(
                "",
                tk.END,
                values=(
                    linha.get("cdprocesso") or "-",
                    linha.get("idcard") or "-",
                    data or "-",
                    linha.get("tarefas", 0),
                ),
            )

    def _mostrar_metricas(self, metricas):
        if not metricas:
            return
        for chave, variavel in self.operacao_vars:
            variavel.set(str(metricas.get(chave, 0)))

    def _alternar_automatico(self):
        self.auto_ativo = self.auto_var.get()
        if self.auto_ativo:
            self.status_var.set("Bot automático ativo.")
            self._agendar_proxima_execucao()
            self._adicionar_tela(_gravar_log("Bot automático MPCE ativado."))
        else:
            if self.auto_after_id:
                self.after_cancel(self.auto_after_id)
                self.auto_after_id = None
            self.proxima_var.set("Próxima execução automática: -")
            self.status_var.set("Bot automático desligado.")
            self._adicionar_tela(_gravar_log("Bot automático MPCE desativado."))

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

    def _obter_periodo_manual(self):
        try:
            inicio_hora = datetime.strptime(self.hora_inicio_var.get().strip(), "%H:%M").time()
            fim_hora = datetime.strptime(self.hora_fim_var.get().strip(), "%H:%M").time()
        except ValueError as exc:
            raise ValueError("Informe os horarios no formato HH:MM, por exemplo 10:00 e 15:00.") from exc

        hoje = datetime.now().date()
        data_inicio = datetime.combine(hoje, inicio_hora)
        data_fim = datetime.combine(hoje, fim_hora)
        if data_fim <= data_inicio:
            raise ValueError("O horario final precisa ser maior que o horario inicial.")
        return data_inicio, data_fim

    def _iniciar_worker(self, origem):
        data_inicio = None
        data_fim = None
        if origem in ("manual", "verificacao"):
            try:
                data_inicio, data_fim = self._obter_periodo_manual()
            except ValueError as exc:
                messagebox.showwarning("Periodo invalido", str(exc), parent=self.winfo_toplevel())
                return

        with self.worker_lock:
            if self.worker_running:
                self._adicionar_tela(_gravar_log("Execução ignorada: já existe uma rodada em andamento.", "AVISO"))
                return
            self.worker_running = True
        self.stop_event.clear()
        self.manual_btn.configure(state="disabled")
        self.verificar_btn.configure(state="disabled")
        if data_inicio and data_fim:
            self.status_var.set(
                f"Executando {origem} de {data_inicio:%H:%M} até {data_fim:%H:%M}..."
            )
        else:
            self.status_var.set(f"Executando rodada {origem}...")
        threading.Thread(
            target=self._rodar_worker,
            args=(origem, data_inicio, data_fim),
            daemon=True,
        ).start()

    def _rodar_worker(self, origem, data_inicio=None, data_fim=None):
        try:
            funcao = verificar_fluxo if origem == "verificacao" else executar_fluxo
            resumo = funcao(
                data_inicio=data_inicio,
                data_fim=data_fim,
                log=lambda linha: self.queue.put(("log", linha)),
                stop_event=self.stop_event,
            )
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
        self.verificar_btn.configure(state="normal")
        if erro:
            self.status_var.set(f"Erro na execução {origem}: {erro}")
            messagebox.showerror("Ajuste MPCE", str(erro), parent=self.winfo_toplevel())
            return
        self._mostrar_metricas(resumo.get("metricas"))
        if origem == "verificacao":
            self._mostrar_preview(resumo)
            self.total_vars[0].set(str(resumo["processos"]))
            self.total_vars[1].set(str(resumo["candidatos"]))
            self.total_vars[2].set(str(resumo["idcards"]))
            self.total_vars[3].set("0")
            self.status_var.set(
                f"Verificação concluída: {resumo['ajustaveis']} idcard(s) prontos para ajuste."
            )
            return
        self.total_vars[0].set(str(resumo["processos"]))
        self.total_vars[1].set(str(resumo["candidatos"]))
        self.total_vars[2].set(str(resumo["idcards"]))
        self.total_vars[3].set(str(resumo["ajustados"]))
        if resumo["cancelado"]:
            self.status_var.set("Execução cancelada.")
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
    root.title("Ajuste de Tarefas MPCE")
    root.geometry("1050x720")
    root.minsize(850, 600)
    aplicar_tema(root)
    app = AjusteMPCE(root)
    app.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.parar(), root.destroy()))
    root.mainloop()
