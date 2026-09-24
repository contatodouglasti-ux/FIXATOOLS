"""Conexão direta do banco sajptf UNJ01CE do cliente MPCE."""

import psycopg

from config_manager import obter_credenciais


def conectar():
    try:
        cred = obter_credenciais()
        campos_obrigatorios = {
            "host": cred["mpce_host"],
            "dbname": cred["mpce_db_unj"],
            "user": cred["mpce_user"],
            "password": cred["mpce_password"],
        }
        ausentes = [nome for nome, valor in campos_obrigatorios.items() if not valor]
        if ausentes:
            raise ValueError(
                "Configure os campos do MPCE UNJ01CE antes de conectar: "
                + ", ".join(ausentes)
            )

        conn = psycopg.connect(
            host=cred["mpce_host"],
            dbname=cred["mpce_db_unj"],
            user=cred["mpce_user"],
            password=cred["mpce_password"],
            port=cred["mpce_port"],
        )
        print("Conectado ao PostgreSQL MPCE UNJ01CE")
        return conn
    except Exception as exc:
        print(f"Erro ao conectar ao PostgreSQL MPCE UNJ01CE: {exc}")
        return None

