import re

from buscador import buscar_fontes
from comparador import (
    comparar_com_fontes,
    resumir_evidencias,
    determinar_resultado_geral,
    filtrar_fontes_com_evidencias
)

# Resultado da comparação -> posição que o site mostra
POSICOES = {
    "compatibilidade_numerica": "confirma",
    "divergencia_numerica": "contradiz"
}


def montar_evidencias(fontes_relevantes):

    evidencias = []

    for fonte in fontes_relevantes:

        # Resume as frases desta fonte e vê se ela confirma ou contradiz
        resumo = resumir_evidencias([fonte])
        resultado = determinar_resultado_geral(resumo)

        evidencias.append({
            "titulo": fonte["titulo"],
            "url": fonte["url"],
            "posicao": POSICOES.get(resultado, "neutra"),
            "trecho": fonte["comparacoes"][0]["frase"]
        })

    return evidencias


def analisar_texto(texto):

    afirmacoes = []
    perguntas = []

    # 1. Separar o texto em frases
    # (corta depois de . ! ? seguido de espaço, para não quebrar "5.571")
    frases = re.split(r"(?<=[.!?])\s+", texto)

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

            # Organizar os dados da afirmação
            afirmacao = {
                "id": len(afirmacoes) + 1,
                "texto": frase,
                "status_verificacao": "concluida",
                "fontes": resultado_busca["fontes"],
                "comparacoes": resultado_comparacao,
                "resumo_evidencias": resumo,
                "resultado_geral": resultado_geral,
                "fontes_relevantes": fontes_relevantes
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
