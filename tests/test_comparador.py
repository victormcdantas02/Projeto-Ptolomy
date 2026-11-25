import pytest

from comparador import (
    comparar_com_fontes,
    comparar_numeros_por_contexto,
    extrair_numero_associado,
    filtrar_frases_por_contexto,
    separar_frases,
)


IBGE_UFS = (
    "A API de Localidades do IBGE lista 27 unidades da Federacao, incluindo "
    "26 estados e o Distrito Federal (DF)."
)


def _classificacoes(afirmacao, descricao, titulo="Brasil"):
    fontes = [{"titulo": titulo, "url": "https://exemplo.test/fonte", "descricao": descricao}]
    comparacoes = comparar_com_fontes(afirmacao, fontes)[0]["comparacoes"]
    return [comparacao["classificacao"] for comparacao in comparacoes]


def test_numero_com_ponto():
    assert extrair_numero_associado("O Brasil tem 5.571 municipios", "municipios") == 5571


def test_frase_nao_quebra_no_numero():
    texto = "O Brasil tem 5.571 municipios. Outra frase."
    assert filtrar_frases_por_contexto(texto, ["brasil", "municipios"]) == [
        "O Brasil tem 5.571 municipios"
    ]


def test_numeros_escritos_por_extenso_e_variacao_plural():
    assert comparar_numeros_por_contexto(
        "A Terra possui dois satelites naturais.",
        "A Lua e o unico satelite natural da Terra.",
    ) == "numeros_diferentes"


def test_mesma_quantidade_em_entidade_diferente_nao_confirma_afirmacao():
    assert comparar_numeros_por_contexto(
        "A Terra possui dois satélites naturais.",
        "Haumea possui dois satélites naturais.",
        "Satélites de Haumea",
    ) == "inconclusivo"


def test_unidades_federativas_nao_sao_contadas_como_estados():
    assert comparar_numeros_por_contexto(
        "O Brasil possui 27 estados.",
        "O Brasil possui 27 unidades da federacao.",
    ) == "inconclusivo"


def test_unidades_de_medida_diferentes_nao_sao_comparadas_como_mesma_quantidade():
    assert comparar_numeros_por_contexto(
        "A temperatura e 100 graus Celsius.",
        "A temperatura e 100 graus Fahrenheit.",
    ) == "inconclusivo"
    assert comparar_numeros_por_contexto(
        "A temperatura e 100 °C.",
        "A temperatura e 100 °F.",
    ) == "inconclusivo"


def test_quantidades_com_conceito_igual_sustentam_ou_contradizem():
    assert _classificacoes("O Brasil possui 26 estados.", IBGE_UFS) == ["compativel"]
    assert _classificacoes("O Brasil possui 30 estados.", IBGE_UFS) == ["divergente"]


def test_unidades_federativas_e_estados_com_df_sao_conceitos_distintos():
    assert _classificacoes("O Brasil possui 27 unidades federativas.", IBGE_UFS) == ["compativel"]
    assert _classificacoes("O Brasil possui 27 estados.", IBGE_UFS) == ["divergente"]
    assert _classificacoes(
        "O Brasil possui 26 estados e um Distrito Federal.",
        IBGE_UFS,
    ) == ["compativel"]


def test_relacao_capital_compara_entidade_e_valor():
    fonte = "Brasilia e a capital do Brasil."
    assert _classificacoes("A capital do Brasil e Brasilia.", fonte) == ["compativel"]
    assert _classificacoes("A capital do Brasil e Recife.", fonte) == ["divergente"]


def test_relacao_de_capital_em_registro_estruturado_wikidata():
    fonte = (
        "Registro estruturado do Wikidata (propriedade P36): "
        "A capital do Brasil é Brasília."
    )
    assert _classificacoes(
        "A capital do Brasil é Recife.",
        fonte,
        "Brasil — Wikidata",
    ) == ["divergente"]


