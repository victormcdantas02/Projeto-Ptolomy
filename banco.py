import json
import sqlite3
from datetime import datetime

# Arquivo do banco de dados (criado sozinho na primeira vez)
ARQUIVO_BANCO = "ptolomy.db"

# Status que o aluno pode escolher ao validar uma análise
STATUS_VALIDOS = ["não verificado", "confirmado", "falso"]


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


# Transforma uma linha do banco em dicionário (o JSON volta a ser lista/dicionário)
def linha_para_dict(linha):

    analise = dict(linha)
    analise["resultado"] = json.loads(analise["resultado"])
    analise["fontes"] = json.loads(analise["fontes"])

    return analise


# CREATE - salva uma análise nova e devolve o id dela
def salvar_analise(usuario_id, texto, ia_origem, resultado, fontes):

    conexao = conectar()

    cursor = conexao.execute(
        """INSERT INTO analises
           (usuario_id, texto, ia_origem, resultado, fontes, status_validacao, observacao, data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            usuario_id,
            texto,
            ia_origem,
            json.dumps(resultado, ensure_ascii=False),
            json.dumps(fontes, ensure_ascii=False),
            "não verificado",
            "",
            datetime.now().isoformat(timespec="seconds")
        )
    )

    conexao.commit()
    novo_id = cursor.lastrowid
    conexao.close()

    return novo_id


# READ - busca uma análise pelo id (None se não existir)
def buscar_analise(analise_id):

    conexao = conectar()

    linha = conexao.execute(
        "SELECT * FROM analises WHERE id = ?",
        (analise_id,)
    ).fetchone()

    conexao.close()

    if linha is None:
        return None

    return linha_para_dict(linha)


# READ - lista as análises, da mais nova para a mais antiga
# (se vier usuario_id, mostra só as daquele usuário)
def listar_analises(usuario_id=None):

    conexao = conectar()

    if usuario_id:
        linhas = conexao.execute(
            "SELECT * FROM analises WHERE usuario_id = ? ORDER BY id DESC",
            (usuario_id,)
        ).fetchall()
    else:
        linhas = conexao.execute(
            "SELECT * FROM analises ORDER BY id DESC"
        ).fetchall()

    conexao.close()

    return [linha_para_dict(linha) for linha in linhas]


# UPDATE - muda o status da validação e a observação
# (devolve False se a análise não existir)
def atualizar_analise(analise_id, status_validacao, observacao):

    conexao = conectar()

    cursor = conexao.execute(
        "UPDATE analises SET status_validacao = ?, observacao = ? WHERE id = ?",
        (status_validacao, observacao, analise_id)
    )

    conexao.commit()
    conexao.close()

    return cursor.rowcount > 0


# DELETE - remove uma análise (devolve False se ela não existir)
def excluir_analise(analise_id):

    conexao = conectar()

    cursor = conexao.execute(
        "DELETE FROM analises WHERE id = ?",
        (analise_id,)
    )

    conexao.commit()
    conexao.close()

    return cursor.rowcount > 0
