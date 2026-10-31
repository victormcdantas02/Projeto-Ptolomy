
import re


# 1. Extrair números de um texto
def extrair_numeros(texto):

    numeros = re.findall(r"\d+", texto)

    return numeros


# 2. Comparar números entre dois textos
def comparar_numeros(afirmacao, evidencia):

    numeros_afirmacao = extrair_numeros(afirmacao)
    numeros_evidencia = extrair_numeros(evidencia)

    if not numeros_afirmacao or not numeros_evidencia:
        return "inconclusivo"

    if numeros_afirmacao == numeros_evidencia:
        return "numeros_iguais"

    return "numeros_diferentes"


# 3. Encontrar frases com uma palavra-chave
def encontrar_frases_relevantes(evidencia, palavra_chave):

    frases = re.split(r"[.!?]", evidencia)

    relevantes = []

    for frase in frases:

        if palavra_chave.lower() in frase.lower():
            relevantes.append(frase.strip())

    return relevantes


# 4. Comparar números nas frases relevantes
def comparar_frases_relevantes(
    afirmacao,
    evidencia,
    palavra_chave
):

    frases = encontrar_frases_relevantes(
        evidencia,
        palavra_chave
    )

    resultados = []

    for frase in frases:

        resultado = comparar_numeros(
            afirmacao,
            frase
        )

        resultados.append({
            "frase": frase,
            "resultado": resultado
        })

    return resultados


# 5. Extrair palavras-chave automaticamente
def extrair_palavras_chave(afirmacao):

    palavras_ignoradas = {
        "o", "a", "os", "as",
        "um", "uma", "de", "do", "da",
        "dos", "das", "em", "no", "na",
        "e", "possui", "tem", "é"
    }

    palavras = re.findall(
        r"[a-zA-ZÀ-ÿ]+",
        afirmacao.lower()
    )

    palavras_chave = []

    for palavra in palavras:

        if palavra not in palavras_ignoradas:
            palavras_chave.append(palavra)

    return palavras_chave


# 6. Filtrar frases por contexto

def filtrar_frases_por_contexto(evidencia, palavras_chave):

    frases = re.split(r"[.!?]", evidencia)

    relevantes = []

    if not palavras_chave:
        return relevantes

    for frase in frases:

        todas_presentes = all(
            re.search(
                rf"\b{re.escape(palavra)}\b",
                frase,
                re.IGNORECASE
            )
            for palavra in palavras_chave
        )

        if todas_presentes:
            relevantes.append(frase.strip())

    return relevantes

# 7. Extrair número associado a uma palavra
def extrair_numero_associado(texto, palavra):

    padrao = rf"(\d+)\s+{re.escape(palavra)}\b"

    resultado = re.search(
        padrao,
        texto,
        re.IGNORECASE
    )

    if resultado:
        return int(resultado.group(1))

    return None


# 8. Comparar números pelo contexto
def comparar_numeros_por_contexto(afirmacao, evidencia):

    palavras_chave = extrair_palavras_chave(afirmacao)

    for palavra in palavras_chave:

        numero_afirmacao = extrair_numero_associado(
            afirmacao,
            palavra
        )

        if numero_afirmacao is None:
            continue

        numero_evidencia = extrair_numero_associado(
            evidencia,
            palavra
        )

        if numero_evidencia is None:
            continue

        if numero_afirmacao == numero_evidencia:
            return "numeros_iguais"

        return "numeros_diferentes"

    return "inconclusivo"


# 9. Classificar a comparação numérica
def classificar_evidencia(resultado_numerico):

    if resultado_numerico == "numeros_iguais":
        return "compativel"

    elif resultado_numerico == "numeros_diferentes":
        return "divergente"

    else:
        return "inconclusiva"


# 10. Comparar a afirmação com as fontes
def comparar_com_fontes(afirmacao, fontes):

    resultados = []

    palavras_chave = extrair_palavras_chave(afirmacao)

    for fonte in fontes:

        frases_relevantes = filtrar_frases_por_contexto(
            fonte["descricao"],
            palavras_chave
        )

        comparacoes = []

        for frase in frases_relevantes:

            resultado = comparar_numeros_por_contexto(
                afirmacao,
                frase
            )

            classificacao = classificar_evidencia(
                resultado
            )

            comparacoes.append({
                "frase": frase,
                "resultado": resultado,
                "classificacao": classificacao
            })

        resultados.append({
            "titulo": fonte["titulo"],
            "comparacoes": comparacoes
        })

    return resultados

def resumir_evidencias(resultados):

    resumo = {
        "compativeis": 0,
        "divergentes": 0,
        "inconclusivas": 0
    }

    for fonte in resultados:

        for comparacao in fonte["comparacoes"]:

            classificacao = comparacao["classificacao"]

            if classificacao == "compativel":
                resumo["compativeis"] += 1

            elif classificacao == "divergente":
                resumo["divergentes"] += 1

            else:
                resumo["inconclusivas"] += 1

    return resumo


def determinar_resultado_geral(resumo):

    compativeis = resumo["compativeis"]
    divergentes = resumo["divergentes"]

    if compativeis > 0 and divergentes > 0:
        return "evidencias_mistas"

    elif compativeis > 0:
        return "compatibilidade_numerica"

    elif divergentes > 0:
        return "divergencia_numerica"

    else:
        return "inconclusivo"


def filtrar_fontes_com_evidencias(resultados):

    fontes_relevantes = []

    for fonte in resultados:

        if len(fonte["comparacoes"]) > 0:
            fontes_relevantes.append(fonte)

    return fontes_relevantes

# 11. Testar o comparador
if __name__ == "__main__":

    afirmacao = "O Brasil possui 26 estados."

    fontes = [
        {
            "titulo": "Fonte de exemplo",
            "descricao": (
                "O Brasil possui 26 estados "
                "e 5571 municípios."
            )
        }
    ]

    resultados = comparar_com_fontes(
        afirmacao,
        fontes
    )

    print("RESULTADOS DA COMPARAÇÃO:")

    for resultado in resultados:
        print(resultado)

    resumo = resumir_evidencias(resultados)

    print("\nRESUMO DAS EVIDÊNCIAS:")
    print(resumo)

    resultado_geral = determinar_resultado_geral(resumo)

    print("\nRESULTADO GERAL:")
    print(resultado_geral)
    fontes_relevantes = filtrar_fontes_com_evidencias(resultados)

    print("\nFONTES COM EVIDÊNCIAS:")
    print(fontes_relevantes)
    

