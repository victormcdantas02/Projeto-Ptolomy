import buscador


def test_tira_palavras_ignoradas():
    assert buscador.preparar_termo_busca("O Brasil possui 26 estados.") == "brasil estados"


def test_gera_consultas_alternativas_por_assunto():
    consultas = buscador.gerar_consultas(
        "O Brasil possui 26 estados e um Distrito Federal."
    )
    assert "estados do brasil" in consultas
    assert "unidades federativas do brasil" in consultas
    assert len(consultas) <= buscador.MAX_CONSULTAS_WIKIPEDIA


def test_sem_termo_nao_busca():
    assert buscador.pesquisar_wikipedia("") == []


def test_retorna_fontes_deduplicadas_prioriza_contexto_e_adiciona_ibge(monkeypatch):
    artigo_longo = "Trecho contextual consultado. " * 35
    pesquisas = {
        "brasil estados distrito federal": [
            {"pageid": 1, "title": "Distrito Federal historico (1891-1960)", "index": 1, "extract": artigo_longo},
            {"pageid": 2, "title": "Distrito Federal (Brasil)", "index": 2, "extract": artigo_longo},
        ],
        "estados do brasil": [
            {"pageid": 3, "title": "Estados do Brasil", "index": 1, "extract": artigo_longo},
            {"pageid": 1, "title": "Distrito Federal historico (1891-1960)", "index": 2, "extract": artigo_longo},
        ],
        "unidades federativas do brasil": [
            {"pageid": 4, "title": "Unidades federativas do Brasil", "index": 1, "extract": ""},
            {"pageid": 3, "title": "Estados do Brasil", "index": 2, "extract": artigo_longo},
        ],
    }
    estados = [
        {"sigla": f"UF{i:02}", "nome": f"Estado {i}"}
        for i in range(26)
    ] + [{"sigla": "DF", "nome": "Distrito Federal"}]
    chamadas = []

    def requisicao_falsa(url, parametros):
        chamadas.append((url, parametros.copy()))
        if url == buscador.URL_IBGE_UFS:
            return estados
        if "pageids" in parametros:
            return {
                "query": {
                    "pages": {
                        "4": {"pageid": 4, "extract": artigo_longo},
                    }
                }
            }
        return {
            "query": {
                "pages": {
                    str(pagina["pageid"]): pagina
                    for pagina in pesquisas[parametros["gsrsearch"]]
                }
            }
        }

    monkeypatch.setattr(buscador, "_requisicao_json", requisicao_falsa)
    fontes = buscador.buscar_fontes(
        "O Brasil possui 26 estados e um Distrito Federal."
    )["fontes"]

    titulos = [fonte["titulo"] for fonte in fontes]
    assert titulos[0].startswith("Unidades da Federação do Brasil — IBGE")
    assert "Unidades federativas do Brasil" in titulos
    assert titulos.index("Unidades federativas do Brasil") < titulos.index(
        "Distrito Federal historico (1891-1960)"
    )
    assert len({fonte["url"] for fonte in fontes}) == len(fontes)
    assert max(len(fonte["descricao"]) for fonte in fontes) > 500
    assert len(chamadas) <= (
        buscador.MAX_CONSULTAS_WIKIPEDIA + 2
    )
    parametros_busca = [
        parametros for url, parametros in chamadas
        if url == buscador.URL_WIKIPEDIA and "gsrsearch" in parametros
    ]
    assert all(parametros["gsrlimit"] == buscador.MAX_RESULTADOS_POR_CONSULTA for parametros in parametros_busca)
    assert all(parametros["exchars"] == buscador.MAX_CARACTERES_EXCERTO for parametros in parametros_busca)
    assert all(parametros["exlimit"] == "max" and parametros["exintro"] == "1" for parametros in parametros_busca)


