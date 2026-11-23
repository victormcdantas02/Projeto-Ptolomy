import json
import os

import anthropic
from dotenv import load_dotenv

# Lê o arquivo .env (se existir), onde fica a ANTHROPIC_API_KEY
load_dotenv()

MODELO = "claude-opus-5-5"

# Formato da resposta: a API garante que a IA devolve exatamente este JSON
FORMATO = {
    "type": "object",
    "properties": {
        "avaliacoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer"},
                    "posicao": {"type": "string", "enum": ["confirma", "contradiz", "neutra"]},
                    "trecho": {"type": "string"},
                    "justificativa": {"type": "string"}
                },
                "required": ["indice", "posicao", "trecho", "justificativa"],
                "additionalProperties": False
            }
        }
    },
    "required": ["avaliacoes"],
    "additionalProperties": False
}

INSTRUCOES = """Você é o verificador de fatos do Ptolomy.AI, um projeto acadêmico de checagem de fatos.

Você recebe uma afirmação e trechos de artigos da Wikipédia em português, numerados. Para cada fonte, decida a posição dela em relação à afirmação, usando só o texto daquela fonte:
- "confirma": o texto sustenta a afirmação.
- "contradiz": o texto diz algo incompatível com a afirmação.
- "neutra": o texto não fala do assunto ou não basta para decidir.

Julgue pelo que o texto diz, não pelo seu conhecimento próprio: se a fonte não trata do que a afirmação diz, ela é neutra, mesmo que você saiba a resposta. Isso mantém o resultado ligado às fontes que o site mostra.

Em "trecho", copie do texto da fonte a frase que sustenta a sua decisão, sem alterar; para "neutra", deixe vazio. Em "justificativa", explique em uma frase curta, em português, por que a fonte confirma, contradiz ou é neutra. Devolva uma avaliação para cada fonte recebida, com o mesmo número."""


def ia_disponivel():
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def montar_pedido(afirmacao, fontes):

    partes = [f"<afirmacao>{afirmacao}</afirmacao>"]

    for indice, fonte in enumerate(fontes):
        partes.append(
            f'<fonte indice="{indice}" titulo="{fonte["titulo"]}">\n{fonte["descricao"]}\n</fonte>'
        )

    return "\n\n".join(partes)


def avaliar_fontes(afirmacao, fontes):
    """Devolve uma lista de avaliações (uma por fonte) ou None se a IA recusar."""

    if not fontes:
        return []

    cliente = anthropic.Anthropic(timeout=60.0)

    resposta = cliente.beta.messages.create(
        model=MODELO,
        max_tokens=8000,
        # Se a IA recusar por engano, a própria API tenta de novo com outro modelo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": FORMATO}
        },
        system=INSTRUCOES,
        messages=[{"role": "user", "content": montar_pedido(afirmacao, fontes)}]
    )

    if resposta.stop_reason == "refusal":
        return None

    texto = next(bloco.text for bloco in resposta.content if bloco.type == "text")
    avaliacoes = json.loads(texto)["avaliacoes"]

    # Guarda só avaliações que apontam para uma fonte que existe
    validas = []

    for avaliacao in avaliacoes:
        if 0 <= avaliacao["indice"] < len(fontes):
            validas.append(avaliacao)

    return validas
