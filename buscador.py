import copy
import logging
import re
import time
import threading

import requests

from comparador import extrair_entidade_capital, extrair_valor_capital, normalizar


URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"
URL_IBGE_UFS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_WIKIDATA = "https://www.wikidata.org/w/api.php"
HEADERS = {
    "User-Agent": "ProjetoPtolomy/1.0 (projeto academico; contato: projeto escolar)"
}

MAX_CONSULTAS_WIKIPEDIA = 3
MAX_RESULTADOS_POR_CONSULTA = 8
MAX_EXTRATOS_POR_LOTE = 20
MAX_FONTES = 6
MAX_CARACTERES_EXCERTO = 2500
TEMPO_CACHE_SEGUNDOS = 600
INTERVALO_REQUISICOES_SEGUNDOS = 1.0
MAX_TENTATIVAS_REQUISICAO = 2
MAX_ESPERA_RETRY_SEGUNDOS = 5.0
MAX_ITENS_CACHE = 256

_PALAVRAS_DE_CONSULTA_IGNORADAS = {
    "afirma", "afirmacao", "informacao", "segundo", "possui", "possuem",
    "tem", "têm", "e", "é", "sao", "ser", "um", "uma", "do", "da", "dos",
    "das", "de", "no", "na", "nos", "nas", "o", "a", "os", "as", "por",
    "com", "para", "em", "que", "qual", "como",
}
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_REQUEST_LOCK = threading.Lock()
_ULTIMA_REQUISICAO = 0.0
_LOGGER = logging.getLogger(__name__)


def _tokens(texto):
    return [
        palavra for palavra in re.findall(r"[a-z0-9]+", normalizar(texto))
        if palavra not in _PALAVRAS_DE_CONSULTA_IGNORADAS
        and not palavra.isdecimal()
    ]


def preparar_termo_busca(afirmacao):
    return " ".join(dict.fromkeys(_tokens(afirmacao)))


def gerar_consultas(afirmacao):
    termos = _tokens(afirmacao)
    if not termos:
        return []

    termos_assunto = {
        "capital", "capitais", "satelite", "satelites", "natural", "naturais",
        "composicao", "composta", "composto", "hidrogenio", "oxigenio",
        "elemento", "elementos",
    }
    consultas = []
    principal = " ".join(dict.fromkeys(termos))
    consultas.append(principal)

    termos_estado = {"estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"}
    fala_de_estados = bool(set(termos) & termos_estado)
    entidade = next(
        (
            termo for termo in termos
            if termo not in termos_estado and termo not in termos_assunto
        ),
        "",
    )
    if fala_de_estados and entidade:
        consultas.extend([
            f"estados do {entidade}",
            f"unidades federativas do {entidade}",
        ])

    if {"capital", "capitais"} & set(termos) and entidade:
        consultas.append(f"capital do {entidade}")

    if {"satelite", "satelites"} & set(termos):
        consultas.append(f"satélites naturais da {entidade}" if entidade else "satélites naturais")

    if {"composicao", "composta", "composto", "hidrogenio", "oxigenio"} & set(termos):
        consultas.append("composição " + " ".join(termos))

    unicas = list(dict.fromkeys(" ".join(consulta.split()) for consulta in consultas if consulta.strip()))
    return unicas[:MAX_CONSULTAS_WIKIPEDIA]


