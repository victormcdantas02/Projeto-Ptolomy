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


# Função falsa que finge que a internet caiu
def analise_que_falha(texto):
    raise requests.RequestException("sem internet")


def test_wikipedia_fora_do_ar():

    # Guarda a função de verdade e coloca a falsa no lugar
    analise_original = main.analisar_texto
    main.analisar_texto = analise_que_falha

    resposta = cliente.post("/verificar", json={"texto": "O Brasil possui 26 estados."})

    # Devolve a função de verdade para não atrapalhar outros testes
    main.analisar_texto = analise_original

    assert resposta.status_code == 503
