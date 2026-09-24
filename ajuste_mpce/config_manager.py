"""Configuração exclusiva do projeto Ajuste MPCE."""

import configparser
import os
import sys


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(get_base_dir(), "config.ini")

DEFAULTS = {
    "sigce": {
        "host": "",
        "port": "5432",
        "dbname": "sigce",
        "user": "",
        "password": "",
    },
    "mpce": {
        "host": "",
        "port": "5432",
        "db_unj": "unj01ce",
        "user": "",
        "password": "",
    }
}


def _criar_config_padrao():
    config = configparser.ConfigParser()
    for secao, valores in DEFAULTS.items():
        config[secao] = valores
    with open(CONFIG_PATH, "w", encoding="utf-8") as arquivo:
        config.write(arquivo)
    return config


def carregar_config():
    # Mantém compatibilidade com configurações antigas que tenham repetido
    # alguma opção. O último valor informado será usado.
    config = configparser.ConfigParser(strict=False)
    if not os.path.exists(CONFIG_PATH):
        return _criar_config_padrao()

    config.read(CONFIG_PATH, encoding="utf-8")
    alterado = False
    for secao, valores in DEFAULTS.items():
        if secao not in config:
            config[secao] = {}
            alterado = True
        for chave, valor_padrao in valores.items():
            if chave not in config[secao]:
                config[secao][chave] = valor_padrao
                alterado = True

    if alterado:
        with open(CONFIG_PATH, "w", encoding="utf-8") as arquivo:
            config.write(arquivo)
    return config


def salvar_mpce_unj(host, port, db_unj, user, password):
    config = carregar_config()
    config["mpce"]["host"] = str(host or "").strip()
    config["mpce"]["port"] = str(port or "5432").strip()
    config["mpce"]["db_unj"] = str(db_unj or "unj01ce").strip()
    config["mpce"]["user"] = str(user or "").strip()
    config["mpce"]["password"] = str(password or "")
    with open(CONFIG_PATH, "w", encoding="utf-8") as arquivo:
        config.write(arquivo)


def obter_credenciais():
    config = carregar_config()
    return {
        "sigce_host": config["sigce"]["host"],
        "sigce_port": config.getint("sigce", "port"),
        "sigce_dbname": config["sigce"]["dbname"],
        "sigce_user": config["sigce"]["user"],
        "sigce_password": config["sigce"]["password"],
        "mpce_host": config["mpce"]["host"],
        "mpce_port": config.getint("mpce", "port"),
        "mpce_db_unj": config["mpce"]["db_unj"],
        "mpce_user": config["mpce"]["user"],
        "mpce_password": config["mpce"]["password"],
    }