def _requisicao_json(url, parametros):
    global _ULTIMA_REQUISICAO
    chave_cache = (url, tuple(sorted((str(k), str(v)) for k, v in parametros.items())))
    agora = time.monotonic()
    with _CACHE_LOCK:
        entrada = _CACHE.get(chave_cache)
        if entrada and agora - entrada[0] < TEMPO_CACHE_SEGUNDOS:
            return copy.deepcopy(entrada[1])

    with _REQUEST_LOCK:
        agora = time.monotonic()
        with _CACHE_LOCK:
            entrada = _CACHE.get(chave_cache)
            if entrada and agora - entrada[0] < TEMPO_CACHE_SEGUNDOS:
                return copy.deepcopy(entrada[1])

        espera = INTERVALO_REQUISICOES_SEGUNDOS - (agora - _ULTIMA_REQUISICAO)
        if espera > 0:
            time.sleep(espera)
        resposta = None
        for tentativa in range(MAX_TENTATIVAS_REQUISICAO):
            resposta = requests.get(
                url,
                params=parametros,
                headers=HEADERS,
                timeout=10,
            )
            _ULTIMA_REQUISICAO = time.monotonic()
            if resposta.status_code not in {429, 500, 502, 503, 504}:
                break
            if tentativa + 1 == MAX_TENTATIVAS_REQUISICAO:
                break
            try:
                espera_retry = float(resposta.headers.get("Retry-After", "1"))
            except (TypeError, ValueError):
                espera_retry = 1.0
            time.sleep(min(max(espera_retry, 1.0), MAX_ESPERA_RETRY_SEGUNDOS))
        if resposta is None:
            raise RuntimeError("A requisição externa não foi iniciada.")
        resposta.raise_for_status()
        dados = resposta.json()
        with _CACHE_LOCK:
            if len(_CACHE) >= MAX_ITENS_CACHE:
                expiradas = [
                    chave for chave, (criada, _) in _CACHE.items()
                    if time.monotonic() - criada >= TEMPO_CACHE_SEGUNDOS
                ]
                for chave in expiradas:
                    _CACHE.pop(chave, None)
                if len(_CACHE) >= MAX_ITENS_CACHE:
                    mais_antiga = min(_CACHE, key=lambda chave: _CACHE[chave][0])
                    _CACHE.pop(mais_antiga, None)
            _CACHE[chave_cache] = (time.monotonic(), copy.deepcopy(dados))
        return dados


def pesquisar_wikipedia(termo):
    if not termo:
        return []

    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": termo,
        "gsrnamespace": 0,
        "gsrlimit": MAX_RESULTADOS_POR_CONSULTA,
        "prop": "extracts",
        "exlimit": "max",
        "exintro": "1",
        "explaintext": "1",
        "exchars": MAX_CARACTERES_EXCERTO,
        "format": "json",
    }
    dados = _requisicao_json(URL_WIKIPEDIA, parametros)
    paginas = list(dados.get("query", {}).get("pages", {}).values())
    return sorted(paginas, key=lambda pagina: pagina.get("index", 999))


def _buscar_ufs_ibge(afirmacao):
    termos = set(_tokens(afirmacao))
    tema_estadual = bool(
        termos & {"estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"}
    )
    menciona_brasil = bool(termos & {"brasil", "brasileiro", "brasileira"})
    if not tema_estadual or not menciona_brasil:
        return None

    try:
        unidades = _requisicao_json(URL_IBGE_UFS, {})
        if not isinstance(unidades, list):
            raise ValueError("A API do IBGE retornou um formato inesperado.")
        unidades_validas = [
            unidade for unidade in unidades
            if isinstance(unidade, dict)
            and isinstance(unidade.get("sigla"), str)
            and isinstance(unidade.get("nome"), str)
        ]
        if not unidades_validas:
            raise ValueError("A API do IBGE não retornou unidades válidas.")

        distrito_federal = next(
            (unidade for unidade in unidades_validas if unidade["sigla"].upper() == "DF"),
            None,
        )
        estados = [
            unidade for unidade in unidades_validas
            if unidade["sigla"].upper() != "DF"
        ]
        descricao = (
            f"A API de Localidades do IBGE lista {len(unidades_validas)} unidades da "
            f"Federação do Brasil, incluindo {len(estados)} estados"
        )
        if distrito_federal:
            descricao += f" e o Distrito Federal ({distrito_federal['sigla']})"
        descricao += ". Unidades listadas: " + ", ".join(
            f"{unidade['nome']} ({unidade['sigla']})"
            for unidade in sorted(unidades_validas, key=lambda item: item["nome"])
        ) + "."
        return {
            "titulo": "Unidades da Federação do Brasil — IBGE (API de Localidades)",
            "descricao": descricao,
            "url": URL_IBGE_UFS,
            "tipo_fonte": "oficial",
        }
    except (requests.RequestException, ValueError, TypeError) as erro:
        _LOGGER.warning("Não foi possível consultar a API de Localidades do IBGE: %s", type(erro).__name__)
        return None


