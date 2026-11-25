import re
import unicodedata


_IGNORADAS = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "do", "da",
    "dos", "das", "em", "no", "na", "nos", "nas", "e", "ou", "que",
    "por", "para", "com", "se", "ao", "aos", "é", "ser", "sao", "sua",
    "seu", "suas", "seus", "tem", "têm", "possui", "possuem", "foi",
    "são", "era", "como", "mais", "menos", "cerca", "aproximadamente",
    "expoente",
}

_NUMEROS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezasseis": 16,
    "dezessete": 17, "dezassete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
    "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400,
    "quatrocentas": 400, "quinhentos": 500, "quinhentas": 500,
    "seiscentos": 600, "seiscentas": 600, "setecentos": 700,
    "setecentas": 700, "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900, "mil": 1000,
    "unico": 1, "unica": 1,
}

_ESTOPWORDS = _IGNORADAS | {
    "artigo", "artigos", "segundo", "consultado", "consultada", "expoente",
    "brasileiro", "brasileira",
}

_CAPITAL_DIRETA = re.compile(
    r"\bcapital\s+(?:do|da|de)\s+(.+?)\s+(?:e|eh)\s+(.+)$"
)
_CAPITAL_INVERSA = re.compile(
    r"^(.+?)\s+(?:e|eh)\s+(?:a\s+)?capital(?:\s+federal)?\s+"
    r"(?:do|da|de)\s+(.+)$"
)
_COMPOSICAO = re.compile(
    r"^(.+?)\s+(?:(?:e|eh|sao)\s+)?(?:composta|composto|compostas|"
    r"compostos|formada|formado|formadas|formados|constituida|"
    r"constituido|constituidas|constituidos)\s+por\s+(.+)$"
)
_EXPOENTES = str.maketrans({
    "⁰": " expoente ", "¹": " expoente ", "²": " expoente ",
    "³": " expoente ", "⁴": " expoente ", "⁵": " expoente ",
    "⁶": " expoente ", "⁷": " expoente ", "⁸": " expoente ",
    "⁹": " expoente ", "⁻": " expoente ", "⁺": " expoente ",
})


def normalizar(texto):
    texto = texto.translate(_EXPOENTES)
    texto = texto.casefold()
    texto = re.sub(r"[°º]\s*c\b", " grau celsius ", texto)
    texto = re.sub(r"[°º]\s*f\b", " grau fahrenheit ", texto)
    texto = re.sub(r"[°º]\s*k\b", " grau kelvin ", texto)
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in texto if not unicodedata.combining(letra))


def _separar_sentencas(texto):
    frases = []
    linhas = re.split(r"[\r\n]+", texto)

    for linha in linhas:
        if re.match(r"^\s*#{1,6}\s+", linha):
            continue
        linha = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", linha.strip())
        linha = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", linha)
        linha = re.sub(r"[*_`~]", "", linha)
        linha = re.sub(r"\s+\[\d+\]", "", linha)
        if not linha:
            continue

        atual = ""
        for indice, caractere in enumerate(linha):
            atual += caractere
            if caractere not in ".!?":
                continue
            if indice + 1 < len(linha) and linha[indice + 1].isdigit():
                continue
            if atual.strip():
                frases.append(atual.strip())
            atual = ""
        if atual.strip():
            frases.append(atual.strip())
    return frases


def separar_frases(texto):
    partes = []
    for frase in _separar_sentencas(texto):
        # Separa orações independentes sem dividir listas de componentes, como
        # "hidrogênio e oxigênio" ou "26 estados e um Distrito Federal".
        oracoes = re.split(
            r"\s+e\s+(?=(?:sua|seu|a capital|o total|a populacao|"
            r"o numero|a area|a temperatura)\b)",
            frase,
            flags=re.IGNORECASE,
        )
        sujeito = re.match(
            r"^(.+?)\s+(?:possui|possuem|tem|têm|conta|contam|"
            r"e|eh|representa|representam)\b",
            oracoes[0],
            flags=re.IGNORECASE,
        )
        for indice, oracao in enumerate(oracoes):
            if indice and sujeito and re.match(r"^(?:sua|seu)\s+capital\b", oracao, re.IGNORECASE):
                sujeito_nome = re.sub(
                    r"^(?:o|a|os|as)\s+",
                    "",
                    sujeito.group(1),
                    flags=re.IGNORECASE,
                )
                oracao = re.sub(
                    r"^(?:sua|seu)\s+capital",
                    f"capital do {sujeito_nome}",
                    oracao,
                    flags=re.IGNORECASE,
                )
            partes.append(oracao)
    return [frase.strip() for frase in partes if frase.strip()]


