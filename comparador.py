
import re


def extrair_numeros(texto):
    return re.findall(r"\d+", texto)


def comparar_numeros(afirmacao, evidencia):

    numeros_afirmacao = extrair_numeros(afirmacao)
    numeros_evidencia = extrair_numeros(evidencia)

    if not numeros_afirmacao or not numeros_evidencia:
        return "inconclusivo"

    if numeros_afirmacao == numeros_evidencia:
        return "numeros_iguais"

    return "numeros_diferentes"


def comparar_com_fontes(afirmacao, fontes):

    resultados = []

    for fonte in fontes:

        resultado = comparar_numeros(
            afirmacao,
            fonte["descricao"]
        )

        resultados.append({
            "titulo": fonte["titulo"],
            "resultado_numerico": resultado
        })

    return resultados


if __name__ == "__main__":

    afirmacao = "O Brasil possui 30 estados."

    fontes = [
        {
            "titulo": "Fonte de exemplo",
            "descricao": "O Brasil possui 26 estados."
        }
    ]

    print(comparar_com_fontes(afirmacao, fontes))
