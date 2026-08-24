import argparse
import logging
import time
from datetime import datetime, date, timedelta
from decimal import Decimal

from supabase import create_client
from connectionCE import conectar as conectar_mpce
from connectionSP import conectar as conectar_mpsp


# ====
# LOG
# ====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# ====
# SUPABASE
# ====
SUPABASE_URL = "https://cbgndmgeoswjetfodqci.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_u-whGHIpKN3LbIdt93tQiA_RyHK8n_o"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_public = supabase.schema("public")


# ====
# CONSULTAS
# ====

SQL_PETICIONAMENTO_HORA = """
SELECT
    l.cdlocal,
    l.delocal AS nomelocal,
    date_trunc('hour', p.dtusuinclusao) AS hora_inicio,
    date_trunc('hour', p.dtusuinclusao) + interval '1 hour' AS hora_fim,
    SUM(CASE
            WHEN p.flstatus = '2' AND p.flsaj6 = 'S'
            THEN 1 ELSE 0
        END) AS protocolado_saj6,
    SUM(CASE
            WHEN p.flstatus = '2' AND p.flsaj6 <> 'S'
            THEN 1 ELSE 0
        END) AS protocolado_saj5,
    SUM(CASE
            WHEN p.flstatus = '3' AND p.flsaj6 = 'S'
            THEN 1 ELSE 0
        END) AS falha_saj6,
    SUM(CASE
            WHEN p.flstatus = '3' AND p.flsaj6 <> 'S'
            THEN 1 ELSE 0
        END) AS falha_saj5
FROM saj.efmppeticionamento p
INNER JOIN saj.efmpprocesso pr
    ON pr.cdprocesso = p.cdprocesso
INNER JOIN saj.esajlocal l
    ON l.cdlocal = pr.cdlocal
WHERE p.dtusuinclusao >= %(data_inicio)s
  AND p.dtusuinclusao < %(data_fim)s
  AND l.flforauso = 'N'
  AND l.flsaj6habilitado = 'S'
GROUP BY
    l.cdlocal,
    l.delocal,
    date_trunc('hour', p.dtusuinclusao)
ORDER BY
    l.cdlocal,
    hora_inicio;
"""

SQL_INTIMACAO_HORA = """
SELECT
    i.cdlocaldestino::text AS cdlocal,
    l.delocal AS nomelocal,
    date_trunc('hour', i.dtusuinclusao) AS hora_inicio,
    date_trunc('hour', i.dtusuinclusao) + interval '1 hour' AS hora_fim,
    COUNT(*) AS intimacao
FROM saj.efmpintimacao i
INNER JOIN saj.esajlocal l
    ON l.cdlocal = i.cdlocaldestino
WHERE i.dtusuinclusao >= %(data_inicio)s
  AND i.dtusuinclusao < %(data_fim)s
  AND l.flforauso = 'N'
  AND l.flsaj6habilitado = 'S'
GROUP BY
    i.cdlocaldestino,
    l.delocal,
    date_trunc('hour', i.dtusuinclusao)
ORDER BY
    i.cdlocaldestino,
    hora_inicio;
"""

SQL_LOTEITEM_DIA = """
SELECT
    date_trunc('day', e.dtalteracao)::date AS dia_referencia,
    e.flstatus,
    COALESCE(NULLIF(TRIM(e.demotivofalha), ''), 'SEM_MOTIVO') AS demotivofalha,
    COUNT(*) AS total
FROM saj.efmppetloteitem e
WHERE e.flstatus <> 'C'
  AND e.dtalteracao >= %(data_inicio)s
  AND e.dtalteracao < %(data_fim)s
GROUP BY
    date_trunc('day', e.dtalteracao)::date,
    e.flstatus,
    COALESCE(NULLIF(TRIM(e.demotivofalha), ''), 'SEM_MOTIVO')
ORDER BY
    dia_referencia,
    demotivofalha,
    e.flstatus;
"""

