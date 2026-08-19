import argparse
import logging
import time
from datetime import datetime, date, timedelta
from decimal import Decimal

from supabase import create_client
from connectionCE import conectar


# =========================
# LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# =========================
# SUPABASE
# =========================
SUPABASE_URL = "https://cbgndmgeoswjetfodqci.supabase.co"
SUPABASE_ANON_KEY = "COLE_SUA_ANON_KEY_AQUI"

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_public = supabase.schema("public")


# =========================
# CONSULTAS
# =========================

SQL_PETICIONAMENTO_HORA = """
SELECT
    l.cdlocal::text AS cdlocal,
    l.delocal AS nomelocal,
    date_trunc('hour', p.dtusuinclusao) AS hora_inicio,
    date_trunc('hour', p.dtusuinclusao) + interval '1 hour' AS hora_fim,
    SUM(CASE WHEN p.flstatus = '2' THEN 1 ELSE 0 END) AS protocolado,
    SUM(CASE WHEN p.flstatus = '3' AND p.flsaj6 = 'S' THEN 1 ELSE 0 END) AS falha_saj6,
    SUM(CASE WHEN p.flstatus = '3' AND COALESCE(p.flsaj6, 'N') <> 'S' THEN 1 ELSE 0 END) AS falha_saj5,
    SUM(CASE WHEN p.flstatus IN ('0','7','9','11') THEN 1 ELSE 0 END) AS pendente,
    COUNT(*) AS total
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
# UTILITÁRIOS
# =========================

def normalizar_valor(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
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


# =========================
# PROCESSAMENTO
# =========================

def processar(data_inicio, data_fim):
    conn_local = conectar()

    if conn_local is None:
        raise RuntimeError("Não foi possível conectar ao banco local.")

    resultados = []

    try:
        print(f"Janela de consulta: {data_inicio} -> {data_fim}")

        # 1) Peticionamento por hora
        try:
            print("Consultando peticionamento por hora...")
            pet_hora = fetch_dicts(conn_local, SQL_PETICIONAMENTO_HORA, {
                "data_inicio": data_inicio,
                "data_fim": data_fim
            })
            salvar_no_supabase(
                "bi_peticionamento_hora",
                pet_hora,
                on_conflict="cdlocal,hora_inicio"
            )
            resultados.append(("peticionamento_hora", "ok", len(pet_hora), None))
        except Exception as e:
            logging.exception("Erro no peticionamento por hora")
            resultados.append(("peticionamento_hora", "erro", 0, str(e)))

        # 2) Intimação por hora
        try:
            print("Consultando intimação por hora...")
            intimacoes = fetch_dicts(conn_local, SQL_INTIMACAO_HORA, {
                "data_inicio": data_inicio,
                "data_fim": data_fim
            })
            salvar_no_supabase(
                "bi_intimacao_hora",
                intimacoes,
                on_conflict="cdlocal,hora_inicio"
            )
            resultados.append(("intimacao_hora", "ok", len(intimacoes), None))
        except Exception as e:
            logging.exception("Erro na intimação por hora")
            resultados.append(("intimacao_hora", "erro", 0, str(e)))

        # 3) Loteitem por dia
        try:
            print("Consultando efmppetloteitem por dia...")
            loteitem_dia = fetch_dicts(conn_local, SQL_LOTEITEM_DIA, {
                "data_inicio": data_inicio,
                "data_fim": data_fim
            })
            salvar_no_supabase(
                "bi_peticionamento_dia_status_motivo",
                loteitem_dia,
                on_conflict="dia_referencia,flstatus,demotivofalha"
            )
            resultados.append(("loteitem_dia", "ok", len(loteitem_dia), None))
        except Exception as e:
            logging.exception("Erro no loteitem por dia")
            resultados.append(("loteitem_dia", "erro", 0, str(e)))

    finally:
        conn_local.close()

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


# =========================
# MAIN
# =========================

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