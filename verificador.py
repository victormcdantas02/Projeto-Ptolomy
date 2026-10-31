import re

from buscador import buscar_fontes
from comparador import (
    comparar_com_fontes,
    resumir_evidencias,
    determinar_resultado_geral
)
from comparador import (
    comparar_com_fontes,
    resumir_evidencias,
    determinar_resultado_geral,
    filtrar_fontes_com_evidencias
)

def analisar_texto(texto):

    afirmacoes = []
    perguntas = []

    # 1. Separar o texto em frases
    frases = re.findall(r"[^.!?]+[.!?]?", texto)

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
                "status_verificacao": "pendente",
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
