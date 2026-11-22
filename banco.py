import sqlite3

# Arquivo do banco de dados (criado sozinho na primeira vez)
ARQUIVO_BANCO = "ptolomy.db"


def conectar():
    conexao = sqlite3.connect(ARQUIVO_BANCO)
    # Permite pegar as colunas pelo nome: linha["texto"]
    conexao.row_factory = sqlite3.Row
    return conexao


# Cria a tabela de análises se ela ainda não existir
def criar_tabela():

    conexao = conectar()

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT,
            texto TEXT NOT NULL,
            ia_origem TEXT NOT NULL,
            resultado TEXT NOT NULL,
            fontes TEXT NOT NULL,
            status_validacao TEXT NOT NULL,
            observacao TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)

    conexao.commit()
    conexao.close()
