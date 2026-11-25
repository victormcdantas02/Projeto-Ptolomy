import json
import logging

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

logger = logging.getLogger(__name__)


def _categoria_falha_ia(erro):
    if isinstance(erro, anthropic.APITimeoutError):
        return "timeout"
    if isinstance(erro, anthropic.AuthenticationError):
        return "erro_autenticacao"
    if isinstance(erro, anthropic.RateLimitError):
        corpo = getattr(erro, "body", None)
        tipo = ""
        if isinstance(corpo, dict):
            tipo = str((corpo.get("error") or {}).get("type", "")).casefold()
        return "creditos_insuficientes" if "billing" in tipo or "credit" in tipo else "limite_requisicoes"
    if isinstance(erro, anthropic.APIStatusError):
        corpo = getattr(erro, "body", None)
        tipo = ""
        if isinstance(corpo, dict):
            tipo = str((corpo.get("error") or {}).get("type", "")).casefold()
        if erro.status_code == 402 or "billing" in tipo or "credit" in tipo:
            return "creditos_insuficientes"
    if isinstance(erro, anthropic.APIConnectionError):
        return "falha_conexao"
    if isinstance(erro, anthropic.APIError):
        return "erro_api"
    return "falha_processamento"


# Traduz o resultado da comparação para a posição que o site mostra
def montar_evidencias(fontes_relevantes):

    evidencias = []

    for fonte in fontes_relevantes:

        trechos_por_posicao = {}
        for comparacao in fonte["comparacoes"]:
            posicao = {
                "compativel": "confirma",
                "divergente": "contradiz",
            }.get(comparacao["classificacao"], "neutra")
            trechos_por_posicao.setdefault(posicao, comparacao["frase"])
        if len(trechos_por_posicao) > 1:
            trechos_por_posicao.pop("neutra", None)
        for posicao, trecho in trechos_por_posicao.items():
            evidencias.append({
                "titulo": fonte["titulo"],
                "url": fonte["url"],
                "tipo_fonte": fonte.get("tipo_fonte", "outra"),
                "posicao": posicao,
                "trecho": trecho,
            })

    return evidencias


# Monta as evidências a partir do que a IA decidiu sobre cada fonte
def montar_evidencias_ia(avaliacoes, fontes):

    evidencias = []

    for avaliacao in avaliacoes:

        fonte = fontes[avaliacao["indice"]]

        # Sem trecho (fonte neutra), mostra o começo do resumo do artigo
        trecho = avaliacao["trecho"].strip()
        posicao = avaliacao["posicao"]
        justificativa = avaliacao["justificativa"]

        trecho_valido = bool(trecho and trecho in fonte["descricao"])
        if not trecho_valido and (trecho or posicao != "neutra"):
            trecho = fonte["descricao"][:200]
            posicao = "neutra"
            justificativa = "O trecho atribuído à fonte não pôde ser confirmado no conteúdo consultado."
        elif trecho == "":
            trecho = fonte["descricao"][:200]

        evidencias.append({
            "titulo": fonte["titulo"],
            "url": fonte["url"],
            "tipo_fonte": fonte.get("tipo_fonte", "enciclopedia"),
            "posicao": posicao,
            "trecho": trecho,
            "justificativa": justificativa,
            "comparada": trecho_valido,
        })

    return evidencias


# Pede para a IA relacionar afirmação e fontes, sem estimar probabilidades.
def avaliar_com_ia(frase, fontes):

    if not ia.ia_disponivel():
        logger.info("Claude indisponível: ANTHROPIC_API_KEY ausente; usando comparação local.")
        return None, "chave_ausente"

    try:
        avaliacoes = ia.avaliar_fontes(frase, fontes)
        if avaliacoes is None:
            logger.warning("Claude recusou ou não retornou avaliações; usando comparação local.")
            return None, "resposta_indisponivel"
        return montar_evidencias_ia(avaliacoes, fontes), "disponivel"
    except anthropic.APIError as erro:
        categoria = _categoria_falha_ia(erro)
        logger.warning(
            "Análise por Claude indisponível (%s, HTTP %s); usando comparação local.",
            categoria,
            getattr(erro, "status_code", None),
        )
        return None, categoria
    except (json.JSONDecodeError, StopIteration, KeyError, TypeError, IndexError) as erro:
        logger.warning(
            "Falha ao processar a resposta de Claude (%s); usando comparação local.",
            type(erro).__name__,
        )
        return None, "falha_processamento"


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
            urls_relevantes = {fonte["url"] for fonte in fontes_relevantes}
            evidencias, diagnostico_ia = avaliar_com_ia(
                frase,
                [fonte for fonte in resultado_busca["fontes"] if fonte["url"] in urls_relevantes],
            )
            metodo = "ia" if evidencias is not None else "numerico"

            if evidencias is None:
                evidencias = montar_evidencias(fontes_relevantes)

            urls_avaliadas = {evidencia["url"] for evidencia in evidencias}
            for fonte in resultado_busca["fontes"]:
                if fonte["url"] not in urls_avaliadas:
                    evidencias.append({
                        "titulo": fonte["titulo"],
                        "url": fonte["url"],
                        "tipo_fonte": fonte.get("tipo_fonte", "enciclopedia"),
                        "posicao": "neutra",
                        "comparada": False,
                        "trecho": fonte["descricao"][:200],
                        "justificativa": (
                            "Fonte consultada, mas sem trecho suficiente para classificar "
                            "a afirmação."
                        ),
                    })

            confirmam = sum(e["posicao"] == "confirma" for e in evidencias)
            contradizem = sum(e["posicao"] == "contradiz" for e in evidencias)
            # Organizar os dados da afirmação
            afirmacao = {
                "id": len(afirmacoes) + 1,
                "texto": frase,
                "status_verificacao": "concluida",
                "fontes": resultado_busca["fontes"],
                "comparacoes": resultado_comparacao,
                "resumo_evidencias": resumo,
                "resultado_geral": resultado_geral,
                "status_evidencias": (
                    "evidencias_insuficientes"
                    if confirmam + contradizem == 0
                    else "evidencias_mistas"
                    if confirmam and contradizem
                    else "evidencias_disponiveis"
                ),
                "fontes_relevantes": fontes_relevantes,
                "evidencias": evidencias,
                "metodo": metodo,
                "diagnostico_ia": diagnostico_ia,
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
