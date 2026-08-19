import psycopg

DB_CONFIG = {
    "host": "prd-mpce-bd.cydamz8vzchm.sa-east-1.rds.amazonaws.com",
    "dbname": "sigce",
    "user": "douglas_s_escrita",
    "password": "KxxtaB8Rm0BwkSkV",
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