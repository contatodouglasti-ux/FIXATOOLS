from connectionRS import conectar as conectar_rs
from connectionSP import conectar as conectar_sp
import win32com.client as win32
import time 
from datetime import datetime, timedelta



query_mprs = """
SELECT
    '📊 Status operacional MPRS - ' ||
    to_char(now(), 'DD/MM/YYYY HH24:MI') ||
    E' \\n• Peticionamentos Sucesso: ' || p.petsucesso ||
    E' \\n• Peticionamentos Processando: ' || p.petprocessamento ||
    E' \\n• Peticionamentos Falha: ' || p.petfalha ||
    E' \\n• Intimações: ' || (i.intimaeproc + i.intimaseeu) ||
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
    SELECT
        COUNT(*) FILTER (WHERE tpsistema = 'EPROC') AS intimaeproc,
        COUNT(*) FILTER (WHERE tpsistema = 'SEEU')  AS intimaseeu
    FROM saj.efmpavisosmni
    WHERE dtusuinclusao >= DATE_TRUNC('day', CURRENT_TIMESTAMP)
) i
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

    conn = conectar_func()

    if conn is None:
        return None

    cur = conn.cursor()
    cur.execute(query)

    resultado = cur.fetchone()

    cur.close()
    conn.close()

    if resultado:
        return resultado[0]

    return None


def enviar_email(msg_mprs, msg_mpsp):

    outlook = win32.Dispatch('outlook.application')
    email = outlook.CreateItem(0)

    email.To = "douglas.s@softplan.com.br"
    email.Subject = "Reporte Operacional"

    email.HTMLBody = f"""
    <h2>Status Operacional</h2>

    <h3>MPRS</h3>
    <p>{msg_mprs.replace('\\n','<br>')}</p>

    <br>

    <h3>MPSP</h3>
    <p>{msg_mpsp.replace('\\n','<br>')}</p>
      <br>
        <br>
          <br>
            <br>
    """

    email.Send()

    print("✅ Email enviado com sucesso")


def executar():

    print("Executando consultas...")

    mprs = consultar(conectar_rs, query_mprs)
    mpsp = consultar(conectar_sp, query_mpsp)

    if mprs or mpsp:
        enviar_email(mprs, mpsp)
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