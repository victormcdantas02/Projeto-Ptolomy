import pytest

import verificador

# Fonte de mentira, para o teste não depender da internet
FONTE = {
    "titulo": "Exemplo",
    "url": "https://exemplo.com",
    "descricao": "O Brasil possui 26 estados e 5.571 municípios."
}


def busca_falsa(afirmacao):
    return {"afirmacao": afirmacao, "fontes": [FONTE]}


def ia_desligada():
    return False


def test_fonte_confirma(monkeypatch):
    monkeypatch.setattr(verificador, "buscar_fontes", busca_falsa)
    monkeypatch.setattr(verificador.ia, "ia_disponivel", ia_desligada)
    resultado = verificador.analisar_texto("O Brasil possui 26 estados.")
    evidencia = resultado["afirmacoes"][0]["evidencias"][0]
    assert evidencia["posicao"] == "confirma"
    assert evidencia["url"] == "https://exemplo.com"


def test_fonte_contradiz(monkeypatch):
    monkeypatch.setattr(verificador, "buscar_fontes", busca_falsa)
    monkeypatch.setattr(verificador.ia, "ia_disponivel", ia_desligada)
    resultado = verificador.analisar_texto("O Brasil possui 30 estados.")
    assert resultado["afirmacoes"][0]["evidencias"][0]["posicao"] == "contradiz"


def test_pergunta_nao_e_verificada(monkeypatch):
    monkeypatch.setattr(verificador, "buscar_fontes", busca_falsa)
    monkeypatch.setattr(verificador.ia, "ia_disponivel", ia_desligada)
    resultado = verificador.analisar_texto("Quantos estados tem o Brasil?")
    assert resultado["perguntas"] == ["Quantos estados tem o Brasil?"]
    assert resultado["afirmacoes"] == []


def test_fonte_sem_relacao_fica_neutra_e_insuficiente(monkeypatch):
    fonte = {
        "titulo": "Artigo sem relação",
        "url": "https://exemplo.com/artigo",
        "descricao": "Um artigo consultado sobre assunto diferente.",
    }
    monkeypatch.setattr(
        verificador,
        "buscar_fontes",
        lambda afirmacao: {"afirmacao": afirmacao, "fontes": [fonte]},
    )

    afirmacao = verificador.analisar_texto("O Brasil possui 30 estados.")["afirmacoes"][0]

    assert afirmacao["status_evidencias"] == "evidencias_insuficientes"
    assert afirmacao["resumo_evidencias"] == {
        "compativeis": 0, "divergentes": 0, "inconclusivas": 0
    }
    assert afirmacao["evidencias"][0]["posicao"] == "neutra"
    assert afirmacao["evidencias"][0]["url"] == fonte["url"]


IBGE_UFS = {
    "titulo": "Unidades da Federação do Brasil — IBGE (API de Localidades)",
    "url": "https://servicodados.ibge.gov.br/api/v1/localidades/estados",
    "tipo_fonte": "oficial",
    "descricao": (
        "A API de Localidades do IBGE lista 27 unidades da Federação do Brasil, "
        "incluindo 26 estados e o Distrito Federal (DF)."
    ),
}


def test_evidencia_preserva_tipo_e_exibe_trecho_decisivo(monkeypatch):
    fonte = {
        **IBGE_UFS,
        "descricao": "O Brasil organiza seus estados em regiões. " + IBGE_UFS["descricao"],
    }
    monkeypatch.setattr(verificador, "buscar_fontes", lambda texto: {"fontes": [fonte]})
    monkeypatch.setattr(verificador.ia, "ia_disponivel", ia_desligada)

    evidencia, = verificador.analisar_texto(
        "O Brasil possui 30 estados."
    )["afirmacoes"][0]["evidencias"]

    assert evidencia["tipo_fonte"] == "oficial"
    assert evidencia["posicao"] == "contradiz"
    assert "26 estados" in evidencia["trecho"]


