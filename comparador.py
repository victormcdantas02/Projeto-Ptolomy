
# Separa um texto em frases, olhando letra por letra.
# Corta depois de . ! ? mas não no ponto de números como "5.571"
def separar_frases(texto):

    frases = []
    atual = ""

    for i in range(len(texto)):

        letra = texto[i]
        atual = atual + letra

        if letra in ".!?":

            # Se o próximo caractere for um dígito, é ponto de número
            if i + 1 < len(texto) and texto[i + 1].isdigit():
                continue

            frases.append(atual.strip())
            atual = ""

    # Sobrou um pedaço sem pontuação no final
    if atual.strip() != "":
        frases.append(atual.strip())

    return frases


# Pontuação que tiramos das pontas de cada palavra
PONTUACAO = ".,;:!?()\"'"


# Separa um texto em palavras: minúsculas e sem pontuação nas pontas
def separar_palavras(texto):

    palavras = []

    for palavra in texto.lower().split():

        palavra = palavra.strip(PONTUACAO)

        if palavra != "":
            palavras.append(palavra)

    return palavras


# 1. Extrair palavras-chave automaticamente
def extrair_palavras_chave(afirmacao):

    palavras_ignoradas = [
        "o", "a", "os", "as",
        "um", "uma", "de", "do", "da",
        "dos", "das", "em", "no", "na",
        "e", "possui", "tem", "é"
    ]

    palavras_chave = []

    for palavra in separar_palavras(afirmacao):

        # Fica só com palavras feitas de letras (sem números)
        # e que não estão na lista de ignoradas
        if palavra.isalpha() and palavra not in palavras_ignoradas:
            palavras_chave.append(palavra)

    return palavras_chave


# 2. Filtrar frases por contexto

def filtrar_frases_por_contexto(evidencia, palavras_chave):

    frases = separar_frases(evidencia)

    relevantes = []

    if not palavras_chave:
        return relevantes

    for frase in frases:

        palavras_da_frase = separar_palavras(frase)

        # A frase só serve se tiver TODAS as palavras-chave
        todas_presentes = True

        for palavra in palavras_chave:
            if palavra not in palavras_da_frase:
                todas_presentes = False

        if todas_presentes:
            # Guarda a frase sem a pontuação do final
            relevantes.append(frase.strip(" .!?"))

    return relevantes

# 3. Extrair número associado a uma palavra
def extrair_numero_associado(texto, palavra):

    palavras = separar_palavras(texto)

    # Procura a palavra e olha a palavra que vem logo antes dela
    for i in range(1, len(palavras)):

        # Tira o ponto de números como "5.571"
        anterior = palavras[i - 1].replace(".", "")

        if palavras[i] == palavra and anterior.isdecimal():
            return int(anterior)

    return None


# 4. Comparar números pelo contexto
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


# 5. Classificar a comparação numérica
def classificar_evidencia(resultado_numerico):

    if resultado_numerico == "numeros_iguais":
        return "compativel"

    elif resultado_numerico == "numeros_diferentes":
        return "divergente"

    else:
        return "inconclusiva"


# 6. Comparar a afirmação com as fontes
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
            "url": fonte.get("url"),
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

# 7. Testar o comparador
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
    

