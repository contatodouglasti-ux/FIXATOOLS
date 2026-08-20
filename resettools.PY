import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from datetime import datetime
import time

from connectionSP import conectar as conectar_sp
from connectionSPunj import conectar as conectar_unj
import config_manager
from ui_helpers import aplicar_tema, COLORS

MARCA_SIGSP = "-- ==== SIGSP (saj) ===="
MARCA_UNJ = "-- ==== UNJ01SP (sajptf) ===="


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
        janela.geometry("380x260")
        janela.resizable(False, False)
        janela.grab_set()

        tk.Label(janela, text="Usuário SSH:").pack(anchor="w", padx=20, pady=(15, 0))
        entry_ssh_user = tk.Entry(janela, width=40)
        entry_ssh_user.pack(padx=20)
        entry_ssh_user.insert(0, cred["ssh_user"])

        tk.Label(janela, text="Senha SSH:").pack(anchor="w", padx=20, pady=(10, 0))
        entry_ssh_pass = tk.Entry(janela, width=40, show="*")
        entry_ssh_pass.pack(padx=20)
        entry_ssh_pass.insert(0, cred["ssh_password"])

        tk.Label(janela, text="Usuário Banco:").pack(anchor="w", padx=20, pady=(10, 0))
        entry_db_user = tk.Entry(janela, width=40)
        entry_db_user.pack(padx=20)
        entry_db_user.insert(0, cred["db_user"])

        tk.Label(janela, text="Senha Banco:").pack(anchor="w", padx=20, pady=(10, 0))
        entry_db_pass = tk.Entry(janela, width=40, show="*")
        entry_db_pass.pack(padx=20)
        entry_db_pass.insert(0, cred["db_password"])

        def salvar():
            config_manager.salvar_credenciais(
                ssh_user=entry_ssh_user.get().strip(),
                ssh_password=entry_ssh_pass.get(),
                db_user=entry_db_user.get().strip(),
                db_password=entry_db_pass.get()
            )
            messagebox.showinfo("Configurações", "Credenciais salvas com sucesso.")
            janela.destroy()

        tk.Button(janela, text="Salvar", command=salvar).pack(pady=20)

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

        Thread(
            target=self._gerar_sql_thread,
            args=(idcards,),
            daemon=True
        ).start()

    def _gerar_sql_thread(self, idcards):
        conn = None
        tunnel = None

        try:
            self.log(f"Gerando SQL para {len(idcards)} idcard(s)...")

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

            # Ajuste sajptf.eptftarefa usa o MESMO idcard informado acima,
            # não precisa consultar o banco pra gerar, é só template.
            lista_sql = ",".join(
                "'" + i.replace("'", "''") + "'"
                for i in idcards
            )

            sql_sajptf = (
                f"UPDATE sajptf.eptftarefa\n"
                f"\tSET idstatus=0,idgrupo=39\n"
                f"\tWHERE idcard IN ({lista_sql});"
            )

            self.sql_text.delete("1.0", tk.END)

            partes = []

            partes.append(MARCA_SIGSP)
            if statements_sigsp:
                partes.extend(statements_sigsp)
            else:
                partes.append("-- Nenhum comando gerado para os idcards informados.")

            partes.append("")
            partes.append(MARCA_UNJ)
            partes.append(sql_sajptf)

            self.sql_text.insert(tk.END, "\n".join(partes))

            self.log(
                f"{len(statements_sigsp)} comando(s) de reset + 1 ajuste sajptf gerado(s). "
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

            self.btn_gerar.config(state="normal")

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
            "Essa ação altera dados nos bancos sigsp e unj01sp."
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
        Lê o texto gerado e separa os comandos entre sigsp e unj,
        usando as marcações MARCA_SIGSP / MARCA_UNJ como divisor.
        """
        alvo_atual = None
        comandos_sigsp = []
        comandos_unj = []

        for linha in conteudo.splitlines():
            linha_strip = linha.strip()

            if not linha_strip:
                continue

            if linha_strip == MARCA_SIGSP:
                alvo_atual = "sigsp"
                continue

            if linha_strip == MARCA_UNJ:
                alvo_atual = "unj"
                continue

            if linha_strip.startswith("--"):
                continue

            if alvo_atual == "sigsp":
                comandos_sigsp.append(linha_strip)
            elif alvo_atual == "unj":
                comandos_unj.append(linha_strip)

        return comandos_sigsp, comandos_unj

    def _executar_sql_thread(self, conteudo):
        conn = None
        tunnel = None
        conn_unj = None
        tunnel_unj = None

        try:
            comandos_sigsp, comandos_unj = self._separar_comandos_por_base(conteudo)

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

            self.btn_executar.config(state="normal")
            self.btn_gerar.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = ResetTool(root)
    root.mainloop()
