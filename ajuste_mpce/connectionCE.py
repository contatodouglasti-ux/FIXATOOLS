"""Conexão da base principal sigce do projeto Ajuste MPCE."""

import psycopg

from config_manager import obter_credenciais


def conectar():
    try:
        cred = obter_credenciais()
        campos = {
            "host": cred["sigce_host"],
            "dbname": cred["sigce_dbname"],
            "user": cred["sigce_user"],
            "password": cred["sigce_password"],
        }
        ausentes = [nome for nome, valor in campos.items() if not valor]
        if ausentes:
            raise ValueError(
                "Configure o banco sigce no config.ini: " + ", ".join(ausentes)
            )

        conn = psycopg.connect(
            host=cred["sigce_host"],
            dbname=cred["sigce_dbname"],
            user=cred["sigce_user"],
            password=cred["sigce_password"],
            port=cred["sigce_port"],
        )
        print("Conectado ao PostgreSQL sigce")
        return conn
    except Exception as exc:
        print(f"Erro ao conectar ao PostgreSQL sigce: {exc}")
        return None
