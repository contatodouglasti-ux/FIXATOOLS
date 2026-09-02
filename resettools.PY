import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from datetime import datetime
import time

from connectionSP import conectar as conectar_sp
from connectionSPunj import conectar as conectar_unj
from connectionRS import conectar as conectar_mprs
from connectionRSunj import conectar as conectar_mprs_unj
import config_manager
from ui_helpers import aplicar_tema, COLORS

MARCA_SIGSP = "-- ==== SIGSP (saj) ===="
MARCA_MPRS = "-- ==== MPRS (saj) ===="
MARCA_MPRS_UNJ = "-- ==== MPRS (sajptf) ===="
MARCA_UNJ = "-- ==== UNJ01SP (sajptf) ===="

SQL_CLASSIFICACAO_SAJPTF = """
select idcard, numerotj
from sajptf.eptftarefa
where idcard = any(%(idcards)s)
"""


class ResetTool:

    def __init__(self, root, parent=None):
        self.root = root
        self.parent = parent or root

        # Mantém a execução independente do módulo e permite reutilizá-lo
        # como uma aba no aplicativo unificado.
        if parent is None:
            self.root.title("FIXATOOLS - Reset em Lote")
            self.root.geometry("1200x800")
            aplicar_tema(self.root)

        self.main_frame = ttk.Frame(
            self.parent,
            style="App.TFrame",
            padding=(16, 14, 16, 12),
        )
        self.main_frame.pack(fill="both", expand=True)

        cabecalho = ttk.Frame(self.main_frame, style="App.TFrame")
        cabecalho.pack(fill="x", pady=(0, 10))
        ttk.Label(
            cabecalho,
            text="Reset em Lote",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            cabecalho,
            text="Gere, revise e execute os comandos para os idcards informados.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self.cliente_status_var = tk.StringVar()
        self.cliente_status_label = ttk.Label(
            cabecalho,
            textvariable=self.cliente_status_var,
            style="ClientSP.TLabel",
            anchor="w",
        )
        self.cliente_status_label.pack(fill="x", pady=(10, 0))

        self.frame_topo = ttk.Frame(
            self.main_frame,
            style="Toolbar.TFrame",
            padding=8,
        )
        self.frame_topo.pack(fill="x", pady=(0, 10))

        self.btn_config = ttk.Button(
            self.frame_topo,
            text="⚙ Configurações",
            command=self.abrir_configuracoes,
            style="Secondary.TButton",
        )
        self.btn_config.pack(side="left")

        ttk.Label(
            self.frame_topo,
            text="Cliente do reset:",
            style="Hint.TLabel",
        ).pack(side="left", padx=(24, 8))

        self.cliente_var = tk.StringVar(value="SIGSP / UNJ01SP")
        self.combo_cliente = ttk.Combobox(
            self.frame_topo,
            textvariable=self.cliente_var,
            values=("SIGSP / UNJ01SP", "MPRS"),
            state="readonly",
            width=20,
        )
        self.combo_cliente.pack(side="left")
        self.combo_cliente.bind("<<ComboboxSelected>>", self.ao_alterar_cliente)
        self.cliente_geracao = self.cliente_var.get()
        self.atualizar_cliente_visual()

        entrada_frame = ttk.LabelFrame(
            self.main_frame,
            text="Idcards para reset",
            style="Card.TLabelframe",
            padding=10,
        )
        entrada_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            entrada_frame,
            text="Informe os idcards separados por vírgula. Exemplo: '2R000000FAGIW','2R000000G498H'",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        self.entry_idcards = tk.Text(
            entrada_frame,
            width=140,
            height=3,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            background="#fbfcfe",
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Consolas", 9),
        )
        self.entry_idcards.pack(fill="x")

        frame_botoes = ttk.Frame(self.main_frame, style="App.TFrame")
        frame_botoes.pack(fill="x", pady=(0, 10))

        self.btn_gerar = ttk.Button(
            frame_botoes,
            text="1) Gerar SQL (reset SAJ + ajuste sajptf)",
            command=self.gerar_sql,
            style="Secondary.TButton",
        )
        self.btn_gerar.pack(side="left")

        self.btn_executar = ttk.Button(
            frame_botoes,
            text="2) Executar SQL Gerado",
            command=self.executar_sql,
            state="disabled",
            style="Primary.TButton",
        )
        self.btn_executar.pack(side="left", padx=10)

        sql_frame = ttk.LabelFrame(
            self.main_frame,
            text="SQL gerado (revise ou edite antes de executar)",
            style="Card.TLabelframe",
            padding=8,
        )
        sql_frame.pack(fill="both", expand=True, pady=(0, 10))
        sql_frame.columnconfigure(0, weight=1)
        sql_frame.rowconfigure(0, weight=1)

        self.sql_text = tk.Text(
            sql_frame,
            width=140,
            height=16,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            background="#fbfcfe",
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Consolas", 9),
        )
        self.sql_text.grid(row=0, column=0, sticky="nsew")
        sql_scroll = ttk.Scrollbar(sql_frame, orient="vertical", command=self.sql_text.yview)
        sql_scroll.grid(row=0, column=1, sticky="ns")
        self.sql_text.configure(yscrollcommand=sql_scroll.set)

        log_frame = ttk.LabelFrame(
            self.main_frame,
            text="Log",
            style="Card.TLabelframe",
            padding=8,
        )
        log_frame.pack(fill="both", expand=True)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            width=150,
            height=9,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            background="#fbfcfe",
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Consolas", 9),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.tag_config("sucesso", foreground=COLORS["success_text"])
        self.log_text.tag_config("erro", foreground="#b91c1c")
        self.log_text.tag_config("normal", foreground="#334155")

    def cliente_mprs_selecionado(self):
        return self.cliente_var.get() == "MPRS"

    def atualizar_cliente_visual(self):
        if self.cliente_mprs_selecionado():
            self.cliente_status_var.set(
                "CLIENTE ATIVO: MPRS  •  sigrs + unj01rs  •  conexão direta"
            )
            self.cliente_status_label.configure(style="ClientMPRS.TLabel")
        else:
            self.cliente_status_var.set(
                "CLIENTE ATIVO: SIGSP / UNJ01SP  •  sigsp + unj01sp  •  conexão via túnel"
            )
            self.cliente_status_label.configure(style="ClientSP.TLabel")

    def ao_alterar_cliente(self, _evento=None):
        """Descarta SQL anterior para impedir executar em outro cliente."""
        self.atualizar_cliente_visual()
        self.sql_text.delete("1.0", tk.END)
        self.btn_executar.config(state="disabled")
        self.log(
            "Cliente selecionado: "
            + ("MPRS (conexão direta, sem túnel)." if self.cliente_mprs_selecionado()
               else "SIGSP / UNJ01SP (conexão via túnel).")
        )

    # ------------------------------------------------------------------
    # LOG
    # ------------------------------------------------------------------
    def log(self, mensagem, tipo="normal"):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        texto = f"[{agora}] {mensagem}"

        self.log_text.insert(tk.END, texto + "\n", tipo)
        self.log_text.see(tk.END)

        with open("reset_lote.log", "a", encoding="utf-8") as arq:
            arq.write(texto + "\n")

        self.root.update_idletasks()

    # ------------------------------------------------------------------
    # CONFIGURAÇÕES (igual ao projeto original)
    # ------------------------------------------------------------------
    def abrir_configuracoes(self):
        cred = config_manager.obter_credenciais()

        janela = tk.Toplevel(self.root)
        janela.title("Configurações de Acesso")
        janela.geometry("560x620")
        janela.resizable(False, False)
        janela.grab_set()

        conteudo = ttk.Frame(janela, padding=18)
        conteudo.pack(fill="both", expand=True)

        def criar_campo(parent, rotulo, valor, segredo=False):
            linha = ttk.Frame(parent)
            linha.pack(fill="x", pady=4)
            ttk.Label(linha, text=rotulo, width=18).pack(side="left")
            entrada = ttk.Entry(linha, show="*" if segredo else "")
            entrada.pack(side="left", fill="x", expand=True)
            entrada.insert(0, str(valor))
            return entrada

        ttk.Label(
            conteudo,
            text="Acessos do Reset em Lote",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        frame_atual = ttk.LabelFrame(
            conteudo,
            text="SIGSP / UNJ01SP — conexão atual via túnel",
            style="Card.TLabelframe",
            padding=10,
        )
        frame_atual.pack(fill="x", pady=(0, 12))
        entry_ssh_user = criar_campo(frame_atual, "Usuário SSH", cred["ssh_user"])
        entry_ssh_pass = criar_campo(frame_atual, "Senha SSH", cred["ssh_password"], True)
        entry_db_user = criar_campo(frame_atual, "Usuário banco", cred["db_user"])
        entry_db_pass = criar_campo(frame_atual, "Senha banco", cred["db_password"], True)

        frame_mprs = ttk.LabelFrame(
            conteudo,
            text="MPRS — conexão direta, sem túnel",
            style="Card.TLabelframe",
            padding=10,
        )
        frame_mprs.pack(fill="x", pady=(0, 12))
        ttk.Label(
            frame_mprs,
            text="Esses dados são usados apenas quando MPRS for selecionado.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 6))
        entry_mprs_host = criar_campo(frame_mprs, "Host", cred["mprs_host"])
        entry_mprs_port = criar_campo(frame_mprs, "Porta", cred["mprs_port"])
        entry_mprs_db_rs = criar_campo(frame_mprs, "Banco principal", cred["mprs_db_rs"])
        entry_mprs_db_unj = criar_campo(frame_mprs, "Banco sajptf", cred["mprs_db_unj"])
        entry_mprs_user = criar_campo(frame_mprs, "Usuário", cred["mprs_user"])
        entry_mprs_pass = criar_campo(frame_mprs, "Senha", cred["mprs_password"], True)

        def salvar():
            try:
                int(entry_mprs_port.get().strip())
            except ValueError:
                messagebox.showerror("Configurações", "A porta do MPRS deve ser numérica.")
                return

            config_manager.salvar_credenciais(
                ssh_user=entry_ssh_user.get().strip(),
                ssh_password=entry_ssh_pass.get(),
                db_user=entry_db_user.get().strip(),
                db_password=entry_db_pass.get(),
                mprs_host=entry_mprs_host.get().strip(),
                mprs_port=entry_mprs_port.get().strip(),
                mprs_db_rs=entry_mprs_db_rs.get().strip(),
                mprs_db_unj=entry_mprs_db_unj.get().strip(),
                mprs_user=entry_mprs_user.get().strip(),
                mprs_password=entry_mprs_pass.get(),
            )
            messagebox.showinfo("Configurações", "Credenciais salvas com sucesso.")
            janela.destroy()

        ttk.Button(
            conteudo,
            text="Salvar configurações",
            command=salvar,
            style="Primary.TButton",
        ).pack(anchor="e", pady=(2, 0))

    # ------------------------------------------------------------------
    # HELPERS DE PARSE
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_idcards_texto(texto):
        """
        Aceita:
            '2R000000FAGIW','2R000000G498H'
        Retorna lista de strings "limpas" (sem aspas/espaços).
        """
        texto = texto.strip()

        if not texto:
            return []

        partes = [p.strip() for p in texto.split(",")]

        idcards = []

        for p in partes:
            if not p:
                continue
            p = p.strip().strip("'").strip('"').strip()
            if p:
                idcards.append(p)

        return idcards

    @staticmethod
    def _classificar_tarefas_sajptf(idcards, linhas, fila_intimacao=39):
        """Classifica os idcards por fila usando o numerotj atual da sajptf."""
        tarefas_por_idcard = {
            str(row[0]).strip(): row[1]
            for row in linhas
            if row and row[0] is not None
        }

        filas = {1: [], 3: [], fila_intimacao: []}
        nao_encontrados = []
        nao_classificados = []

        for idcard in idcards:
            idcard_limpo = str(idcard).strip()
            if idcard_limpo not in tarefas_por_idcard:
                nao_encontrados.append(idcard_limpo)
                continue

            numerotj = tarefas_por_idcard[idcard_limpo]
            prefixo = idcard_limpo.upper()

            if numerotj is None:
                filas[3].append(idcard_limpo)
            elif prefixo.startswith("2R"):
                filas[fila_intimacao].append(idcard_limpo)
            elif prefixo.startswith("S6"):
                filas[1].append(idcard_limpo)
            else:
                nao_classificados.append(idcard_limpo)

        return filas, nao_encontrados, nao_classificados

    @staticmethod
    def _montar_updates_sajptf(filas, fila_intimacao=39):
        """Monta um UPDATE por fila, mantendo os grupos separados no preview."""
        descricoes = {
            3: "INICIAL (numerotj nulo)",
            fila_intimacao: "INTIMAÇÃO (numerotj preenchido + idcard 2R)",
            1: "TAREFA SEM INTIMAÇÃO (numerotj preenchido + idcard S6)",
        }
        validacoes = {
            3: "numerotj IS NULL",
            fila_intimacao: "numerotj IS NOT NULL AND UPPER(idcard) LIKE '2R%'",
            1: "numerotj IS NOT NULL AND UPPER(idcard) LIKE 'S6%'",
        }
        comandos = []

        for fila in (3, fila_intimacao, 1):
            idcards = filas[fila]
            if not idcards:
                continue

            lista_sql = ",".join(
                "'" + idcard.replace("'", "''") + "'"
                for idcard in idcards
            )
            comandos.append(f"-- Fila {fila}: {descricoes[fila]}")
            comandos.append(
                "UPDATE sajptf.eptftarefa "
                f"SET idstatus=0,idgrupo={fila} "
                f"WHERE idcard IN ({lista_sql}) AND {validacoes[fila]};"
            )

        if not comandos:
            comandos.append("-- Nenhum ajuste de fila foi classificado.")

        return comandos

    # Blocos de análise executados contra a base sigsp (saj).
    # Cada bloco roda separado (não é mais um UNION ALL único), e o
    # tempo de cada um é medido e logado.
    _BLOCOS_ANALISE_SIGSP = [
        (
            "efmppeticionamento",
            """
            select
                case
                    when a.flpeticionamento = 1 then
                        'UPDATE saj.efmppeticionamento SET cdprocesso=NULL, flstatus=5 WHERE cdpeticionamento=''' || a.cdpeticionamento::text || ''';'
                    else
                        'UPDATE saj.efmppeticionamento SET flstatus=5 WHERE cdpeticionamento=''' || a.cdpeticionamento::text || ''';'
                end
            from saj.efmppeticionamento a
            where a.idcard = ANY(%(idcards)s)
              and a.flstatus not in (5,2,4)
            """
        ),
        (
            "efmpintimacao",
            """
            select
                'UPDATE saj.efmpintimacao SET cdpeticionamento=NULL WHERE nuseqintimacao=' || b.nuseqintimacao::text || ';'
            from saj.efmpintimacao b
            where b.cdobjeto = ANY(%(idcards)s)
            """
        ),
        (
            "efmpexpediente",
            """
            select
                'UPDATE saj.efmpexpediente SET dtfinalizacao=NULL, idusuariofinalizacao=NULL, status=''Elaboracao'' WHERE id=''' || sub.id::text || ''';'
            from (
                select distinct on (c.idcard) c.id, c.idcard, c.dtfinalizacao
                from saj.efmpexpediente c
                where c.idcard = ANY(%(idcards)s)
                order by c.idcard, c.dtfinalizacao desc
            ) sub
            """
        ),
        (
            "efmppeticaocard",
            """
            select
                'DELETE FROM saj.efmppeticaocard WHERE cdpeticionamento='|| d.cdpeticionamento::text ||' AND idcard=''' || d.idcard::text || ''';'
            from saj.efmppeticaocard d
            where d.idcard = ANY(%(idcards)s)
            """
        ),
        (
            "efmppeticaoblobdoc",
            """
            select
                'DELETE FROM saj.efmppeticaoblobdoc WHERE cdpeticaoblobdoc=''' || e.cdpeticaoblobdoc::text || ''';'
            from saj.efmppeticaoblobdoc e
            where e.cdobjeto = ANY(%(idcards)s)
            """
        ),
        (
            "efmppetloteitem",
            """
            select
                'UPDATE saj.efmppetloteitem SET flstatus=''F'' WHERE cdpetloteitem=''' || f.cdpetloteitem::text || ''';'
            from saj.efmppetloteitem f
            where f.idcard = ANY(%(idcards)s) and f.flstatus = 'C'
            """
        ),
    ]

    # ------------------------------------------------------------------
    # GERAR SQL (sigsp + sajptf, usando os mesmos idcards)
    # ------------------------------------------------------------------
    def gerar_sql(self):
        texto = self.entry_idcards.get("1.0", tk.END)
        idcards = self._parse_idcards_texto(texto)

        if not idcards:
            messagebox.showwarning("Atenção", "Informe ao menos um idcard.")
            return

        self.btn_gerar.config(state="disabled")
        self.btn_executar.config(state="disabled")
        self.cliente_geracao = self.cliente_var.get()
        self.combo_cliente.config(state="disabled")

        Thread(
            target=self._gerar_sql_thread,
            args=(idcards,),
            daemon=True
        ).start()

    def _gerar_sql_thread(self, idcards):
        conn = None
        tunnel = None
        conn_unj = None
        tunnel_unj = None
        cliente_mprs = self.cliente_geracao == "MPRS"
        fila_intimacao = 11 if cliente_mprs else 39

        try:
            self.log(f"Gerando SQL para {len(idcards)} idcard(s)...")

            if cliente_mprs:
                self.log("Cliente MPRS selecionado: conexão direta, sem túnel.")
                conn = conectar_mprs()
            else:
                self.log("Cliente SIGSP / UNJ01SP selecionado: conexão via túnel.")
                conn, tunnel = conectar_sp()

            if not conn:
                self.log("Falha ao conectar ao banco (sigsp).", "erro")
                return

            cur = conn.cursor()

            statements_sigsp = []

            for nome, query in self._BLOCOS_ANALISE_SIGSP:

                inicio = time.time()

                cur.execute(query, {"idcards": idcards})

                linhas = cur.fetchall()

                duracao = time.time() - inicio

                statements_sigsp.extend(row[0] for row in linhas if row[0])

                tipo_log = "erro" if duracao > 3 else "normal"

                self.log(
                    f"Bloco {nome}: {duracao:.2f}s, {len(linhas)} linha(s) encontrada(s).",
                    tipo_log
                )

            # Antes de montar qualquer UPDATE na sajptf, consulta o
            # numerotj no banco UNJ01SP e classifica cada idcard por fila.
            self.log("Validando numerotj na sajptf antes de montar os ajustes...")
            if cliente_mprs:
                conn_unj = conectar_mprs_unj()
                if not conn_unj:
                    self.log(
                        "Falha ao conectar ao banco MPRS sajptf para validar numerotj.",
                        "erro"
                    )
                    return
                cur_unj = conn_unj.cursor()
            else:
                conn_unj, tunnel_unj = conectar_unj()

                if not conn_unj:
                    self.log(
                        "Falha ao conectar ao banco (unj01sp) para validar numerotj.",
                        "erro"
                    )
                    return

                cur_unj = conn_unj.cursor()
            cur_unj.execute(SQL_CLASSIFICACAO_SAJPTF, {"idcards": idcards})
            linhas_tarefas = cur_unj.fetchall()

            filas, nao_encontrados, nao_classificados = self._classificar_tarefas_sajptf(
                idcards,
                linhas_tarefas,
                fila_intimacao=fila_intimacao,
            )
            comandos_sajptf = self._montar_updates_sajptf(
                filas,
                fila_intimacao=fila_intimacao,
            )

            self.log(
                f"Classificação sajptf: fila 3={len(filas[3])}, "
                f"fila {fila_intimacao}={len(filas[fila_intimacao])}, "
                f"fila 1={len(filas[1])}.",
                "sucesso"
            )

            if nao_encontrados:
                self.log(
                    "Idcard(s) não encontrado(s) na sajptf: "
                    + ", ".join(nao_encontrados),
                    "erro"
                )

            if nao_classificados:
                self.log(
                    "Idcard(s) sem regra de fila (não alterados): "
                    + ", ".join(nao_classificados),
                    "erro"
                )

            self.sql_text.delete("1.0", tk.END)

            partes = []

            partes.append(MARCA_MPRS if cliente_mprs else MARCA_SIGSP)
            if statements_sigsp:
                partes.extend(statements_sigsp)
            else:
                partes.append("-- Nenhum comando gerado para os idcards informados.")

            if not cliente_mprs:
                partes.append("")
                partes.append(MARCA_UNJ)
            else:
                partes.append("")
                partes.append(MARCA_MPRS_UNJ)
            partes.extend(comandos_sajptf)

            self.sql_text.insert(tk.END, "\n".join(partes))

            self.log(
                f"{len(statements_sigsp)} comando(s) de reset + "
                f"{len([idcard for fila in filas.values() for idcard in fila])} "
                "ajuste(s) sajptf classificado(s). "
                "Revise antes de executar.",
                "sucesso"
            )

            self.btn_executar.config(state="normal")

        except Exception as e:
            self.log(f"ERRO ao gerar SQL: {e}", "erro")

        finally:
            try:
                if conn:
                    conn.close()
            except:
                pass
            try:
                if tunnel:
                    tunnel.stop()
            except:
                pass
            try:
                if conn_unj:
                    conn_unj.close()
            except:
                pass
            try:
                if tunnel_unj:
                    tunnel_unj.stop()
            except:
                pass

            self.btn_gerar.config(state="normal")
            self.combo_cliente.config(state="readonly")

    # ------------------------------------------------------------------
    # EXECUTAR SQL (roteia cada seção pra base certa)
    # ------------------------------------------------------------------
    def executar_sql(self):
        conteudo = self.sql_text.get("1.0", tk.END).strip()

        if not conteudo:
            messagebox.showwarning("Atenção", "Não há SQL gerado para executar.")
            return

        if not messagebox.askyesno(
            "Confirmar execução",
            "Confirma a execução dos comandos SQL exibidos na tela?\n"
            "O cliente selecionado e os registros correspondentes serão alterados."
        ):
            return

        self.btn_executar.config(state="disabled")
        self.btn_gerar.config(state="disabled")

        Thread(
            target=self._executar_sql_thread,
            args=(conteudo,),
            daemon=True
        ).start()

    @staticmethod
    def _separar_comandos_por_base(conteudo):
        """
        Lê o texto gerado e separa os comandos por cliente/base.
        """
        alvo_atual = None
        comandos_sigsp = []
        comandos_unj = []
        comandos_mprs = []
        comandos_mprs_unj = []

        for linha in conteudo.splitlines():
            linha_strip = linha.strip()

            if not linha_strip:
                continue

            if linha_strip == MARCA_SIGSP:
                alvo_atual = "sigsp"
                continue

            if linha_strip == MARCA_MPRS:
                alvo_atual = "mprs"
                continue

            if linha_strip == MARCA_MPRS_UNJ:
                alvo_atual = "mprs_unj"
                continue

            if linha_strip == MARCA_UNJ:
                alvo_atual = "unj"
                continue

            if linha_strip.startswith("--"):
                continue

            if alvo_atual == "sigsp":
                comandos_sigsp.append(linha_strip)
            elif alvo_atual == "mprs":
                comandos_mprs.append(linha_strip)
            elif alvo_atual == "mprs_unj":
                comandos_mprs_unj.append(linha_strip)
            elif alvo_atual == "unj":
                comandos_unj.append(linha_strip)

        return comandos_sigsp, comandos_unj, comandos_mprs, comandos_mprs_unj

    def _executar_sql_thread(self, conteudo):
        conn = None
        tunnel = None
        conn_unj = None
        tunnel_unj = None
        conn_mprs = None
        conn_mprs_unj = None

        try:
            (
                comandos_sigsp,
                comandos_unj,
                comandos_mprs,
                comandos_mprs_unj,
            ) = self._separar_comandos_por_base(conteudo)

            # -------- SIGSP --------
            if comandos_sigsp:

                conn, tunnel = conectar_sp()

                if not conn:
                    self.log("Falha ao conectar ao banco (sigsp).", "erro")
                    return

                cur = conn.cursor()

                self.log(f"Executando {len(comandos_sigsp)} comando(s) no sigsp...")

                erros = 0

                for comando in comandos_sigsp:
                    try:
                        cur.execute(comando)
                        self.log(f"OK: {comando}", "sucesso")
                    except Exception as e:
                        conn.rollback()
                        erros += 1
                        self.log(f"ERRO: {comando} -> {e}", "erro")

                conn.commit()

                self.log(
                    f"sigsp finalizado. {len(comandos_sigsp) - erros} OK / {erros} erro(s).",
                    "sucesso" if erros == 0 else "erro"
                )
            else:
                self.log("Nenhum comando de sigsp para executar.")

            # -------- MPRS (saj) --------
            if comandos_mprs:
                conn_mprs = conectar_mprs()

                if not conn_mprs:
                    self.log("Falha ao conectar ao banco MPRS.", "erro")
                    return

                cur_mprs = conn_mprs.cursor()
                self.log(
                    f"Executando {len(comandos_mprs)} comando(s) no MPRS..."
                )
                erros_mprs = 0

                for comando in comandos_mprs:
                    try:
                        cur_mprs.execute(comando)
                        self.log(f"OK MPRS: {comando}", "sucesso")
                    except Exception as e:
                        conn_mprs.rollback()
                        erros_mprs += 1
                        self.log(f"ERRO MPRS: {comando} -> {e}", "erro")

                conn_mprs.commit()
                self.log(
                    f"MPRS finalizado. "
                    f"{len(comandos_mprs) - erros_mprs} OK / {erros_mprs} erro(s).",
                    "sucesso" if erros_mprs == 0 else "erro"
                )

            # -------- MPRS (sajptf) --------
            if comandos_mprs_unj:
                conn_mprs_unj = conectar_mprs_unj()

                if not conn_mprs_unj:
                    self.log("Falha ao conectar ao banco MPRS sajptf.", "erro")
                    return

                cur_mprs_unj = conn_mprs_unj.cursor()
                comando_mprs_unj = " ".join(comandos_mprs_unj)

                self.log("Executando ajuste em sajptf.eptftarefa do MPRS...")

                try:
                    cur_mprs_unj.execute(comando_mprs_unj)
                    conn_mprs_unj.commit()

                    self.log(
                        "sajptf.eptftarefa do MPRS atualizado. "
                        f"Linhas afetadas: {cur_mprs_unj.rowcount}.",
                        "sucesso"
                    )
                except Exception as e:
                    conn_mprs_unj.rollback()
                    self.log(f"ERRO ao executar UPDATE no sajptf do MPRS: {e}", "erro")

            # -------- UNJ01SP (sajptf) --------
            if comandos_unj:

                conn_unj, tunnel_unj = conectar_unj()

                if not conn_unj:
                    self.log("Falha ao conectar ao banco (unj01sp).", "erro")
                    return

                cur_unj = conn_unj.cursor()

                comando_unj = " ".join(comandos_unj)

                self.log("Executando ajuste em sajptf.eptftarefa...")

                try:
                    cur_unj.execute(comando_unj)
                    conn_unj.commit()

                    self.log(
                        f"sajptf.eptftarefa atualizado. Linhas afetadas: {cur_unj.rowcount}.",
                        "sucesso"
                    )
                except Exception as e:
                    conn_unj.rollback()
                    self.log(f"ERRO ao executar UPDATE em sajptf: {e}", "erro")
            else:
                self.log("Nenhum comando de sajptf para executar.")

        except Exception as e:
            self.log(f"ERRO FATAL: {e}", "erro")

        finally:
            try:
                if conn:
                    conn.close()
            except:
                pass
            try:
                if tunnel:
                    tunnel.stop()
            except:
                pass
            try:
                if conn_unj:
                    conn_unj.close()
            except:
                pass
            try:
                if tunnel_unj:
                    tunnel_unj.stop()
            except:
                pass
            try:
                if conn_mprs:
                    conn_mprs.close()
            except:
                pass
            try:
                if conn_mprs_unj:
                    conn_mprs_unj.close()
            except:
                pass

            self.btn_executar.config(state="normal")
            self.btn_gerar.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = ResetTool(root)
    root.mainloop()
