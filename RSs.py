from connectionSP import conectar as conectar_sp
import win32com.client as win32
import time 
from datetime import datetime, timedelta


query_mpsp = """
SELECT
    '📊 Status operacional MPSP - ' ||
    to_char(now(), 'DD/MM/YYYY HH24:MI') ||
    E' \\n• Peticionamentos Sucesso: ' || p.petsucesso ||
    E' \\n• Peticionamentos Processando: ' || p.petprocessamento ||
    E' \\n• Peticionamentos Falha: ' || p.petfalha ||
    E' \\n• Intimações: ' || (i.intimaeproc + s.intimasaj) ||
    E' \\n• Pré-peticionamento: ' || pre.prepeticionamento ||
    E' \\n• Remessa pendente: ' || r.remessapendente
    AS mensagem
FROM
(
    SELECT
        COUNT(*) FILTER (WHERE flstatus = 2) AS petsucesso,
        COUNT(*) FILTER (WHERE flstatus IN (0,1,4,9,6,7)) AS petprocessamento,
        COUNT(*) FILTER (WHERE flstatus = 3) AS petfalha
    FROM saj.efmppeticionamento
    WHERE dtusuinclusao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
) p
CROSS JOIN
(
    SELECT COUNT(*) AS intimaeproc
    FROM saj.efmpavisosmni
    WHERE dtusuinclusao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
) i
CROSS JOIN
(
    SELECT COUNT(*) AS intimasaj
    FROM saj.efmptjlotecargait
    WHERE dtusuinclusao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
) s
CROSS JOIN
(
    SELECT COUNT(DISTINCT e.idcard) AS prepeticionamento
    FROM saj.efmppetloteitem e
    LEFT JOIN saj.efmppeticionamento e3 ON e.idcard = e3.idcard
    LEFT JOIN saj.efmppeticaocard e4 ON e.idcard = e4.idcard
    WHERE e.flstatus = 'F'
      AND e.dtalteracao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
      AND e3.cdpeticionamento IS NULL
      AND e4.cdpeticionamento IS NULL
) pre
CROSS JOIN
(
    SELECT COUNT(*) AS remessapendente
    FROM saj.efmpdistlote
    WHERE dtusuinclusao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
      AND flstatus = 'A'
      AND flstatusrobo = 'A'
) r;
"""


def consultar(conectar_func, query):
    conn = None
    cur = None

    try:
        conn = conectar_func()

        if conn is None:
            return None

        cur = conn.cursor()
        cur.execute(query)
        resultado = cur.fetchone()

        if resultado:
            return resultado[0]

        return None

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def enviar_email(msg_mpsp):

    outlook = win32.Dispatch('outlook.application')
    email = outlook.CreateItem(0)

    email.To = "douglas.s@softplan.com.br"
    email.Subject = "Reporte Operacional - MPSP"

    email.HTMLBody = f"""
    <h2>Status Operacional</h2>

    <h3>MPSP</h3>
    <p>{msg_mpsp.replace('\\n','<br>')}</p>
    """

    email.Send()

    print("✅ Email enviado com sucesso")


def executar():

    print("Executando consulta MPSP...")

    mpsp = consultar(conectar_sp, query_mpsp)

    if mpsp:
        enviar_email(mpsp)
    else:
        print("Nenhum dado retornado")


def esperar_proxima_hora_cheia():
    agora = datetime.now()
    proxima = (agora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    segundos = (proxima - agora).total_seconds()

    print(f"⏳ Aguardando até {proxima.strftime('%H:%M')}...")
    time.sleep(segundos)


while True:
    esperar_proxima_hora_cheia()
    executar()