def _buscar_capital_wikidata(afirmacao):
    entidade = extrair_entidade_capital(afirmacao)
    if not entidade:
        return None

    try:
        busca = _requisicao_json(
            URL_WIKIDATA,
            {
                "action": "wbsearchentities",
                "search": entidade,
                "language": "pt",
                "format": "json",
                "limit": 10,
            },
        )
        entidade_normalizada = normalizar(entidade)
        resultado = next(
            (
                item for item in busca.get("search", [])
                if normalizar(item.get("match", {}).get("text", "")) == entidade_normalizada
                or normalizar(item.get("label", "")) == entidade_normalizada
                or any(
                    normalizar(alias) == entidade_normalizada
                    for alias in item.get("aliases", [])
                )
            ),
            None,
        )
        if not resultado or not resultado.get("id"):
            return None

        entidade_id = resultado["id"]
        dados_entidade = _requisicao_json(
            URL_WIKIDATA,
            {
                "action": "wbgetentities",
                "ids": entidade_id,
                "props": "labels|claims",
                "languages": "pt|en",
                "format": "json",
            },
        )
        entidade_dados = dados_entidade.get("entities", {}).get(entidade_id, {})
        declaracoes = entidade_dados.get("claims", {}).get("P36", [])
        preferidas = [declaracao for declaracao in declaracoes if declaracao.get("rank") == "preferred"]
        atuais = preferidas or [
            declaracao for declaracao in declaracoes
            if "P582" not in declaracao.get("qualifiers", {})
        ]
        capitais_ids = list(dict.fromkeys(
            declaracao.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for declaracao in atuais
            if declaracao.get("mainsnak", {}).get("datavalue", {}).get("type") == "wikibase-entityid"
        ))
        capitais_ids = [capital_id for capital_id in capitais_ids if capital_id]
        if not capitais_ids:
            return None

        rotulos = _requisicao_json(
            URL_WIKIDATA,
            {
                "action": "wbgetentities",
                "ids": "|".join([entidade_id, *capitais_ids]),
                "props": "labels",
                "languages": "pt|en",
                "format": "json",
            },
        ).get("entities", {})
        rotulo_entidade = (
            entidade_dados.get("labels", {}).get("pt", {}).get("value")
            or entidade_dados.get("labels", {}).get("en", {}).get("value")
            or resultado.get("label")
            or entidade
        )
        capitais = [
            rotulos.get(capital_id, {}).get("labels", {}).get("pt", {}).get("value")
            or rotulos.get(capital_id, {}).get("labels", {}).get("en", {}).get("value")
            for capital_id in capitais_ids
        ]
        capitais = [capital for capital in capitais if capital]
        if not capitais:
            return None

        descricao = "Registro estruturado do Wikidata (propriedade P36): " + " ".join(
            f"A capital do {rotulo_entidade} é {capital}."
            for capital in capitais
        )
        return {
            "titulo": f"{rotulo_entidade} — Wikidata",
            "descricao": descricao,
            "url": f"https://www.wikidata.org/wiki/{entidade_id}",
            "tipo_fonte": "base_dados_aberta",
        }
    except (requests.RequestException, ValueError, TypeError, KeyError) as erro:
        _LOGGER.warning("Não foi possível consultar a propriedade de capital no Wikidata: %s", type(erro).__name__)
        return None


def _relevancia(fonte, termos_afirmacao, consultas, tema_estados):
    titulo = normalizar(fonte.get("title", fonte.get("titulo", "")))
    descricao = normalizar(fonte.get("extract", fonte.get("descricao", "")))
    termos_titulo = set(re.findall(r"[a-z0-9]+", titulo))
    termos_texto = set(re.findall(r"[a-z0-9]+", descricao))
    pontos = 5 * len(termos_afirmacao & termos_titulo)
    pontos += 2 * len(termos_afirmacao & termos_texto)

    consulta = " ".join(consultas)
    if "unidades federativas do brasil" in consulta and "unidades federativas" in titulo:
        pontos += 15
    if tema_estados and "estados do brasil" in titulo:
        pontos += 15
    if tema_estados and "unidades federativas" in titulo and "brasil" in titulo:
        pontos += 20

    historico = bool(re.search(r"\b(?:18|19|20)\d{2}\s*[-–—]\s*(?:18|19|20)?\d{0,4}\b", titulo))
    if historico or any(termo in titulo for termo in ("historico", "historia do", "extinto")):
        pontos -= 25
    if "lista de" in titulo:
        pontos -= 15
    if tema_estados and titulo.startswith("estado do brasil"):
        pontos -= 20
    if tema_estados and "distrito federal" in titulo and "brasil" not in titulo:
        pontos -= 8
    return pontos


