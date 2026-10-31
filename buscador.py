import requests


# 1. Busca simulada (temporária)
def buscar_fontes(afirmacao):

    artigos = pesquisar_wikipedia(afirmacao)

    fontes = []

    for artigo in artigos:

        resumo = obter_resumo_wikipedia(
            artigo["pagina_id"]
        )

        fonte = {
         "titulo": resumo["titulo"],
         "descricao": resumo["resumo"][:500],
         "url": (
          "https://pt.wikipedia.org/?curid="
         + str(artigo["pagina_id"])
         )
         }


        fontes.append(fonte)

    return {
        "afirmacao": afirmacao,
        "fontes": fontes
    }



# 2. Pesquisar artigos na Wikipédia
def pesquisar_wikipedia(termo):

    url = "https://pt.wikipedia.org/w/api.php"

    parametros = {
        "action": "query",
        "list": "search",
        "srsearch": termo,
        "format": "json",
        "srlimit": 3
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers={
            "User-Agent": "VerificadorIAAcademico/0.1 (projeto educacional)"
        },
        timeout=10
    )

    resposta.raise_for_status()

    dados = resposta.json()

    resultados = []

    for artigo in dados["query"]["search"]:
        resultados.append({
            "titulo": artigo["title"],
            "pagina_id": artigo["pageid"]
        })

    return resultados


# 3. Recuperar resumo de um artigo
def obter_resumo_wikipedia(pagina_id):

    url = "https://pt.wikipedia.org/w/api.php"

    parametros = {
        "action": "query",
        "prop": "extracts",
        "pageids": pagina_id,
        "exintro": True,
        "explaintext": True,
        "format": "json"
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers={
            "User-Agent": "VerificadorIAAcademico/0.1 (projeto educacional)"
        },
        timeout=10
    )

    resposta.raise_for_status()

    dados = resposta.json()

    pagina = dados["query"]["pages"][str(pagina_id)]

    return {
        "titulo": pagina.get("title", ""),
        "resumo": pagina.get("extract", "")
    }


# 4. Testar as funções
if __name__ == "__main__":

    artigos = pesquisar_wikipedia("Estados do Brasil")

    print("ARTIGOS ENCONTRADOS:")
    print(artigos)

    if artigos:

        primeiro_artigo = artigos[0]

        resumo = obter_resumo_wikipedia(
            primeiro_artigo["pagina_id"]
        )

        print("\nRESUMO DO PRIMEIRO ARTIGO:")
        print(resumo)
