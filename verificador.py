import anthropic

import ia
from buscador import buscar_fontes
from comparador import (
    separar_frases,
    comparar_com_fontes,
    resumir_evidencias,
    determinar_resultado_geral,
    filtrar_fontes_com_evidencias
)

# Traduz o resultado da comparação para a posição que o site mostra
def definir_posicao(resultado):

    if resultado == "compatibilidade_numerica":
        return "confirma"

    elif resultado == "divergencia_numerica":
        return "contradiz"

    else:
        return "neutra"


def montar_evidencias(fontes_relevantes):

    evidencias = []

    for fonte in fontes_relevantes:

        # Resume as frases desta fonte e vê se ela confirma ou contradiz
        resumo = resumir_evidencias([fonte])
        resultado = determinar_resultado_geral(resumo)

        evidencias.append({
            "titulo": fonte["titulo"],
            "url": fonte["url"],
            "posicao": definir_posicao(resultado),
            "trecho": fonte["comparacoes"][0]["frase"]
        })

    return evidencias


# Monta as evidências a partir do que a IA decidiu sobre cada fonte
def montar_evidencias_ia(avaliacoes, fontes):

    evidencias = []

    for avaliacao in avaliacoes:

        fonte = fontes[avaliacao["indice"]]

        # Sem trecho (fonte neutra), mostra o começo do resumo do artigo
        trecho = avaliacao["trecho"].strip()

        if trecho == "":
            trecho = fonte["descricao"][:200]

        evidencias.append({
            "titulo": fonte["titulo"],
            "url": fonte["url"],
            "posicao": avaliacao["posicao"],
            "trecho": trecho,
            "justificativa": avaliacao["justificativa"]
        })

    return evidencias


# Pede para a IA julgar as fontes. Devolve None se não der (sem chave, erro ou recusa)
def avaliar_com_ia(frase, fontes):

    if not ia.ia_disponivel():
        return None

    try:
        avaliacoes = ia.avaliar_fontes(frase, fontes)
    except anthropic.APIError:
        # Chave inválida, sem crédito, sem internet... segue com a comparação de números
        return None

    if avaliacoes is None:
        return None

    return montar_evidencias_ia(avaliacoes, fontes)


def analisar_texto(texto):

    afirmacoes = []
    perguntas = []

    # 1. Separar o texto em frases (sem quebrar números como "5.571")
    frases = separar_frases(texto)

    # 2. Analisar cada frase
    for frase in frases:

        frase = frase.strip()

        # Ignorar frases vazias
        if not frase:
            continue

        # 3. Identificar perguntas
        if frase.endswith("?"):
            perguntas.append(frase)

        # 4. Identificar afirmações
        else:

            # Buscar fontes na Wikipédia
            resultado_busca = buscar_fontes(frase)

            # Comparar a afirmação com as fontes
            resultado_comparacao = comparar_com_fontes(
                frase,
                resultado_busca["fontes"]
            )
            
            resumo = resumir_evidencias(resultado_comparacao)
            resultado_geral = determinar_resultado_geral(resumo)
            fontes_relevantes = filtrar_fontes_com_evidencias(
            resultado_comparacao
            )

            # A IA lê os trechos e decide; se não estiver disponível, vale a comparação de números
            evidencias = avaliar_com_ia(frase, resultado_busca["fontes"])
            metodo = "ia"

            if evidencias is None:
                evidencias = montar_evidencias(fontes_relevantes)
                metodo = "numerico"

            # Organizar os dados da afirmação
            afirmacao = {
                "id": len(afirmacoes) + 1,
                "texto": frase,
                "status_verificacao": "concluida",
                "fontes": resultado_busca["fontes"],
                "comparacoes": resultado_comparacao,
                "resumo_evidencias": resumo,
                "resultado_geral": resultado_geral,
                "fontes_relevantes": fontes_relevantes,
                "evidencias": evidencias,
                "metodo": metodo
            }

            afirmacoes.append(afirmacao)

    # 5. Retornar os resultados
    return {
        "status": "sucesso",
        "texto_analisado": texto,
        "afirmacoes": afirmacoes,
        "perguntas": perguntas,
        "quantidade_afirmacoes": len(afirmacoes),
        "quantidade_perguntas": len(perguntas)
    }
