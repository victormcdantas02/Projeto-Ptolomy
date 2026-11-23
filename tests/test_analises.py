import os

from fastapi.testclient import TestClient

import banco
import main

cliente = TestClient(main.app)

# Arquivo de banco só para os testes (não mexe no ptolomy.db)
ARQUIVO_TESTE = "teste_analises.db"

NOVA = {
    "usuario_id": "usr-aluno",
    "texto": "O Brasil possui 26 estados.",
    "ia_origem": "ChatGPT",
    "resultado": {"score": 55, "cor": "amarelo"},
    "fontes": [{"posicao": "confirma"}]
}


# Cada teste chama esta função primeiro: começa com um banco vazio
def preparar_banco():
    banco.ARQUIVO_BANCO = ARQUIVO_TESTE

    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)

    banco.criar_tabela()


def test_cadastrar():
    preparar_banco()
    resposta = cliente.post("/analises", json=NOVA)
    assert resposta.status_code == 201
    analise = resposta.json()
    assert analise["ia_origem"] == "ChatGPT"
    assert analise["status_validacao"] == "não verificado"
    assert analise["fontes"] == [{"posicao": "confirma"}]


def test_listar_so_do_usuario():
    preparar_banco()
    cliente.post("/analises", json=NOVA)

    outra = NOVA.copy()
    outra["usuario_id"] = "usr-maria"
    cliente.post("/analises", json=outra)

    resposta = cliente.get("/analises", params={"usuario_id": "usr-aluno"})
    assert len(resposta.json()) == 1


def test_editar_status_e_observacao():
    preparar_banco()
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "confirmado", "observacao": "Conferi no IBGE"})
    assert resposta.status_code == 200
    assert resposta.json()["status_validacao"] == "confirmado"
    assert resposta.json()["observacao"] == "Conferi no IBGE"


def test_status_invalido():
    preparar_banco()
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    resposta = cliente.put(f"/analises/{analise_id}", json={"status_validacao": "talvez"})
    assert resposta.status_code == 400


def test_excluir():
    preparar_banco()
    analise_id = cliente.post("/analises", json=NOVA).json()["id"]
    assert cliente.delete(f"/analises/{analise_id}").status_code == 204
    assert cliente.get(f"/analises/{analise_id}").status_code == 404
