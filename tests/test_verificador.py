import verificador

# Fonte de mentira, para o teste não depender da internet
FONTE = {
    "titulo": "Exemplo",
    "url": "https://exemplo.com",
    "descricao": "O Brasil possui 26 estados e 5.571 municípios."
}


def busca_falsa(afirmacao):
    return {"afirmacao": afirmacao, "fontes": [FONTE]}


# Nos testes, o verificador usa a busca falsa no lugar da Wikipédia
verificador.buscar_fontes = busca_falsa


# Estes testes conferem a comparação de números, então a IA fica desligada
def ia_desligada():
    return False


verificador.ia.ia_disponivel = ia_desligada


def test_fonte_confirma():
    resultado = verificador.analisar_texto("O Brasil possui 26 estados.")
    evidencia = resultado["afirmacoes"][0]["evidencias"][0]
    assert evidencia["posicao"] == "confirma"
    assert evidencia["url"] == "https://exemplo.com"


def test_fonte_contradiz():
    resultado = verificador.analisar_texto("O Brasil possui 30 estados.")
    assert resultado["afirmacoes"][0]["evidencias"][0]["posicao"] == "contradiz"


def test_pergunta_nao_e_verificada():
    resultado = verificador.analisar_texto("Quantos estados tem o Brasil?")
    assert resultado["perguntas"] == ["Quantos estados tem o Brasil?"]
    assert resultado["afirmacoes"] == []
