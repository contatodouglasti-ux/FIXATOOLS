from flask import Flask, render_template_string, request, jsonify
from connectionRS import conectar as conectar_rs
from connectionSP import conectar as conectar_sp
from datetime import datetime

app = Flask(__name__)

# ================== SUAS QUERIES ==================
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

# ==================================================

historico = []


def consultar(conectar_func, query):
    try:
        conn = conectar_func()

        if conn is None:
            return "Erro na conexão"

        cur = conn.cursor()
        cur.execute(query)
        resultado = cur.fetchone()

        cur.close()
        conn.close()

        if resultado:
            return resultado[0]

        return "Sem dados"

    except Exception as e:
        return f"Erro: {str(e)}"


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Status Operacional</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial;
            background: #f4f6f8;
            margin: 0;
            padding: 20px;
        }

        h1 {
            text-align: center;
        }

        .container {
            max-width: 900px;
            margin: auto;
        }

        button {
            padding: 12px 25px;
            font-size: 16px;
            cursor: pointer;
            border-radius: 10px;
            border: none;
            background: #007bff;
            color: white;
        }

        .cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            white-space: pre-line;
        }

        .ok { border-left: 6px solid green; }
        .warn { border-left: 6px solid orange; }
        .error { border-left: 6px solid red; }

        .historico {
            margin-top: 30px;
        }

        .item {
            background: white;
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 10px;
            font-size: 14px;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>📊 Status Operacional</h1>

    <div style="text-align:center;">
        <button onclick="consultar()">Consultar Agora</button>
    </div>

    <div class="cards" id="resultado"></div>

    <div class="historico">
        <h3>🕘 Histórico</h3>
        <div id="historico"></div>
    </div>
</div>

<script>
function getStatusClass(text) {
    if (!text) return 'ok';

    if (text.includes('Falha') && !text.includes(': 0')) return 'error';
    if (text.includes('Processando')) return 'warn';
    return 'ok';
}

function consultar() {
    fetch('/consultar')
    .then(res => res.json())
    .then(data => {

        document.getElementById('resultado').innerHTML = `
            <div class="card ${getStatusClass(data.mprs)}">
                <h3>MPRS</h3>
                ${data.mprs}
            </div>
            <div class="card ${getStatusClass(data.mpsp)}">
                <h3>MPSP</h3>
                ${data.mpsp}
            </div>
        `;

        let hist = document.getElementById('historico');

        hist.innerHTML = data.historico
            .map(h => `<div class="item">${h}</div>`)
            .join('');
    });
}

// auto refresh a cada 60s
setInterval(consultar, 60000);

// já carrega ao abrir a página
consultar();
</script>

</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/consultar')
def consultar_api():
    mprs = consultar(conectar_rs, query_mprs)
    mpsp = consultar(conectar_sp, query_mpsp)

    timestamp = datetime.now().strftime('%d/%m %H:%M:%S')
    registro = f"[{timestamp}] Consulta realizada"

    historico.insert(0, registro)

    return jsonify({
        "mprs": mprs.replace("\\n", "<br>") if mprs else "Sem dados",
        "mpsp": mpsp.replace("\\n", "<br>") if mpsp else "Sem dados",
        "historico": historico[:10]
    })


if __name__ == '__main__':
    app.run(debug=True)