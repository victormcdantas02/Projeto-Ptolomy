import requests
from fastapi.testclient import TestClient

import main

cliente = TestClient(main.app)


def test_api_funcionando():
    resposta = cliente.get("/")
    assert resposta.status_code == 200


def test_texto_curto_e_recusado():
    resposta = cliente.post("/verificar", json={"texto": "curto"})
    assert resposta.status_code == 422


def test_wikipedia_fora_do_ar(monkeypatch):

    def analise_que_falha(texto):
        raise requests.RequestException("sem internet")

    monkeypatch.setattr(main, "analisar_texto", analise_que_falha)
    resposta = cliente.post("/verificar", json={"texto": "O Brasil possui 26 estados."})
    assert resposta.status_code == 503
