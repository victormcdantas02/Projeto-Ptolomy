import sqlite3
from importlib import import_module
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import banco

# main cria a tabela ao importar; mantenha essa inicialização fora do banco local.
_BANCO_IMPORT = tempfile.TemporaryDirectory(prefix="ptolomy-test-import-")
banco.ARQUIVO_BANCO = str(Path(_BANCO_IMPORT.name) / "analises.db")

main = import_module("main")

cliente = TestClient(main.app)

NOVA = {
    "usuario_id": "usr-aluno",
    "texto": "O Brasil possui 26 estados.",
    "ia_origem": "ChatGPT",
    "resultado": {"score": 55, "cor": "amarelo"},
    "fontes": [{"posicao": "confirma"}]
}


@pytest.fixture(autouse=True)
def preparar_banco(tmp_path, monkeypatch):
    monkeypatch.setattr(banco, "ARQUIVO_BANCO", str(tmp_path / "analises.db"))
    banco.criar_tabela()


def test_cadastrar():
    resposta = cliente.post("/analises", json=NOVA)
    assert resposta.status_code == 201
    analise = resposta.json()
    assert analise["ia_origem"] == "ChatGPT"
    assert analise["status_validacao"] == "não verificado"
    assert analise["fontes"] == [{"posicao": "confirma"}]


def test_listar_so_do_usuario():
    cliente.post("/analises", json=NOVA)

    outra = NOVA.copy()
    outra["usuario_id"] = "usr-maria"
    cliente.post("/analises", json=outra)

    resposta = cliente.get("/analises", params={"usuario_id": "usr-aluno"})
    assert len(resposta.json()) == 1


def test_editar_status_e_observacao():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "confirmado", "observacao": "Conferi no IBGE"})
    assert resposta.status_code == 200
    assert resposta.json()["status_validacao"] == "confirmado"
    assert resposta.json()["observacao"] == "Conferi no IBGE"


def test_salvar_conclusao_e_fontes_consultadas():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(
        f"/analises/{analise_id}",
        json={
            "status_validacao": "não verificado",
            "observacao": "Conferi fontes independentes",
            "conclusao_usuario": "necessita_pesquisa",
            "fontes_consultadas": ["google_academico", "scielo"],
        },
    )
    assert resposta.status_code == 200
    assert resposta.json()["conclusao_usuario"] == "necessita_pesquisa"
    assert resposta.json()["fontes_consultadas"] == ["google_academico", "scielo"]


def test_migrar_banco_existente_sem_perder_analise(tmp_path, monkeypatch):
    arquivo = tmp_path / "legado.db"
    conexao = sqlite3.connect(arquivo)
    conexao.execute("""
        CREATE TABLE analises (
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
    conexao.execute(
        """INSERT INTO analises
           (usuario_id, texto, ia_origem, resultado, fontes, status_validacao, observacao, data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("usr-aluno", "Afirmação antiga.", "ChatGPT", "{}", "[]", "não verificado", "", "2025-01-01"),
    )
    conexao.commit()
    conexao.close()

    monkeypatch.setattr(banco, "ARQUIVO_BANCO", str(arquivo))
    banco.criar_tabela()

    analise = banco.buscar_analise(1)
    assert analise["texto"] == "Afirmação antiga."
    assert analise["conclusao_usuario"] == ""
    assert analise["fontes_consultadas"] == []


def test_rejeitar_conclusao_invalida():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(
        f"/analises/{analise_id}",
        json={
            "status_validacao": "não verificado",
            "conclusao_usuario": "verdadeiro_com_certeza",
        },
    )
    assert resposta.status_code == 400


def test_status_invalido():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "talvez"})
    assert resposta.status_code == 400


def test_excluir():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    assert cliente.delete(f"/analises/{analise_id}").status_code == 204
    assert cliente.get(f"/analises/{analise_id}").status_code == 404
