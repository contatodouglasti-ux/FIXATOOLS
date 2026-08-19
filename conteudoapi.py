import os
import requests

# Pasta onde os arquivos serão salvos
# ==========================================
PASTA_DESTINO = r"C:\Users\douglas.s\Downloads\testePY"
os.makedirs(PASTA_DESTINO, exist_ok=True)
# Lista de arquivos (ID, versão)
# ==========================================
ARQUIVOS = [
("003cc09c-924d-43aa-82a6-b3c9f3c8da27",1),
]
HEADERS = {
    "tenant": "Default",
    "lotacao": "null",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJGTGkwX2xQbjBQdDB5ODQ1bk9tY1lNSld4R0w3UUlfY1ZFRUJ5NGlZVnc4In0.eyJleHAiOjE3ODI4Nzk1NjMsImlhdCI6MTc4Mjg0MzU3NywiYXV0aF90aW1lIjoxNzgyODQzNTYzLCJqdGkiOiJmNDdjM2VkNy1iMmVkLTQ3YTgtYjBkOS0xZWVmMjQ5ZTc5NWEiLCJpc3MiOiJodHRwczovL2tleWNsb2FrLXNhai5tcHJzLm1wLmJyL2F1dGgvcmVhbG1zL1NBSi1NUCIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiJmOmI0ZTVmMDlkLTRkMGYtNDE5NC1iNWQyLTgxZTMwMmJlN2ZkMTpTT0ZUUExBTkRPVUdMQVMiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJzYWotbXAiLCJub25jZSI6IjUyMjJjMGMwLWIzODgtNGUyNy04NGRiLWE0YTgwMjI0OGZhOCIsInNlc3Npb25fc3RhdGUiOiI2MDhmNmViNi1kMTQ1LTQ5MTQtYWRkZS0xODhhMjcxNTNkYzkiLCJhbGxvd2VkLW9yaWdpbnMiOlsiKiJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdfSwicmVzb3VyY2VfYWNjZXNzIjp7ImFjY291bnQiOnsicm9sZXMiOlsibWFuYWdlLWFjY291bnQiLCJtYW5hZ2UtYWNjb3VudC1saW5rcyIsInZpZXctcHJvZmlsZSJdfX0sInNjb3BlIjoib3BlbmlkIGVtYWlsIHByb2ZpbGUiLCJzaWQiOiI2MDhmNmViNi1kMTQ1LTQ5MTQtYWRkZS0xODhhMjcxNTNkYzkiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInVzZXJfcmVhbG1fcm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdLCJuYW1lIjoiRG91Z2xhcyBkYSBTaWx2YSBDb3N0YSAoU29mdHBsYW4pIiwicHJlZmVycmVkX3VzZXJuYW1lIjoiU09GVFBMQU5ET1VHTEFTIiwiZ2l2ZW5fbmFtZSI6IkRvdWdsYXMiLCJuZXdWZXJzaW9uVXNlciI6IkZBTFNFIiwiZmFtaWx5X25hbWUiOiJkYSBTaWx2YSBDb3N0YSAoU29mdHBsYW4pIiwicHJvdmlkZWRfdXNlcm5hbWUiOiJTT0ZUUExBTkRPVUdMQVMiLCJlbWFpbCI6ImRvdWdsYXMuc0Bzb2Z0cGxhbi5jb20uYnIifQ.LpH8zc-gFd2tSp0AxCRzWEATOEnE0Z-RCiSKN8vlCML_ZPrZkrLY-JWk4f6ZG_Ah9J2xVpJtn2nJdC0XMCo4mEKrLg8Az-JHcFU6tTBpXq024W3hhXp8k7ALgItYVoY5LqQE9WGU64ZlWU96lkt6FkfdsrOusZiUS1aviDX4-kX-wNWedYuLcHtdR-BKCySKKFpB7QOSx8liA4qJiPl5B9hWtBjvWVaqoD6r2L7tZ1GCTPxlNh-BTIapiheXtGEajP3wlvQzG37pLVtjslomP_CTGDK1UsaTM4Nj6FiWSvFJAdKQf_UIE2nhOiyFKouMo4fKw3k9DkBzZc0q38WVog"
}
# Download dos arquivos
# ==========================================
for arquivo_id, versao in ARQUIVOS:
    url = (
        f"https://saj.mprs.mp.br/mp-conteudo-api/api/v1/contents/"
        f"{arquivo_id}/?version={versao}"
    )
    print(f"Baixando {arquivo_id} (versão {versao})...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            caminho_arquivo = os.path.join(
                PASTA_DESTINO,
                f"{arquivo_id}_v{versao}.html"
            )
            with open(caminho_arquivo, "wb") as f:
                f.write(response.content)
            print(f"✅ Salvo em: {caminho_arquivo}")

        else:
            print(f"❌ Erro {response.status_code} ao baixar {arquivo_id}")
            print(response.text)
    except Exception as e:
        print(f"❌ Erro ao baixar {arquivo_id}: {e}")

print("\nProcesso concluído!")