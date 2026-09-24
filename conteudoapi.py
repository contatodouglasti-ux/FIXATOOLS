import os
import requests

# Pasta onde os arquivos serão salvos
# ==========================================
PASTA_DESTINO = r"C:\Users\douglas.s\Downloads\arqu"
os.makedirs(PASTA_DESTINO, exist_ok=True)
# Lista de arquivos (ID, versão)
# ==========================================
ARQUIVOS = [
("0577d757-a023-45d2-8261-51193b0fefaa",1),
("0577d757-a023-45d2-8261-51193b0fefaa",2),
("0577d757-a023-45d2-8261-51193b0fefaa",3),
("0577d757-a023-45d2-8261-51193b0fefaa",4),
("0577d757-a023-45d2-8261-51193b0fefaa",5),

]
HEADERS = {
    "tenant": "Default",
    "lotacao": "2085",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJKdnc1VExEaVQ3RUhhUGt5eVJEY215NDhVMkNHVmxDbWRtemtjV2tXdzlFIn0.eyJleHAiOjE3OTAxOTQzMzYsImlhdCI6MTc5MDE5MDczNiwiYXV0aF90aW1lIjoxNzkwMTc5Mzk2LCJqdGkiOiJjZDlmOTc2Yy1hMjk2LTQzMjUtYTc2OS0xMWEyYWRiN2YzMTEiLCJpc3MiOiJodHRwczovL2tleWNsb2FrLXNhai5zYWptcC5tcHNwLm1wLmJyL2F1dGgvcmVhbG1zL1NBSi1NUCIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiJmOjc4MWVjYjY1LTc1ZWQtNGQ5MS1iZDlhLTg2YmQwM2IzZjQ4YzowMTg1ODkzMzI1MCIsInR5cCI6IkJlYXJlciIsImF6cCI6InNhajYtbXAiLCJub25jZSI6ImVhMGUwYmU0LTNkMGItNGQ2Ni05ODcxLTU2YmM1NWYwMzI5NSIsInNlc3Npb25fc3RhdGUiOiI5MDIyNTY2YS1jMzNhLTQ5M2MtYjkyNC04ODE2YmUzZGYyMWIiLCJhbGxvd2VkLW9yaWdpbnMiOlsiKiJdLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdfSwicmVzb3VyY2VfYWNjZXNzIjp7ImFjY291bnQiOnsicm9sZXMiOlsibWFuYWdlLWFjY291bnQiLCJtYW5hZ2UtYWNjb3VudC1saW5rcyIsInZpZXctcHJvZmlsZSJdfX0sInNjb3BlIjoib3BlbmlkIGVtYWlsIHByb2ZpbGUiLCJzaWQiOiI5MDIyNTY2YS1jMzNhLTQ5M2MtYjkyNC04ODE2YmUzZGYyMWIiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInVzZXJfcmVhbG1fcm9sZXMiOlsib2ZmbGluZV9hY2Nlc3MiLCJ1bWFfYXV0aG9yaXphdGlvbiJdLCJuYW1lIjoiRG91Z2xhcyBkYSBTaWx2YSBDb3N0YSIsInByZWZlcnJlZF91c2VybmFtZSI6IkRPVUdMQVMuQ09TVEEiLCJnaXZlbl9uYW1lIjoiRG91Z2xhcyIsIm5ld1ZlcnNpb25Vc2VyIjoiRkFMU0UiLCJmYW1pbHlfbmFtZSI6ImRhIFNpbHZhIENvc3RhIiwicHJvdmlkZWRfdXNlcm5hbWUiOiIwMTg1ODkzMzI1MCIsImVtYWlsIjoiZG91Z2xhcy5zQHNvZnRwbGFuLmNvbS5iciJ9.GhRKArB1etk7QeAkEz8pJam0qlE_F0caJGrMWvFDfVKHEnAH4zeN9TLWkX2vIpOQ6E2d2p_kI_B4PJbmKN4F62Fo2Y9farxOGzEKpvh1U2H1VuLuCvP1F7faJy_qMPPJ_7WrL2PCN09Ge02JCcgk9jNcw2cUgDkJCJOp7WzMLScfhi7GxHwP6HFdsBTEXTvx19gXeJxxlPuVl1PqryDdpkTp57U4F1BEu6YRumu1PDcCjzjOm9vGXTr2kmEy8mA7ZoohxabteFOHF_I6uxLmKk4QUdm0b4kclyJAFo4g-ZC45dSeG4-OUgK9D2kumulrI_loiL6JMUUfVhnGg9mQig"
}
# Download dos arquivos
# ==========================================
for arquivo_id, versao in ARQUIVOS:
    url = (
        f"https://saj.sajmp.mpsp.mp.br/mp-conteudo-api/api/v1/contents"
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