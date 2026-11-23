import requests

from comparador import extrair_palavras_chave


# Configuração da Wikipédia
URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "ProjetoPtolomy/1.0 (projeto academico)"
}


# PASSO 1 - Preparar o termo de busca
def preparar_termo_busca(afirmacao):

    # Usa a mesma lista de palavras ignoradas do comparador
    palavras_chave = extrair_palavras_chave(afirmacao)

    return " ".join(palavras_chave)


# PASSO 2 - Pesquisar artigos na Wikipédia (já com o resumo de cada um)
def pesquisar_wikipedia(termo):

    # Sem palavras-chave não tem o que buscar
    if not termo:
        return []

    # Uma requisição só: busca 3 artigos e traz o resumo deles
    # (antes eram 4 requisições e a Wikipédia bloqueava com erro 429)
    parametros = {
        "action": "query",
        "generator": "search",
        "gsrsearch": termo,
        "gsrlimit": 3,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json"
    }

    resposta = requests.get(
        URL_WIKIPEDIA,
        params=parametros,
        headers=HEADERS,
        timeout=10
    )

    resposta.raise_for_status()

    dados = resposta.json()

    # Se a Wikipédia não achou nada, não vem "query" na resposta
    if "query" not in dados:
        return []

    paginas = []

    for pagina in dados["query"]["pages"].values():
        paginas.append(pagina)

    # Ordena pela relevância da busca (campo "index": 1, 2, 3...)
    # usando o bubble sort: troca vizinhos fora de ordem
    for i in range(len(paginas)):
        for j in range(len(paginas) - 1 - i):
            if paginas[j]["index"] > paginas[j + 1]["index"]:
                paginas[j], paginas[j + 1] = paginas[j + 1], paginas[j]

    return paginas


# PASSO 3 - Buscar fontes para uma afirmação
def buscar_fontes(afirmacao):

    fontes = []

    termo_busca = preparar_termo_busca(afirmacao)

    resultados = pesquisar_wikipedia(termo_busca)

    for resultado in resultados:

        pagina_id = resultado["pageid"]

        fonte = {
            "titulo": resultado["title"],
            "descricao": resultado.get("extract", "")[:500],
            "url": f"https://pt.wikipedia.org/?curid={pagina_id}"
        }

        fontes.append(fonte)

    return {
        "afirmacao": afirmacao,
        "fontes": fontes
    }


# PASSO 4 - Testar a nova função
if __name__ == "__main__":

    afirmacao = "O Brasil possui 30 estados."

    termo = preparar_termo_busca(afirmacao)

    print("Termo de busca:", termo)