def test_cache_evita_requisicoes_repetidas(monkeypatch):
    buscador._CACHE.clear()
    chamadas = []

    class Resposta:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def get_falso(*args, **kwargs):
        chamadas.append((args, kwargs))
        return Resposta()

    monkeypatch.setattr(buscador.requests, "get", get_falso)
    primeira = buscador._requisicao_json("https://example.test/api", {"q": "x"})
    segunda = buscador._requisicao_json("https://example.test/api", {"q": "x"})

    assert primeira == segunda == {"ok": True}
    assert len(chamadas) == 1
    buscador._CACHE.clear()


def test_retry_controlado_para_limite_de_requisicoes(monkeypatch):
    buscador._CACHE.clear()
    monkeypatch.setattr(buscador, "_ULTIMA_REQUISICAO", 0.0)
    monkeypatch.setattr(buscador.time, "sleep", lambda segundos: None)
    chamadas = []

    class Resposta:
        def __init__(self, status_code):
            self.status_code = status_code
            self.headers = {"Retry-After": "1"}

        def raise_for_status(self):
            if self.status_code == 429:
                raise RuntimeError("limite de teste")

        def json(self):
            return {"ok": True}

    def get_falso(*args, **kwargs):
        chamadas.append(True)
        return Resposta(429 if len(chamadas) == 1 else 200)

    monkeypatch.setattr(buscador.requests, "get", get_falso)
    monkeypatch.setattr(buscador.time, "monotonic", lambda: 10.0)

    assert buscador._requisicao_json("https://example.test/retry", {}) == {"ok": True}
    assert len(chamadas) == 2
    buscador._CACHE.clear()


def test_busca_wikidata_usa_declaracao_preferida_de_capital(monkeypatch):
    def requisicao_falsa(url, parametros):
        assert url == buscador.URL_WIKIDATA
        if parametros["action"] == "wbsearchentities":
            return {
                "search": [{
                    "id": "Q155",
                    "label": "Brazil",
                    "match": {"text": "Brasil"},
                }]
            }
        if parametros["ids"] == "Q155" and "claims" in parametros["props"]:
            return {
                "entities": {
                    "Q155": {
                        "labels": {"pt": {"value": "Brasil"}},
                        "claims": {
                            "P36": [
                                {
                                    "rank": "normal",
                                    "mainsnak": {"datavalue": {"type": "wikibase-entityid", "value": {"id": "Q8678"}}},
                                    "qualifiers": {"P582": [{"datavalue": {"value": {"time": "+1960-04-22T00:00:00Z"}}}]},
                                },
                                {
                                    "rank": "preferred",
                                    "mainsnak": {"datavalue": {"type": "wikibase-entityid", "value": {"id": "Q2844"}}},
                                },
                            ]
                        },
                    }
                }
            }
        assert parametros["ids"] == "Q155|Q2844"
        return {
            "entities": {
                "Q2844": {"labels": {"pt": {"value": "Brasília"}}},
            }
        }

    monkeypatch.setattr(buscador, "_requisicao_json", requisicao_falsa)
    fonte = buscador._buscar_capital_wikidata("A capital do Brasil é Recife.")

    assert fonte == {
        "titulo": "Brasil — Wikidata",
        "descricao": "Registro estruturado do Wikidata (propriedade P36): A capital do Brasil é Brasília.",
        "url": "https://www.wikidata.org/wiki/Q155",
        "tipo_fonte": "base_dados_aberta",
    }


def test_usa_wikidata_quando_wikipedia_limita_requisicoes(monkeypatch):
    fonte = {
        "titulo": "Brasil — Wikidata",
        "descricao": "Registro estruturado do Wikidata (propriedade P36): A capital do Brasil é Brasília.",
        "url": "https://www.wikidata.org/wiki/Q155",
        "tipo_fonte": "base_dados_aberta",
    }
    monkeypatch.setattr(buscador, "_buscar_capital_wikidata", lambda afirmacao: fonte)

    def wikipedia_limitada(consulta):
        raise buscador.requests.HTTPError("limite de requisições")

    monkeypatch.setattr(buscador, "pesquisar_wikipedia", wikipedia_limitada)
    resultado = buscador.buscar_fontes("A capital do Brasil é Recife.")

    assert resultado["fontes"] == [fonte]
