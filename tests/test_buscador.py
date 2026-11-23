from buscador import preparar_termo_busca, pesquisar_wikipedia


def test_tira_palavras_ignoradas():
    termo = preparar_termo_busca("O Brasil possui 26 estados.")
    assert termo == "brasil estados"


def test_sem_termo_nao_busca():
    # Retorna vazio sem nem chamar a Wikipédia
    assert pesquisar_wikipedia("") == []