def separar_palavras(texto):
    return re.findall(r"\d+(?:[.,]\d+)*|[a-z]+", normalizar(texto))


def extrair_palavras_chave(afirmacao):
    return [
        palavra for palavra in separar_palavras(afirmacao)
        if palavra not in _IGNORADAS and palavra not in _NUMEROS and not palavra.isdecimal()
    ]


def _raiz(palavra):
    if len(palavra) > 5 and palavra.endswith("ais"):
        return palavra[:-3] + "al"
    if len(palavra) > 5 and palavra.endswith("eis"):
        return palavra[:-3] + "el"
    if len(palavra) > 4 and palavra.endswith("s"):
        palavra = palavra[:-1]
    return palavra


def _palavras_significativas(texto):
    return {
        _raiz(palavra)
        for palavra in separar_palavras(texto)
        if palavra not in _ESTOPWORDS and palavra not in _NUMEROS and not palavra.isdecimal()
    }


def _conceito_proximo(palavras, inicio):
    candidatos = []
    for posicao, palavra in enumerate(palavras[inicio:inicio + 5], start=inicio):
        if palavra.isdecimal():
            break
        if palavra in {"de", "do", "da", "dos", "das", "e", "a", "o", "um", "uma"}:
            continue
        palavra = _raiz(palavra)
        if palavra == "grau":
            seguinte = next(
                (
                    _raiz(termo) for termo in palavras[posicao + 1:posicao + 3]
                    if termo not in {"de", "do", "da"}
                ),
                "",
            )
            if seguinte in {"celsius", "fahrenheit", "kelvin"}:
                return (f"temperatura_{seguinte}",)
        unidades = {
            "celsius": "temperatura_celsius",
            "fahrenheit": "temperatura_fahrenheit",
            "kelvin": "temperatura_kelvin",
            "quilometro": "distancia_quilometro",
            "metro": "distancia_metro",
            "centimetro": "distancia_centimetro",
            "milimetro": "distancia_milimetro",
            "quilograma": "massa_quilograma",
            "grama": "massa_grama",
            "litro": "volume_litro",
            "mililitro": "volume_mililitro",
            "kg": "massa_quilograma",
            "km": "distancia_quilometro",
            "cm": "distancia_centimetro",
            "mm": "distancia_milimetro",
            "l": "volume_litro",
            "ml": "volume_mililitro",
        }
        if palavra in unidades:
            return (unidades[palavra],)
        if palavra == "unidade":
            seguinte = next(
                (
                    _raiz(termo) for termo in palavras[posicao + 1:posicao + 4]
                    if termo not in {"da", "de", "do", "das", "dos"}
                ),
                "",
            )
            if seguinte in {"federativa", "federacao"}:
                return ("unidade_federativa",)
        if palavra == "satelite":
            seguinte = next(
                (
                    _raiz(termo) for termo in palavras[posicao + 1:posicao + 3]
                    if termo not in {"da", "de", "do", "das", "dos"}
                ),
                "",
            )
            if seguinte == "natural":
                return ("satelite_natural",)
        candidatos.append(palavra)
        break
    return tuple(candidatos)


def _valor_numerico(palavra):
    if re.fullmatch(r"\d+(?:[.,]\d+)*", palavra):
        return int(palavra.replace(".", "").replace(",", ""))
    if palavra not in _NUMEROS:
        return None
    return _NUMEROS[palavra]


