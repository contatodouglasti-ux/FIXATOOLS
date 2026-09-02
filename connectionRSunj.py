"""Conexão direta do banco sajptf do cliente MPRS."""

import psycopg

from config_manager import obter_credenciais


def conectar():
    try:
        cred = obter_credenciais()
        campos_obrigatorios = {
            "host": cred["mprs_host"],
            "dbname": cred["mprs_db_unj"],
            "user": cred["mprs_user"],
            "password": cred["mprs_password"],
        }
        ausentes = [nome for nome, valor in campos_obrigatorios.items() if not valor]
        if ausentes:
            raise ValueError(
                "Configure os campos do MPRS UNJ antes de conectar: "
                + ", ".join(ausentes)
            )

        conn = psycopg.connect(
            host=cred["mprs_host"],
            dbname=cred["mprs_db_unj"],
            user=cred["mprs_user"],
            password=cred["mprs_password"],
            port=cred["mprs_port"],
        )
        print("✅ Conectado ao PostgreSQL MPRS UNJ")
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar ao PostgreSQL MPRS UNJ: {e}")
        return None


if __name__ == "__main__":
    conexao = conectar()
    if conexao:
        conexao.close()
        print("Conexão MPRS UNJ encerrada.")
