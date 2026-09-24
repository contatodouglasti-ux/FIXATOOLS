"""Compatibilidade entre o sshtunnel legado e versões novas do Paramiko."""

import paramiko


# O sshtunnel 0.4.0 referencia DSSKey mesmo quando a autenticação é feita
# apenas por senha. O Paramiko 4+ removeu essa classe. O alias mantém o
# construtor do sshtunnel compatível; a aplicação usa autenticação por senha.
if not hasattr(paramiko, "DSSKey"):
    paramiko.DSSKey = paramiko.RSAKey