def _extrair_quantidades(texto):
    palavras = separar_palavras(texto)
    quantidades = []
    indice = 0

    while indice < len(palavras):
        palavra = palavras[indice]
        if palavra == "expoente" or (
            indice > 0 and palavras[indice - 1] == "expoente"
        ) or (
            indice + 1 < len(palavras) and palavras[indice + 1] == "expoente"
        ):
            indice += 1
            continue
        valor = _valor_numerico(palavra)
        if valor is None:
            indice += 1
            continue

        fim = indice + 1
        total = valor
        if palavra in _NUMEROS:
            while fim + 1 < len(palavras):
                conector = palavras[fim]
                proxima = _valor_numerico(palavras[fim + 1])
                if proxima is None or (conector != "e" and palavras[fim + 1] not in _NUMEROS):
                    break
                total += proxima
                fim += 2
        elif "." in palavra or "," in palavra:
            normalizado = palavra.replace(".", "").replace(",", "")
            if normalizado.isdecimal():
                total = int(normalizado)

        # Rankings e contagens regionais n?o descrevem o total de estados.
        conceito = _conceito_proximo(palavras, fim)
        if conceito == ("estado",):
            escopo = palavras[max(0, indice - 3):indice] + palavras[fim + 1:fim + 7]
            if set(escopo) & {
                "mais", "menos", "maior", "menor", "maiores", "menores", "principais", "regiao",
                "norte", "nordeste", "sul", "sudeste", "oeste",
            }:
                conceito = ()
        quantidades.append((total, conceito))
        indice = max(fim, indice + 1)

    return quantidades


def extrair_numero_associado(texto, palavra):
    alvo = _raiz(normalizar(palavra))
    for numero, conceito in _extrair_quantidades(texto):
        if alvo in conceito:
            return numero
    return None


def comparar_numeros_por_contexto(afirmacao, evidencia, titulo=""):
    quantidades_afirmacao = [
        (numero, conceito)
        for numero, conceito in _extrair_quantidades(afirmacao)
        if conceito
    ]
    quantidades_evidencia = [
        (numero, conceito)
        for numero, conceito in _extrair_quantidades(evidencia)
        if conceito
    ]
    termos_entidade = _palavras_significativas(afirmacao)
    termos_conceito = {
        subtermo
        for _, conceito in quantidades_afirmacao
        for termo in conceito
        for subtermo in termo.split("_")
    }
    termos_entidade -= termos_conceito | {
        "distrito", "federal", "unidade", "federativa", "uf",
        "natural", "grau", "temperatura",
    }
    termos_contexto = _palavras_significativas(evidencia) | _palavras_significativas(titulo)

    for numero_afirmacao, conceito_afirmacao in quantidades_afirmacao:
        for numero_evidencia, conceito_evidencia in quantidades_evidencia:
            if conceito_afirmacao != conceito_evidencia:
                continue
            if termos_entidade and not (termos_entidade & termos_contexto):
                continue
            return (
                "numeros_iguais"
                if numero_afirmacao == numero_evidencia
                else "numeros_diferentes"
            )
    return "inconclusivo"


def _extrair_relacao_capital(texto):
    normalizado = normalizar(texto).strip(" .!?;:")
    direta = _CAPITAL_DIRETA.search(normalizado)
    if direta:
        entidade, valor = direta.groups()
        return _palavras_significativas(entidade), _palavras_significativas(valor)

    inversa = _CAPITAL_INVERSA.search(normalizado)
    if inversa:
        valor, entidade = inversa.groups()
        return _palavras_significativas(entidade), _palavras_significativas(valor)
    return None


def extrair_entidade_capital(texto):
    normalizado = normalizar(texto).strip(" .!?;:")
    direta = _CAPITAL_DIRETA.search(normalizado)
    if direta:
        return re.sub(r"^(?:o|a|os|as)\s+", "", direta.group(1)).strip()

    inversa = _CAPITAL_INVERSA.search(normalizado)
    if inversa:
        return re.sub(r"^(?:o|a|os|as)\s+", "", inversa.group(2)).strip()
    return None


def extrair_valor_capital(texto):
    normalizado = normalizar(texto).strip(" .!?;:")
    direta = _CAPITAL_DIRETA.search(normalizado)
    if direta:
        return direta.group(2).strip()

    inversa = _CAPITAL_INVERSA.search(normalizado)
    if inversa:
        return inversa.group(1).strip()
    return None


def _extrair_relacao_composicao(texto):
    normalizado = normalizar(texto).strip(" .!?;:")
    resultado = _COMPOSICAO.search(normalizado)
    if not resultado:
        return None
    entidade, componentes = resultado.groups()
    entidade_palavras = _palavras_significativas(entidade)
    componentes_palavras = _palavras_significativas(componentes) - {
        "atomo", "molecula", "elemento", "quimico",
    }
    if not entidade_palavras or not componentes_palavras:
        return None
    return entidade_palavras, componentes_palavras


