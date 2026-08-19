import psycopg
from sshtunnel import SSHTunnelForwarder
import traceback
from config_manager import obter_credenciais


def conectar():
    try:
        cred = obter_credenciais()

        tunnel = SSHTunnelForwarder(
            (cred["ssh_host"], cred["ssh_port"]),
            ssh_username=cred["ssh_user"],
            ssh_password=cred["ssh_password"],
            remote_bind_address=(cred["remote_host"], cred["remote_port"])
        )

        tunnel.start()

        conn = psycopg.connect(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            dbname=cred["db_sp"],
            user=cred["db_user"],
            password=cred["db_password"]
        )

        print("✅ Conectado ao PostgreSQL via SSH")

        return conn, tunnel

    except Exception as e:
        traceback.print_exc()
        return None, None


if __name__ == "__main__":
    conexao, tunnel = conectar()

    if conexao:
        try:
            with conexao.cursor() as cur:
                cur.execute("SELECT version();")
                print(cur.fetchone()[0])

        finally:
            conexao.close()
            tunnel.stop()
            print("✅ Conexão e túnel encerrados")