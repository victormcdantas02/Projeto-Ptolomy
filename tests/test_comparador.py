from comparador import (
    extrair_numero_associado,
    filtrar_frases_por_contexto,
    comparar_numeros_por_contexto
)


def test_numero_com_ponto():
    numero = extrair_numero_associado("O Brasil tem 5.571 municípios", "municípios")
    assert numero == 5571


def test_frase_nao_quebra_no_numero():
    texto = "O Brasil tem 5.571 municípios. Outra frase."
    frases = filtrar_frases_por_contexto(texto, ["brasil", "municípios"])
    assert frases == ["O Brasil tem 5.571 municípios"]


def test_numeros_iguais():
    resultado = comparar_numeros_por_contexto("O Brasil possui 26 estados.", "O Brasil possui 26 estados")
    assert resultado == "numeros_iguais"


def test_numeros_diferentes():
    resultado = comparar_numeros_por_contexto("O Brasil possui 30 estados.", "O Brasil possui 26 estados")
    assert resultado == "numeros_diferentes"