def _comparar_relacoes(afirmacao, evidencia, titulo=""):
    capital_afirmacao = _extrair_relacao_capital(afirmacao)
    capital_evidencia = _extrair_relacao_capital(evidencia)
    if capital_afirmacao and capital_evidencia:
        entidade_a, valor_a = capital_afirmacao
        entidade_e, valor_e = capital_evidencia
        if entidade_a & entidade_e:
            return "relacoes_iguais" if valor_a & valor_e else "relacoes_diferentes"

    composicao_afirmacao = _extrair_relacao_composicao(afirmacao)
    composicao_evidencia = _extrair_relacao_composicao(evidencia)
    if composicao_afirmacao and composicao_evidencia:
        entidade_a, partes_a = composicao_afirmacao
        entidade_e, partes_e = composicao_evidencia
        if not entidade_e:
            entidade_e = _palavras_significativas(titulo)
        if entidade_a & entidade_e and partes_a and partes_e:
            return "relacoes_iguais" if partes_a == partes_e else "relacoes_diferentes"
    return "inconclusivo"


def filtrar_frases_por_contexto(evidencia, palavras_chave, titulo="", afirmacao=None):
    termos_afirmacao = {
        _raiz(normalizar(palavra))
        for palavra in palavras_chave
        if normalizar(palavra) not in _ESTOPWORDS
    }
    if not termos_afirmacao:
        return []

    minimo_termos = max(2, (len(termos_afirmacao) + 1) // 2)
    relevantes = []
    for frase in _separar_sentencas(evidencia):
        termos_frase = _palavras_significativas(frase)
        intersecao = termos_afirmacao & termos_frase
        tem_conceito_numerico = (
            comparar_numeros_por_contexto(
                afirmacao or " ".join(palavras_chave),
                frase,
                titulo,
            )
            != "inconclusivo"
        )
        tem_relacao = _comparar_relacoes(
            afirmacao or " ".join(palavras_chave),
            frase,
            titulo,
        ) != "inconclusivo"
        if tem_conceito_numerico or tem_relacao or len(intersecao) >= minimo_termos:
            relevantes.append(frase.strip(" .!?"))
    return relevantes


def classificar_evidencia(resultado_numerico):
    if resultado_numerico in {"numeros_iguais", "relacoes_iguais"}:
        return "compativel"
    if resultado_numerico in {"numeros_diferentes", "relacoes_diferentes"}:
        return "divergente"
    return "inconclusiva"


def comparar_com_fontes(afirmacao, fontes):
    resultados = []
    palavras_chave = extrair_palavras_chave(afirmacao)

    for fonte in fontes:
        frases_relevantes = filtrar_frases_por_contexto(
            fonte.get("descricao", ""),
            palavras_chave,
            fonte.get("titulo", ""),
            afirmacao,
        )
        comparacoes = []

        for frase in frases_relevantes:
            comparacao = _comparar_relacoes(afirmacao, frase, fonte.get("titulo", ""))
            if comparacao == "inconclusivo":
                comparacao = comparar_numeros_por_contexto(
                    afirmacao,
                    frase,
                    fonte.get("titulo", ""),
                )
            comparacoes.append({
                "frase": frase,
                "resultado": comparacao,
                "classificacao": classificar_evidencia(comparacao),
            })

        resultados.append({
            "titulo": fonte["titulo"],
            "url": fonte.get("url"),
            "tipo_fonte": fonte.get("tipo_fonte", "outra"),
            "comparacoes": comparacoes,
        })
    return resultados


def resumir_evidencias(resultados):
    resumo = {"compativeis": 0, "divergentes": 0, "inconclusivas": 0}
    for fonte in resultados:
        for comparacao in fonte["comparacoes"]:
            if not comparacao["frase"].strip():
                continue
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
    if compativeis > 0:
        return "compatibilidade_numerica"
    if divergentes > 0:
        return "divergencia_numerica"
    return "inconclusivo"


def filtrar_fontes_com_evidencias(resultados):
    return [fonte for fonte in resultados if fonte["comparacoes"]]