def _preencher_extratos_ausentes(paginas):
    sem_extrato = [
        str(pagina["pageid"])
        for pagina in paginas
        if pagina.get("pageid") is not None and not pagina.get("extract")
    ]
    if not sem_extrato:
        return

    dados = _requisicao_json(
        URL_WIKIPEDIA,
        {
            "action": "query",
            "pageids": "|".join(sem_extrato[:MAX_EXTRATOS_POR_LOTE]),
            "prop": "extracts",
            "exlimit": "max",
            "exintro": "1",
            "explaintext": "1",
            "exchars": MAX_CARACTERES_EXCERTO,
            "format": "json",
        },
    )
    por_id = dados.get("query", {}).get("pages", {})
    for pagina in paginas:
        extraida = por_id.get(str(pagina.get("pageid")), {})
        if extraida.get("extract"):
            pagina["extract"] = extraida["extract"]


def buscar_fontes(afirmacao):
    consultas = gerar_consultas(afirmacao)
    fontes_por_id = {}
    termos = set(_tokens(afirmacao))
    entidade_capital = extrair_entidade_capital(afirmacao)
    valor_capital = extrair_valor_capital(afirmacao)
    if entidade_capital and valor_capital:
        termos -= set(_tokens(valor_capital)) - set(_tokens(entidade_capital))
    fala_de_estados = bool(
        termos & {"estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"}
    )

    fontes_adicionais = [
        fonte for fonte in (
            _buscar_ufs_ibge(afirmacao),
            _buscar_capital_wikidata(afirmacao),
        )
        if fonte
    ]
    falha_wikipedia = None
    for consulta in consultas:
        try:
            resultados = pesquisar_wikipedia(consulta)
        except requests.RequestException as erro:
            falha_wikipedia = erro
            _LOGGER.warning(
                "A pesquisa na Wikipédia falhou (%s); serão usados outros provedores disponíveis.",
                type(erro).__name__,
            )
            break
        for resultado in resultados:
            pagina_id = resultado.get("pageid")
            if pagina_id is None:
                continue
            fonte = {
                **resultado,
                "titulo": resultado.get("title", ""),
                "descricao": resultado.get("extract", "")[:MAX_CARACTERES_EXCERTO],
                "url": f"https://pt.wikipedia.org/?curid={pagina_id}",
                "tipo_fonte": "enciclopedia",
            }
            fonte["_relevancia"] = _relevancia(
                fonte,
                termos,
                consultas,
                fala_de_estados,
            )
            fonte_anterior = fontes_por_id.get(pagina_id)
            if not fonte_anterior or fonte["_relevancia"] > fonte_anterior["_relevancia"]:
                fontes_por_id[pagina_id] = fonte

    candidatas = sorted(
        fontes_por_id.values(),
        key=lambda fonte: (
            -_relevancia(fonte, termos, consultas, fala_de_estados),
            fonte.get("index", 999),
            fonte["title"],
        ),
    )
    _preencher_extratos_ausentes(candidatas)
    candidatas = [fonte for fonte in candidatas if fonte.get("extract")]
    ordenadas = sorted(
        candidatas,
        key=lambda fonte: (-fonte["_relevancia"], fonte.get("index", 999), fonte["titulo"]),
    )
    fontes = []
    listas_adicionadas = 0
    for fonte in ordenadas:
        if normalizar(fonte["titulo"]).startswith("lista de"):
            if listas_adicionadas:
                continue
            listas_adicionadas += 1
        fontes.append(fonte)
    for fonte in fontes:
        fonte.pop("_relevancia", None)
        fonte.pop("index", None)

    limite_wikipedia = MAX_FONTES - len(fontes_adicionais)
    fontes = fontes[:limite_wikipedia]
    fontes = fontes_adicionais + fontes
    if not fontes and falha_wikipedia:
        raise falha_wikipedia
    return {"afirmacao": afirmacao, "fontes": fontes[:MAX_FONTES]}


if __name__ == "__main__":
    afirmacao = "O Brasil possui 30 estados."
    print("Consultas:", gerar_consultas(afirmacao))
    print("Fontes:", buscar_fontes(afirmacao)["fontes"])
