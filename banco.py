import json
import sqlite3
from datetime import datetime

# Arquivo do banco de dados (criado sozinho na primeira vez)
ARQUIVO_BANCO = "ptolomy.db"

# Status que o aluno pode escolher ao validar uma análise
STATUS_VALIDOS = ["não verificado", "confirmado", "falso"]
CONCLUSOES_USUARIO_VALIDAS = [
    "",
    "confirmada",
    "contradita",
    "evidencias_insuficientes",
    "necessita_pesquisa",
]


def conectar():
    conexao = sqlite3.connect(ARQUIVO_BANCO)
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
            data TEXT NOT NULL,
            conclusao_usuario TEXT NOT NULL DEFAULT '',
            fontes_consultadas TEXT NOT NULL DEFAULT '[]'
        )
    """)

    colunas = {
        coluna[1]
        for coluna in conexao.execute("PRAGMA table_info(analises)").fetchall()
    }
    if "conclusao_usuario" not in colunas:
        conexao.execute(
            "ALTER TABLE analises ADD COLUMN conclusao_usuario TEXT NOT NULL DEFAULT ''"
        )
    if "fontes_consultadas" not in colunas:
        conexao.execute(
            "ALTER TABLE analises ADD COLUMN fontes_consultadas TEXT NOT NULL DEFAULT '[]'"
        )

    conexao.commit()
    conexao.close()


# Transforma uma linha do banco em dicionário.
# A linha vem como TUPLA, na mesma ordem das colunas da tabela:
# (id, usuario_id, texto, ia_origem, resultado, fontes, status_validacao, observacao, data)
def linha_para_dict(linha):

    analise = {
        "id": linha[0],
        "usuario_id": linha[1],
        "texto": linha[2],
        "ia_origem": linha[3],
        # resultado e fontes foram guardados como texto JSON: voltam a ser dicionário/lista
        "resultado": json.loads(linha[4]),
        "fontes": json.loads(linha[5]),
        "status_validacao": linha[6],
        "observacao": linha[7],
        "data": linha[8]
    }

    analise["conclusao_usuario"] = linha[9] if len(linha) > 9 else ""
    analise["fontes_consultadas"] = (
        json.loads(linha[10]) if len(linha) > 10 else []
    )
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

    # fetchall devolve uma lista de tuplas (uma "matriz": linhas x colunas)
    analises = []

    for linha in linhas:
        analises.append(linha_para_dict(linha))

    return analises


# UPDATE - muda o status da validação e a observação
# (devolve False se a análise não existir)
def atualizar_analise(
    analise_id,
    status_validacao,
    observacao,
    conclusao_usuario=None,
    fontes_consultadas=None,
):

    conexao = conectar()

    cursor = conexao.execute(
        """UPDATE analises
           SET status_validacao = ?, observacao = ?,
               conclusao_usuario = COALESCE(?, conclusao_usuario),
               fontes_consultadas = COALESCE(?, fontes_consultadas)
           WHERE id = ?""",
        (
            status_validacao,
            observacao,
            conclusao_usuario,
            (
                json.dumps(fontes_consultadas, ensure_ascii=False)
                if fontes_consultadas is not None
                else None
            ),
            analise_id,
        )
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