# =========================
# CONSULTAS MPSP
# =========================
# O MPSP usa a mesma base sigsp do Erro Foro/Reset em Lote. As consultas
# abaixo não fazem JOIN com esajlocal: cada janela retorna um total geral.
SQL_MPSP_PETICIONAMENTO_HORA = """
SELECT
    date_trunc('hour', p.dtusuinclusao) AS hora_inicio,
    date_trunc('hour', p.dtusuinclusao) + interval '1 hour' AS hora_fim,
    SUM(CASE
        WHEN p.flstatus = '2' AND p.flsaj6 = 'S'
        THEN 1 ELSE 0
    END) AS protocolado_saj6,
    SUM(CASE
        WHEN p.flstatus = '2' AND COALESCE(p.flsaj6, 'N') <> 'S'
        THEN 1 ELSE 0
    END) AS protocolado_saj5,
    SUM(CASE
        WHEN p.flstatus = '3' AND p.flsaj6 = 'S'
        THEN 1 ELSE 0
    END) AS falha_saj6,
    SUM(CASE
        WHEN p.flstatus = '3' AND COALESCE(p.flsaj6, 'N') <> 'S'
        THEN 1 ELSE 0
    END) AS falha_saj5
FROM saj.efmppeticionamento p
WHERE p.dtusuinclusao >= %(data_inicio)s
  AND p.dtusuinclusao < %(data_fim)s
GROUP BY date_trunc('hour', p.dtusuinclusao)
ORDER BY hora_inicio;
"""

SQL_MPSP_INTIMACAO_HORA = """
SELECT
    fontes.hora_inicio,
    fontes.hora_inicio + interval '1 hour' AS hora_fim,
    SUM(fontes.intimacao)::bigint AS intimacao
FROM (
    SELECT
        date_trunc('hour', a.dtusuinclusao) AS hora_inicio,
        COUNT(*) AS intimacao
    FROM saj.efmpavisosmni a
    WHERE a.dtusuinclusao >= %(data_inicio)s
      AND a.dtusuinclusao < %(data_fim)s
    GROUP BY date_trunc('hour', a.dtusuinclusao)

    UNION ALL

    SELECT
        date_trunc('hour', i.dtusuinclusao) AS hora_inicio,
        COUNT(*) AS intimacao
    FROM saj.efmptjlotecargait i
    WHERE i.dtusuinclusao >= %(data_inicio)s
      AND i.dtusuinclusao < %(data_fim)s
    GROUP BY date_trunc('hour', i.dtusuinclusao)
) fontes
GROUP BY fontes.hora_inicio
ORDER BY fontes.hora_inicio;
"""


# ====
# UTILITÁRIOS
# ====

