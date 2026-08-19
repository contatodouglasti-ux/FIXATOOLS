import os
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from datetime import datetime
import time
import re

from connectionSP import conectar as conectar_sp
from connectionSPunj import conectar as conectar_unj
import config_manager

TEMPO_LIMITE = 180
INTERVALO_CONSULTA = 10
INTERVALO_REEXECUCAO = 1 * 60 * 60 * 1000  # 2 horas em milissegundos
CDFORO_FIXO_INSERT = 23


class BotReprocessamento:

    def __init__(self, root):

        self.root = root
        self.root.title("FIXATOOLS")
        self.root.geometry("1200x700")

        self.total = 0
        self.sucessos = 0
        self.pendentes = 0
        self.agendamento_automatico_ativo = False
        self.timer_execucao_id = None

        self.frame_topo = tk.Frame(root)
        self.frame_topo.pack(fill="x", padx=10, pady=5)

        self.btn_config = tk.Button(
            self.frame_topo,
            text="⚙ Configurações",
            command=self.abrir_configuracoes
        )
        self.btn_config.pack(side="left")

        self.btn_atualizar_total = tk.Button(
            self.frame_topo,
            text="🔄 Atualizar Total",
            command=self.atualizar_total
        )
        self.btn_atualizar_total.pack(side="left", padx=10)

        self.btn_agendamento = tk.Button(
            self.frame_topo,
            text="Agendamento Automático: DESLIGADO",
            command=self.alternar_agendamento
        )
        self.btn_agendamento.pack(side="left", padx=10)

        self.lbl_total = tk.Label(
            root,
            text="Encontrados: 0",
            font=("Arial", 10, "bold")
        )
        self.lbl_total.pack(pady=5)

        self.lbl_sucesso = tk.Label(
            root,
            text="Sucesso: 0",
            fg="green",
            font=("Arial", 10, "bold")
        )
        self.lbl_sucesso.pack()

        self.lbl_pendente = tk.Label(
            root,
            text="Pendentes: 0",
            fg="orange",
            font=("Arial", 10, "bold")
        )
        self.lbl_pendente.pack()

        self.btn_executar = tk.Button(
            root,
            text="Executar Processo",
            command=self.executar
        )
        self.btn_executar.pack(pady=10)

        self.log_text = tk.Text(
            root,
            width=150,
            height=25
        )
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_config("sucesso", foreground="green")
        self.log_text.tag_config("erro", foreground="red")
        self.log_text.tag_config("timeout", foreground="orange")
        self.log_text.tag_config("normal", foreground="black")

        tk.Label(
            root,
            text="SQL Pendentes"
        ).pack()

        self.sql_text = tk.Text(
            root,
            width=150,
            height=8
        )
        self.sql_text.pack(fill="x")

        Thread(
            target=self.carregar_contagem_inicial,
            daemon=True
        ).start()

    # =========================================================
    # UTILITÁRIOS
    # =========================================================

    def obter_nome_arquivo_log(self):
        data_hoje = datetime.now().strftime("%Y-%m-%d")
        pasta_logs = "logs"
        os.makedirs(pasta_logs, exist_ok=True)
        return os.path.join(pasta_logs, f"reprocessamento_{data_hoje}.log")

    def log(self, mensagem, tipo="normal"):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        texto = f"[{agora}] {mensagem}"

        self.log_text.insert(tk.END, texto + "\n", tipo)
        self.log_text.see(tk.END)

        nome_arquivo = self.obter_nome_arquivo_log()
        with open(nome_arquivo, "a", encoding="utf-8") as arq:
            arq.write(texto + "\n")

        self.root.update_idletasks()

    def extrair_nome_foro(self, observacao):
        if not observacao:
            return None

        match = re.search(r'"([^"]+)"', observacao)
        if match:
            return match.group(1).strip()

        return None

    def buscar_cdforo_por_nome(self, cur, nome_foro):
        try:
            cur.execute(
                """
                select cdforo
                from saj.efmptjforo
                where trim(nmforo) = %s
                """,
                (nome_foro.strip(),)
            )
            row = cur.fetchone()
            if row:
                return row[0]
        except Exception as e:
            self.log(
                f"Erro ao buscar cdforo para '{nome_foro}': {e}",
                "erro"
            )
        return None

    def montar_insert_sql(self, cdtipolocal, cdlocal, cdcomarca):
        return f"""
        insert into SAJ.EFMPLOCALCOMARCA (
            CDFORO,
            CDTIPOLOCAL,
            CDLOCAL,
            CDCOMARCA,
            FLCOMARCASEDE
        ) values (
            {CDFORO_FIXO_INSERT},
            {int(cdtipolocal)},
            {int(cdlocal)},
            {int(cdcomarca)},
            'N'
        ) on conflict do nothing;
        """

    def montar_insert_vinc_local_origem(self, cdtipolocal, cdlocal, cdorigem):
        sql = """
        insert into SAJ.EFMPVINCLOCALORIGEM (
            CDFORO,
            CDTIPOLOCAL,
            CDLOCAL,
            CDORIGEM,
            FLINTEGRADO
        ) values (
            %s,
            %s,
            %s,
            %s,
            %s
        ) on conflict do nothing;
        """
        params = (
            CDFORO_FIXO_INSERT,
            int(cdtipolocal),
            int(cdlocal),
            int(cdorigem),
            'S'
        )
        return sql, params

    def aplicar_reprocessamento(self, cur, conn, nuseq):
        cur.execute(
            """
            update efmptjlotecargait
            set
                nucontarobo = 0,
                flstatusrobo = 'F',
                dtexpirarobo = null,
                cdsituacaoitem = 1,
                flstatus = 177
            where nuseqintimacao = %s
            """,
            (nuseq,)
        )
        conn.commit()

    def atualizar_texto_botao_agendamento(self):
        if self.agendamento_automatico_ativo:
            self.btn_agendamento.config(text="Agendamento Automático: LIGADO")
        else:
            self.btn_agendamento.config(text="Agendamento Automático: DESLIGADO")

    def alternar_agendamento(self):
        self.agendamento_automatico_ativo = not self.agendamento_automatico_ativo
        self.atualizar_texto_botao_agendamento()

        if self.agendamento_automatico_ativo:
            self.log("Agendamento automático ativado.", "normal")
            self.agendar_proxima_execucao()
        else:
            if self.timer_execucao_id is not None:
                try:
                    self.root.after_cancel(self.timer_execucao_id)
                except Exception:
                    pass
                self.timer_execucao_id = None
            self.log("Agendamento automático desativado.", "normal")

    def agendar_proxima_execucao(self):
        if not self.agendamento_automatico_ativo:
            return

        if self.timer_execucao_id is not None:
            try:
                self.root.after_cancel(self.timer_execucao_id)
            except Exception:
                pass

        self.timer_execucao_id = self.root.after(
            INTERVALO_REEXECUCAO,
            self._executar_agendada
        )

        self.log("Próxima execução automática agendada para daqui 1h.")

    def _executar_agendada(self):
        self.timer_execucao_id = None

        if not self.agendamento_automatico_ativo:
            return

        self.log("Iniciando execução automática agendada.")
        self.executar()

    # =========================================================
    # CONSULTA DE TOTAL
    # =========================================================

    def carregar_contagem_inicial(self):
        self._consultar_total(mostrar_aviso=False)

    def atualizar_total(self):
        if self.btn_executar["state"] == "disabled":
            messagebox.showinfo(
                "Aguarde",
                "O processo principal está em execução. "
                "Aguarde finalizar para atualizar o total."
            )
            return

        self.btn_atualizar_total.config(state="disabled")

        Thread(
            target=self._consultar_total,
            kwargs={"mostrar_aviso": True},
            daemon=True
        ).start()

    def _consultar_total(self, mostrar_aviso=False):
        conn = None
        tunnel = None

        try:
            conn, tunnel = conectar_sp()

            if not conn:
                if mostrar_aviso:
                    self.log(
                        "Falha ao conectar ao banco para atualizar o total.",
                        "erro"
                    )
                return

            cur = conn.cursor()

            sql_count = """
            select count(*)
            from saj.efmptjlotecargait i
            join saj.esajlocal l
                 on i.cdlocaldestino = l.cdlocal
                and i.cdtipolocaldestino = l.cdtipolocal
            join saj.efmpintimacaoelet e
                 on i.nuseqintimacao = e.nuseqintimacao
            left join saj.efmpintimacao int
                 on int.nuseqintimacao = i.nuseqintimacaouni
            where flstatus in (-1)
              and i.nucontarobo not in (16,15,17)
              and i.nuseqintimacao is not null
              and i.dtusuinclusao >= current_date - 5
              and i.deobservacao ~* 'O processo recebido se encontra no Poder Judiciário para o foro'
            """

            cur.execute(sql_count)
            total = cur.fetchone()[0]

            self.total = total
            self.lbl_total.config(text=f"Encontrados: {self.total}")

            if mostrar_aviso:
                self.log(f"Total atualizado: {self.total} registros encontrados.")

        except Exception as e:
            if mostrar_aviso:
                self.log(f"Erro ao atualizar total: {e}", "erro")
            else:
                print(f"Erro ao carregar contagem inicial: {e}")

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

            self.btn_atualizar_total.config(state="normal")

    # =========================================================
    # CONFIGURAÇÕES
    # =========================================================

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

    # =========================================================
    # EXECUÇÃO PRINCIPAL
    # =========================================================

    def executar(self):
        if self.btn_atualizar_total["state"] == "disabled":
            messagebox.showinfo(
                "Aguarde",
                "A atualização do total está em execução. "
                "Aguarde finalizar para iniciar o processo."
            )
            return

        self.btn_executar.config(state="disabled")

        Thread(
            target=self.processo,
            daemon=True
        ).start()

    def construir_sql_inicial(self):
        return """
        select
            l.cdtipolocal,
            l.cdlocal,
            e.cdforo,
            i.nuseqintimacao,
            int.cdobjeto,
            i.cdorigem,
            i.deobservacao,
            i.nuprocessoexterno
        from saj.efmptjlotecargait i
        join saj.esajlocal l
             on i.cdlocaldestino = l.cdlocal
            and i.cdtipolocaldestino = l.cdtipolocal
        join saj.efmpintimacaoelet e
             on i.nuseqintimacao = e.nuseqintimacao
        left join saj.efmpintimacao int
             on int.nuseqintimacao = i.nuseqintimacaouni
        where flstatus in (-1)
          and i.nucontarobo not in (16,15,17)
          and i.nuseqintimacao is not null
          and i.dtusuinclusao >= current_date - 5
          and i.deobservacao ~* 'O processo recebido se encontra no Poder Judiciário para o foro'
        order by l.cdtipolocal, l.cdforo
        """

    def obter_registros(self, cur):
        cur.execute(self.construir_sql_inicial())

        registros = []
        for row in cur.fetchall():
            registros.append({
                "cdtipolocal": int(row[0]),
                "cdlocal": int(row[1]),
                "cdcomarca_original": int(row[2]) if row[2] is not None else None,
                "nuseq": int(row[3]),
                "cdobjeto": row[4],
                "cdorigem": int(row[5]) if row[5] is not None else None,
                "deobservacao": row[6],
                "nuprocessoexterno": row[7],
                "tentou_vinc_origem": False,
                "tentou_correcao_foro": False,
                "cdcomarca_usada": int(row[2]) if row[2] is not None else None
            })

        return registros

    def executar_inserts(self, cur, conn, registros):
        self.log("Executando inserts iniciais...")

        inserts_executados = set()

        for item in registros:
            chave_insert = (
                item["cdtipolocal"],
                item["cdlocal"],
                item["cdcomarca_usada"]
            )

            if chave_insert in inserts_executados:
                self.log(
                    f"INSERT DUPLICADO IGNORADO - NUSEQ {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}",
                    "normal"
                )
                continue

            insert_sql = self.montar_insert_sql(
                item["cdtipolocal"],
                item["cdlocal"],
                item["cdcomarca_usada"]
            )

            try:
                cur.execute(insert_sql)
                conn.commit()
                inserts_executados.add(chave_insert)

                self.log(
                    f"INSERT OK - NUSEQ {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}"
                )

            except Exception as e:
                conn.rollback()
                self.log(
                    f"ERRO INSERT {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']} - {e}",
                    "erro"
                )

        self.log("Todos os inserts iniciais executados.")

    def iniciar_reprocessamento(self, cur, conn, registros):
        for item in registros:
            try:
                self.log(
                    f"Reprocessando NUSEQ {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}",
                    "normal"
                )
                self.aplicar_reprocessamento(cur, conn, item["nuseq"])
            except Exception as e:
                self.log(
                    f"ERRO AO REPROCESSAR NUSEQ {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}: {e}",
                    "erro"
                )

        self.log("Reprocessamento inicial iniciado.")

    def atualizar_tarefa_unj(self, cur_unj, conn_unj, cdobjeto):
        sql_update = """
        UPDATE sajptf.eptftarefa
        SET idgrupo = 39
        WHERE idcard = %s
        """

        cur_unj.execute(sql_update, (str(cdobjeto),))
        conn_unj.commit()

    def consultar_vinculo_local_origem(self, cur, nuseq):
        sql = """
        select
            l.cdtipolocal,
            l.cdlocal,
            i.cdorigem,
            i.nuseqintimacao,
            int.cdobjeto,
            i.nuprocessoexterno
        from saj.efmptjlotecargait i
        join saj.esajlocal l
             on i.cdlocaldestino = l.cdlocal
            and i.cdtipolocaldestino = l.cdtipolocal
        join saj.efmpintimacaoelet e
             on i.nuseqintimacao = e.nuseqintimacao
        left join saj.efmpintimacao int
             on int.nuseqintimacao = i.nuseqintimacaouni
        where flstatus not in (-2, 0, 160, 161, 32)
          and i.nuseqintimacao is not null
          and i.dtusuinclusao >= current_date - 10
          and i.deobservacao like %s
          and i.nuseqintimacao = %s
        order by l.cdtipolocal, l.cdforo
        limit 1
        """

        cur.execute(
            sql,
            ('%a lotação atual não possui vínculo com o mesmo. %', nuseq)
        )
        row = cur.fetchone()

        if not row:
            return None

        return {
            "cdtipolocal": int(row[0]),
            "cdlocal": int(row[1]),
            "cdorigem": int(row[2]) if row[2] is not None else None,
            "nuseq": int(row[3]),
            "cdobjeto": row[4],
            "nuprocessoexterno": row[5],
        }

    def tentar_vinculo_local_origem(self, cur, conn, nuseq):
        dados = self.consultar_vinculo_local_origem(cur, nuseq)

        if not dados:
            raise ValueError(
                f"Nenhum registro encontrado para a nova consulta do NUSEQ {nuseq}"
            )

        if dados["cdorigem"] is None:
            raise ValueError(f"CDORIGEM nulo para o NUSEQ {nuseq}")

        insert_sql, params = self.montar_insert_vinc_local_origem(
            dados["cdtipolocal"],
            dados["cdlocal"],
            dados["cdorigem"]
        )

        cur.execute(insert_sql, params)
        conn.commit()

        self.log(
            f"INSERT EFMPVINCLOCALORIGEM executado - NUSEQ {nuseq} | NUPROCESSOEXTERNO {dados['nuprocessoexterno']} / CDORIGEM {dados['cdorigem']}",
            "sucesso"
        )

        self.aplicar_reprocessamento(cur, conn, nuseq)

        self.log(
            f"NUSEQ {nuseq} | NUPROCESSOEXTERNO {dados['nuprocessoexterno']} reprocessado novamente após INSERT em EFMPVINCLOCALORIGEM.",
            "normal"
        )

    def tentar_correcao_foro(self, cur, conn, item, nuseq):
        nome_foro = self.extrair_nome_foro(item["deobservacao"])

        if not nome_foro:
            raise ValueError(
                f"Não foi possível extrair o nome do foro da observação do NUSEQ {nuseq}"
            )

        cdcomarca_encontrada = self.buscar_cdforo_por_nome(cur, nome_foro)

        if cdcomarca_encontrada is None:
            raise ValueError(
                f"FORO '{nome_foro}' não encontrado na tabela saj.efmptjforo"
            )

        self.log(
            f"FORO IDENTIFICADO: '{nome_foro}' -> CDCOMARCA {cdcomarca_encontrada}",
            "normal"
        )

        insert_corrigido = self.montar_insert_sql(
            item["cdtipolocal"],
            item["cdlocal"],
            cdcomarca_encontrada
        )

        cur.execute(insert_corrigido)
        conn.commit()

        item["tentou_correcao_foro"] = True
        item["cdcomarca_usada"] = cdcomarca_encontrada

        self.log(
            f"INSERT CORRIGIDO EXECUTADO - NUSEQ {nuseq} | NUPROCESSOEXTERNO {item['nuprocessoexterno']} com CDCOMARCA {cdcomarca_encontrada}",
            "sucesso"
        )

        self.aplicar_reprocessamento(cur, conn, nuseq)

        self.log(
            f"NUSEQ {nuseq} | NUPROCESSOEXTERNO {item['nuprocessoexterno']} reprocessado novamente após correção do foro.",
            "normal"
        )

    def monitorar_registros(self, cur, cur_unj, conn, conn_unj, registros):
        mapa_objetos = {r["nuseq"]: r["cdobjeto"] for r in registros}
        mapa_registros = {r["nuseq"]: r for r in registros}
        inicio = {r["nuseq"]: time.time() for r in registros}

        sucesso = []
        pendentes = []
        finalizados = set()

        lista_ids = ",".join(str(x["nuseq"]) for x in registros)

        while True:
            sql_status = f"""
            select
                nuseqintimacao,
                flstatus
            from saj.efmptjlotecargait
            where nuseqintimacao in ({lista_ids})
            """

            cur.execute(sql_status)
            resultado = cur.fetchall()

            for nuseq, flstatus in resultado:
                if nuseq in finalizados:
                    continue

                item_reg = mapa_registros.get(nuseq)
                nuprocessoexterno = item_reg["nuprocessoexterno"] if item_reg else None

                self.log(
                    f"NUSEQ {nuseq} | NUPROCESSOEXTERNO {nuprocessoexterno} STATUS {flstatus}"
                )

                if flstatus == 161:
                    cdobjeto = mapa_objetos.get(nuseq)

                    try:
                        self.atualizar_tarefa_unj(cur_unj, conn_unj, cdobjeto)

                        sucesso.append(nuseq)
                        finalizados.add(nuseq)

                        self.sucessos = len(sucesso)
                        self.lbl_sucesso.config(text=f"Sucesso: {self.sucessos}")

                        self.log(
                            f"SUCESSO: NUSEQ {nuseq} | NUPROCESSOEXTERNO {nuprocessoexterno} -> ID {cdobjeto} atualizado para grupo 39",
                            "sucesso"
                        )

                    except Exception as e:
                        conn_unj.rollback()

                        pendentes.append(nuseq)
                        finalizados.add(nuseq)

                        self.pendentes = len(pendentes)
                        self.lbl_pendente.config(text=f"Pendentes: {self.pendentes}")

                        self.log(
                            f"ERRO AO ATUALIZAR {cdobjeto} | NUSEQ {nuseq} | NUPROCESSOEXTERNO {nuprocessoexterno}: {e}",
                            "erro"
                        )

                else:
                    tempo = time.time() - inicio[nuseq]

                    if tempo >= TEMPO_LIMITE:
                        item = mapa_registros.get(nuseq)

                        # 1ª tentativa: consulta nova + insert em EFMPVINCLOCALORIGEM
                        if item and not item["tentou_vinc_origem"]:
                            try:
                                self.tentar_vinculo_local_origem(cur, conn, nuseq)
                                item["tentou_vinc_origem"] = True
                                inicio[nuseq] = time.time()
                                continue
                            except Exception as e:
                                conn.rollback()
                                self.log(
                                    f"ERRO AO EXECUTAR INSERT EFMPVINCLOCALORIGEM PARA NUSEQ {nuseq} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}: {e}",
                                    "erro"
                                )
                                item["tentou_vinc_origem"] = True
                                inicio[nuseq] = time.time()
                                continue

                        # 2ª tentativa: correção do foro via efmptjforo
                        if item and item["tentou_vinc_origem"] and not item["tentou_correcao_foro"]:
                            try:
                                self.tentar_correcao_foro(cur, conn, item, nuseq)
                                item["tentou_correcao_foro"] = True
                                inicio[nuseq] = time.time()
                                continue
                            except Exception as e:
                                conn.rollback()
                                self.log(
                                    f"ERRO AO EXECUTAR CORREÇÃO DO FORO PARA NUSEQ {nuseq} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}: {e}",
                                    "erro"
                                )
                                item["tentou_correcao_foro"] = True
                                inicio[nuseq] = time.time()
                                continue

                        pendentes.append(nuseq)
                        finalizados.add(nuseq)

                        self.pendentes = len(pendentes)
                        self.lbl_pendente.config(text=f"Pendentes: {self.pendentes}")

                        self.log(
                            f"TIMEOUT: NUSEQ {nuseq} | NUPROCESSOEXTERNO {nuprocessoexterno} não chegou ao status 161 após as duas tentativas",
                            "timeout"
                        )

            if len(finalizados) == len(registros):
                break

            time.sleep(INTERVALO_CONSULTA)

        return sucesso, pendentes

    def gerar_sql_pendentes(self, pendentes):
        if not pendentes:
            self.sql_text.insert(tk.END, "Nenhum pendente encontrado.")
            self.log("Nenhum pendente encontrado.")
            return

        ids_pendentes = ",".join(str(x) for x in pendentes)

        sql_pendente = f"""
select *
from saj.efmptjlotecargait
where nuseqintimacao in (
    {ids_pendentes}
);
"""

        self.sql_text.insert(tk.END, sql_pendente)
        self.log("SQL de pendentes gerado.")

    def processo(self):
        conn = None
        tunnel = None
        conn_unj = None
        tunnel_unj = None

        try:
            conn, tunnel = conectar_sp()

            if not conn:
                self.log("Falha ao conectar ao banco (sigsp).", "erro")
                return

            conn_unj, tunnel_unj = conectar_unj()

            if not conn_unj:
                self.log("Falha ao conectar ao banco (unj01sp).", "erro")
                return

            cur = conn.cursor()
            cur_unj = conn_unj.cursor()

            self.log("Iniciando processo")

            registros = self.obter_registros(cur)

            if not registros:
                self.log("Nenhum registro encontrado.", "erro")
                return

            self.total = len(registros)
            self.lbl_total.config(text=f"Encontrados: {self.total}")

            self.log(f"{self.total} registros encontrados")
            self.log("Registros que serão alterados:")

            for item in registros:
                self.log(
                    f"NUSEQ {item['nuseq']} | NUPROCESSOEXTERNO {item['nuprocessoexterno']}",
                    "normal"
                )

            self.executar_inserts(cur, conn, registros)
            self.iniciar_reprocessamento(cur, conn, registros)

            sucesso, pendentes = self.monitorar_registros(
                cur,
                cur_unj,
                conn,
                conn_unj,
                registros
            )

            self.log("=" * 60)
            self.log("PROCESSAMENTO FINALIZADO")
            self.log(f"Total: {self.total}")
            self.log(f"Sucesso: {len(sucesso)}")
            self.log(f"Pendentes: {len(pendentes)}")

            self.sql_text.delete("1.0", tk.END)
            self.gerar_sql_pendentes(pendentes)

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

            # Se o agendamento estiver ligado, agenda a próxima execução
            if self.agendamento_automatico_ativo:
                self.agendar_proxima_execucao()


root = tk.Tk()
app = BotReprocessamento(root)

root.mainloop()