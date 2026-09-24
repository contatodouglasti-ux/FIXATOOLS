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
    },
    "mprs": {
        "host": "",
        "port": "5432",
        "db_rs": "sigrs",
        "db_unj": "unj01rs",
        "user": "",
        "password": ""
    }
}


def _criar_config_padrao():
    config = configparser.ConfigParser(strict=False)
    for secao, valores in DEFAULTS.items():
        config[secao] = valores
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)
    return config


def carregar_config():
    # strict=False permite recuperar configurações antigas que acabaram
    # recebendo a mesma chave duas vezes na mesma seção. O último valor
    # informado no arquivo é mantido e, ao salvar, o arquivo é normalizado.
    config = configparser.ConfigParser(strict=False)

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


def salvar_credenciais(
    ssh_user,
    ssh_password,
    db_user,
    db_password,
    mprs_host=None,
    mprs_port=None,
    mprs_db_rs=None,
    mprs_db_unj=None,
    mprs_user=None,
    mprs_password=None,
    mprs_dbname=None,
):
    config = carregar_config()

    config["ssh"]["user"] = ssh_user
    config["ssh"]["password"] = ssh_password
    config["database"]["user"] = db_user
    config["database"]["password"] = db_password

    # mprs_dbname é mantido como alias para instalações que usavam a
    # configuração anterior com apenas um banco MPRS.
    if mprs_db_rs is None:
        mprs_db_rs = mprs_dbname

    mprs_valores = {
        "host": mprs_host,
        "port": mprs_port,
        "db_rs": mprs_db_rs,
        "db_unj": mprs_db_unj,
        "user": mprs_user,
        "password": mprs_password,
    }
    for chave, valor in mprs_valores.items():
        if valor is not None:
            config["mprs"][chave] = str(valor)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)


def salvar_mpce_unj(host, port, db_unj, user, password):
    """Salva somente a conexão direta do banco sajptf do MPCE."""
    config = carregar_config()
    config["mpce"]["host"] = str(host or "").strip()
    config["mpce"]["port"] = str(port or "5432").strip()
    config["mpce"]["db_unj"] = str(db_unj or "unj01ce").strip()
    config["mpce"]["user"] = str(user or "").strip()
    config["mpce"]["password"] = str(password or "")

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
        "mprs_host": config["mprs"]["host"],
        "mprs_port": config.getint("mprs", "port"),
        "mprs_db_rs": config["mprs"]["db_rs"],
        "mprs_db_unj": config["mprs"]["db_unj"],
        "mprs_dbname": config["mprs"]["db_rs"],
        "mprs_user": config["mprs"]["user"],
        "mprs_password": config["mprs"]["password"],
        "mpce_host": config["mpce"]["host"],
        "mpce_port": config.getint("mpce", "port"),
        "mpce_db_unj": config["mpce"]["db_unj"],
        "mpce_user": config["mpce"]["user"],
        "mpce_password": config["mpce"]["password"],
    }
