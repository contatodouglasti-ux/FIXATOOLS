import psycopg

DB_CONFIG = {
    "host": "prod-bd-mprs.cj4mqn7dlzo1.sa-east-1.rds.amazonaws.com",
    "dbname": "sigrs",
    "user": "douglas_s_leitura",
    "password": "uyR2YelEULyWXws6",
    "port": 5432
}

def conectar():
    try:
        conn = psycopg.connect(**DB_CONFIG)
        print("✅ Conectado ao PostgreSQL")
        return conn
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

if __name__ == "__main__":
    conexao = conectar()

    if conexao:
        conexao.close()
        print("Conexão encerrada.")