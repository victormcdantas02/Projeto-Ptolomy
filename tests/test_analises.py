import pytest
from fastapi.testclient import TestClient

import banco
import main

cliente = TestClient(main.app)

NOVA = {
    "usuario_id": "usr-aluno",
    "texto": "O Brasil possui 26 estados.",
    "ia_origem": "ChatGPT",
    "resultado": {"score": 55, "cor": "amarelo"},
    "fontes": [{"posicao": "confirma"}]
}


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    # Cada teste usa um banco novo e vazio, sem mexer no ptolomy.db
    monkeypatch.setattr(banco, "ARQUIVO_BANCO", str(tmp_path / "teste.db"))
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
    cliente.post("/analises", json={**NOVA, "usuario_id": "usr-maria"})
    resposta = cliente.get("/analises", params={"usuario_id": "usr-aluno"})
    assert len(resposta.json()) == 1


def test_editar_status_e_observacao():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "confirmado", "observacao": "Conferi no IBGE"})
    assert resposta.status_code == 200
    assert resposta.json()["status_validacao"] == "confirmado"
    assert resposta.json()["observacao"] == "Conferi no IBGE"


def test_status_invalido():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "talvez"})
    assert resposta.status_code == 400


def test_excluir():
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    assert cliente.delete(f"/analises/{analise_id}").status_code == 204
    assert cliente.get(f"/analises/{analise_id}").status_code == 404