def normalizar_valor(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        # SUM/COUNT do PostgreSQL podem voltar como Decimal. Contagens
        # inteiras precisam ser serializadas como int para o tipo bigint do
        # Supabase; enviar 8256.0 causa erro de conversão no PostgREST.
        if valor == valor.to_integral_value():
            return int(valor)
        return float(valor)
    return valor


def normalizar_registro(registro):
    return {k: normalizar_valor(v) for k, v in registro.items()}


def fetch_dicts(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        colunas = [desc[0] for desc in cur.description]
        linhas = cur.fetchall()
        registros = [dict(zip(colunas, linha)) for linha in linhas]
        return [normalizar_registro(r) for r in registros]


def salvar_no_supabase(tabela, registros, on_conflict):
    if not registros:
        print(f"Nenhum registro para salvar em {tabela}")
        return {"ok": True, "qtd": 0}

    supabase_public.table(tabela).upsert(
        registros,
        on_conflict=on_conflict
    ).execute()

    print(f"Salvos {len(registros)} registros em {tabela}")
    return {"ok": True, "qtd": len(registros)}


def inicio_fim_ultima_hora():
    agora = datetime.now()
    fim = agora.replace(minute=0, second=0, microsecond=0)
    inicio = fim - timedelta(hours=1)
    return inicio, fim


def dormir_ate_proxima_hora():
    agora = datetime.now()
    proxima_hora = agora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    segundos = (proxima_hora - agora).total_seconds()
    if segundos > 0:
        print(f"Aguardando {int(segundos)} segundos até a próxima execução...")
        time.sleep(segundos)


# ====
# PROCESSAMENTO
# ====

def _consultar_e_salvar(
    conn,
    data_inicio,
    data_fim,
    nome,
    sql,
    tabela,
    on_conflict,
):
    """Executa uma consulta, publica os dados e devolve o resumo da etapa."""
    try:
        print(f"Consultando {nome}...")
        registros = fetch_dicts(conn, sql, {
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        })
        salvar_no_supabase(tabela, registros, on_conflict=on_conflict)
        return (nome, "ok", len(registros), None)
    except Exception as e:
        logging.exception("Erro em %s", nome)
        return (nome, "erro", 0, str(e))


def _processar_fonte(
    conn,
    data_inicio,
    data_fim,
    prefixo,
    sql_peticionamento,
    sql_intimacao,
    tabela_peticionamento,
    tabela_intimacao,
    tabela_loteitem,
    conflito_peticionamento,
    conflito_intimacao,
):
    """Processa uma fonte sem compartilhar conexão ou resultados com a outra."""
    resultados = []

    resultados.append(_consultar_e_salvar(
        conn,
        data_inicio,
        data_fim,
        f"{prefixo}_peticionamento_hora",
        sql_peticionamento,
        tabela_peticionamento,
        conflito_peticionamento,
    ))
    resultados.append(_consultar_e_salvar(
        conn,
        data_inicio,
        data_fim,
        f"{prefixo}_intimacao_hora",
        sql_intimacao,
        tabela_intimacao,
        conflito_intimacao,
    ))
    resultados.append(_consultar_e_salvar(
        conn,
        data_inicio,
        data_fim,
        f"{prefixo}_loteitem_dia",
        SQL_LOTEITEM_DIA,
        tabela_loteitem,
        "dia_referencia,flstatus,demotivofalha",
    ))

    return resultados


def _resultado_falha_conexao(nome, erro):
    return (nome, "erro", 0, str(erro))


def processar(data_inicio, data_fim):
    """Coleta MPCE por lotação e MPSP no total geral."""
    resultados = []
    print(f"Janela de consulta: {data_inicio} -> {data_fim}")

    # MPCE: conexão e tabelas atuais, mantendo a agregação por lotação.
    conn_mpce = conectar_mpce()
    if conn_mpce is None:
        resultados.append(_resultado_falha_conexao(
            "mpce_conexao",
            "Não foi possível conectar ao banco do MPCE.",
        ))
    else:
        try:
            resultados.extend(_processar_fonte(
                conn_mpce,
                data_inicio,
                data_fim,
                "mpce",
                SQL_PETICIONAMENTO_HORA,
                SQL_INTIMACAO_HORA,
                "bi_peticionamento_hora",
                "bi_intimacao_hora",
                "bi_peticionamento_mensal_motivo",
                "cdlocal,hora_inicio",
                "cdlocal,hora_inicio",
            ))
        finally:
            conn_mpce.close()

    # MPSP: conexão sigsp usada pelo Erro Foro/Reset, sem agrupamento por
    # lotação. As tabelas possuem sufixo próprio para não misturar os dados.
    conn_mpsp = None
    tunnel_mpsp = None
    try:
        conn_mpsp, tunnel_mpsp = conectar_mpsp()
        if conn_mpsp is None:
            resultados.append(_resultado_falha_conexao(
                "mpsp_conexao",
                "Não foi possível conectar ao banco sigsp do MPSP.",
            ))
        else:
            resultados.extend(_processar_fonte(
                conn_mpsp,
                data_inicio,
                data_fim,
                "mpsp_total",
                SQL_MPSP_PETICIONAMENTO_HORA,
                SQL_MPSP_INTIMACAO_HORA,
                "bi_peticionamento_hora_mpsp",
                "bi_intimacao_hora_mpsp",
                "bi_peticionamento_mensal_motivo_mpsp",
                "hora_inicio",
                "hora_inicio",
            ))
    finally:
        if conn_mpsp is not None:
            conn_mpsp.close()
        if tunnel_mpsp is not None:
            tunnel_mpsp.stop()

    print("\nResumo da execução:")
    for nome, status, qtd, erro in resultados:
        if status == "ok":
            print(f" - {nome}: OK ({qtd} registros)")
        else:
            print(f" - {nome}: ERRO -> {erro}")

    return resultados


def executar_uma_vez_automatico():
    data_inicio, data_fim = inicio_fim_ultima_hora()
    processar(data_inicio, data_fim)


def executar_em_loop():
    while True:
        data_inicio, data_fim = inicio_fim_ultima_hora()
        processar(data_inicio, data_fim)
        dormir_ate_proxima_hora()


# ====
# MAIN
# ====

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--fim", help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--auto", action="store_true", help="Executa a última hora fechada")
    parser.add_argument("--loop", action="store_true", help="Executa automaticamente a cada 1h")
    args = parser.parse_args()

    if args.inicio and args.fim:
        data_inicio = datetime.strptime(args.inicio, "%Y-%m-%d %H:%M:%S")
        data_fim = datetime.strptime(args.fim, "%Y-%m-%d %H:%M:%S")
        processar(data_inicio, data_fim)

    elif args.loop:
        print("Modo automático em loop ativado.")
        executar_em_loop()

    else:
        if args.auto or (not args.inicio and not args.fim):
            print("Modo automático de última hora fechada ativado.")
            executar_uma_vez_automatico()
        else:
            print("Você precisa informar --inicio e --fim juntos, ou usar --auto, ou --loop.")