def test_composicao_quimica_compara_componentes():
    fonte = (
        "A molecula de agua e composta por dois atomos de hidrogenio "
        "e um atomo de oxigenio."
    )
    assert _classificacoes(
        "A agua e composta por hidrogenio e oxigenio.",
        fonte,
    ) == ["compativel"]


def test_composicao_reconhece_moleculas_formadas_por_componentes():
    descricao = (
        "Água (fórmula química: H2O) é uma substância química cujas moléculas "
        "são formadas por dois átomos de hidrogênio e um de oxigênio."
    )
    assert _classificacoes(
        "A água é composta por hidrogênio e oxigênio.",
        descricao,
        "Água",
    ) == ["compativel"]


def test_separa_afirmacao_composta_e_preserva_contexto_do_sujeito():
    frases = separar_frases(
        "O Brasil possui 26 estados e sua capital e Buenos Aires."
    )
    assert frases == [
        "O Brasil possui 26 estados",
        "capital do Brasil e Buenos Aires.",
    ]


def test_afirmacao_composta_com_lista_markdown():
    assert separar_frases(
        "- O Brasil possui 26 estados.\n"
        "- A capital do Brasil e Brasilia.\n"
        "1. A agua e composta por hidrogenio e oxigenio."
    ) == [
        "O Brasil possui 26 estados.",
        "A capital do Brasil e Brasilia.",
        "A agua e composta por hidrogenio e oxigenio.",
    ]


def test_extrai_afirmacoes_de_resposta_completa_do_chatgpt_em_markdown():
    resposta = (
        "### Resposta do ChatGPT\n\n"
        "1. **O Brasil possui 26 estados e um Distrito Federal.**\n"
        "2. [A capital do Brasil é Brasília.](https://exemplo.test)\n"
        "3. A água é composta por hidrogênio e oxigênio."
    )
    assert separar_frases(resposta) == [
        "O Brasil possui 26 estados e um Distrito Federal.",
        "A capital do Brasil é Brasília.",
        "A água é composta por hidrogênio e oxigênio.",
    ]


def test_numero_com_expoente_nao_e_confundido_com_contagem():
    assert extrair_numero_associado("A area tem 10² metros", "metros") is None


@pytest.mark.parametrize(
    ("afirmacao", "descricao", "esperada"),
    [
        ("O Brasil possui 26 estados.", IBGE_UFS, "compativel"),
        ("O Brasil possui 30 estados.", IBGE_UFS, "divergente"),
        ("O Brasil possui 27 unidades federativas.", IBGE_UFS, "compativel"),
        ("O Brasil possui 27 estados.", IBGE_UFS, "divergente"),
        ("O Brasil possui 26 estados e um Distrito Federal.", IBGE_UFS, "compativel"),
        ("A capital do Brasil e Brasilia.", "Brasilia e a capital do Brasil.", "compativel"),
        ("A capital do Brasil e Recife.", "Brasilia e a capital do Brasil.", "divergente"),
        (
            "A Terra possui dois satelites naturais.",
            "A Lua e o unico satelite natural da Terra.",
            "divergente",
        ),
        (
            "A agua e composta por hidrogenio e oxigenio.",
            "A agua e composta por atomos de hidrogenio e oxigenio.",
            "compativel",
        ),
    ],
)
def test_regressoes_de_afirmacoes_solicitadas(afirmacao, descricao, esperada):
    assert esperada in _classificacoes(afirmacao, descricao)


def test_subconjunto_de_estados_nao_contradiz_total():
    assert comparar_numeros_por_contexto(
        "O Brasil possui 26 estados e um Distrito Federal.",
        "Os cinco estados mais populosos do Brasil concentram a população.",
        "Estados do Brasil",
    ) == "inconclusivo"


def test_pontuacao_isolada_nao_gera_comparacoes():
    assert filtrar_frases_por_contexto(
        "...!!", ["brasil", "estados"], "Estados do Brasil"
    ) == []
