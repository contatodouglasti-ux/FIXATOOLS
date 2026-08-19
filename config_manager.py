import configparser
import os
import sys


def get_base_dir():
    """
    Retorna a pasta onde o executável (ou o script) está rodando.
    Isso garante que o config.ini fique ao lado do .exe gerado,
    e não "escondido" dentro do pacote do PyInstaller.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(get_base_dir(), "config.ini")


DEFAULTS = {
    "ssh": {
        "host": "172.22.0.28",
        "port": "22",
        "user": "",
        "password": ""
    },
    "database": {
        "user": "",
        "password": "",
        "db_sp": "sigsp",
        "db_unj": "unj01sp",
        "remote_host": "192.168.1.195",
        "remote_port": "5000"
    }
}


def _criar_config_padrao():
    config = configparser.ConfigParser()
    for secao, valores in DEFAULTS.items():
        config[secao] = valores
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)
    return config


def carregar_config():
    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_PATH):
        return _criar_config_padrao()

    config.read(CONFIG_PATH, encoding="utf-8")

    # garante que todas as chaves existam, mesmo se o config.ini
    # for de uma versão antiga do programa
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
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            config.write(f)

    return config


def salvar_credenciais(ssh_user, ssh_password, db_user, db_password):
    config = carregar_config()

    config["ssh"]["user"] = ssh_user
    config["ssh"]["password"] = ssh_password
    config["database"]["user"] = db_user
    config["database"]["password"] = db_password

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)


def obter_credenciais():
    config = carregar_config()

    return {
        "ssh_host": config["ssh"]["host"],
        "ssh_port": config.getint("ssh", "port"),
        "ssh_user": config["ssh"]["user"],
        "ssh_password": config["ssh"]["password"],
        "db_user": config["database"]["user"],
        "db_password": config["database"]["password"],
        "db_sp": config["database"]["db_sp"],
        "db_unj": config["database"]["db_unj"],
        "remote_host": config["database"]["remote_host"],
        "remote_port": config.getint("database", "remote_port"),
    }