@pytest.mark.parametrize(
    ("afirmacao", "fontes", "posicao"),
    [
        ("O Brasil possui 26 estados.", [IBGE_UFS], "confirma"),
        ("O Brasil possui 30 estados.", [IBGE_UFS], "contradiz"),
        ("O Brasil possui 27 unidades federativas.", [IBGE_UFS], "confirma"),
        ("O Brasil possui 27 estados.", [IBGE_UFS], "contradiz"),
        ("O Brasil possui 26 estados e um Distrito Federal.", [IBGE_UFS], "confirma"),
        (
            "A capital do Brasil é Brasília.",
            [{"titulo": "Brasil", "url": "https://pt.wikipedia.org/brasil", "descricao": "Brasília é a capital do Brasil."}],
            "confirma",
        ),
        (
            "A capital do Brasil é Recife.",
            [{"titulo": "Brasil", "url": "https://pt.wikipedia.org/brasil", "descricao": "Brasília é a capital do Brasil."}],
            "contradiz",
        ),
        (
            "A Terra possui dois satélites naturais.",
            [{"titulo": "Lua", "url": "https://pt.wikipedia.org/lua", "descricao": "A Lua é o único satélite natural da Terra."}],
            "contradiz",
        ),
        (
            "A água é composta por hidrogênio e oxigênio.",
            [{"titulo": "Água", "url": "https://pt.wikipedia.org/agua", "descricao": "A molécula de água é composta por dois átomos de hidrogênio e um átomo de oxigênio."}],
            "confirma",
        ),
    ],
)
def test_afirmacoes_de_regressao_com_fontes_consultadas(
    monkeypatch,
    afirmacao,
    fontes,
    posicao,
):
    monkeypatch.setattr(
        verificador,
        "buscar_fontes",
        lambda texto: {"afirmacao": texto, "fontes": fontes},
    )
    monkeypatch.setattr(verificador.ia, "ia_disponivel", lambda: False)

    resultado = verificador.analisar_texto(afirmacao)
    assert resultado["afirmacoes"][0]["metodo"] == "numerico"
    assert resultado["afirmacoes"][0]["diagnostico_ia"] == "chave_ausente"
    assert posicao in [
        evidencia["posicao"]
        for evidencia in resultado["afirmacoes"][0]["evidencias"]
    ]


def test_afirmacao_composta_separa_estado_e_capital(monkeypatch):
    fontes = [
        IBGE_UFS,
        {
            "titulo": "Brasil",
            "url": "https://pt.wikipedia.org/brasil",
            "descricao": "Brasília é a capital do Brasil.",
        },
    ]
    monkeypatch.setattr(
        verificador,
        "buscar_fontes",
        lambda texto: {"afirmacao": texto, "fontes": fontes},
    )
    monkeypatch.setattr(verificador.ia, "ia_disponivel", lambda: False)

    resultado = verificador.analisar_texto(
        "O Brasil possui 26 estados e sua capital é Buenos Aires."
    )

    assert len(resultado["afirmacoes"]) == 2
    assert resultado["afirmacoes"][0]["evidencias"][0]["posicao"] == "confirma"
    assert any(
        evidencia["posicao"] == "contradiz"
        for evidencia in resultado["afirmacoes"][1]["evidencias"]
    )


def test_analisa_resposta_completa_do_chatgpt_em_lista_markdown(monkeypatch):
    fontes = [
        IBGE_UFS,
        {
            "titulo": "Brasil",
            "url": "https://pt.wikipedia.org/brasil",
            "descricao": "Brasília é a capital do Brasil.",
        },
        {
            "titulo": "Água",
            "url": "https://pt.wikipedia.org/agua",
            "descricao": (
                "A molécula de água é composta por dois átomos de hidrogênio "
                "e um átomo de oxigênio."
            ),
        },
    ]
    monkeypatch.setattr(
        verificador,
        "buscar_fontes",
        lambda texto: {"afirmacao": texto, "fontes": fontes},
    )
    monkeypatch.setattr(verificador.ia, "ia_disponivel", lambda: False)

    resultado = verificador.analisar_texto(
        "### Resposta do ChatGPT\n\n"
        "1. **O Brasil possui 26 estados e um Distrito Federal.**\n"
        "2. [A capital do Brasil é Brasília.](https://exemplo.test)\n"
        "3. A água é composta por hidrogênio e oxigênio."
    )

    assert len(resultado["afirmacoes"]) == 3
    assert all(
        afirmacao["metodo"] == "numerico"
        and afirmacao["status_evidencias"] == "evidencias_disponiveis"
        for afirmacao in resultado["afirmacoes"]
    )
