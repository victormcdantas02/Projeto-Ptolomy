import re
import requests


# Configuração da Wikipédia
URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "ProjetoPtolomy/1.0 (projeto academico)"
}


# PASSO 1 - Preparar o termo de busca
def preparar_termo_busca(afirmacao):

    palavras_ignoradas = {
        "o", "a", "os", "as",
        "um", "uma", "de", "do", "da",
        "dos", "das", "em", "no", "na",
        "e", "possui", "tem", "é"
    }

    palavras = re.findall(
        r"[a-zA-ZÀ-ÿ]+",
        afirmacao.lower()
    )

    palavras_chave = []

    for palavra in palavras:
        if palavra not in palavras_ignoradas:
            palavras_chave.append(palavra)

    return " ".join(palavras_chave)


# PASSO 2 - Pesquisar artigos na Wikipédia
def pesquisar_wikipedia(termo):

    parametros = {
        "action": "query",
        "list": "search",
        "srsearch": termo,
        "srlimit": 3,
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

    return dados["query"]["search"]


# PASSO 3 - Obter o resumo de um artigo
def obter_resumo_wikipedia(pagina_id):

    parametros = {
        "action": "query",
        "prop": "extracts",
        "pageids": pagina_id,
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

    pagina = dados["query"]["pages"][str(pagina_id)]

    return pagina.get("extract", "")[:500]


# PASSO 4 - Buscar fontes para uma afirmação
def buscar_fontes(afirmacao):

    fontes = []

    # Por enquanto, mantemos a busca original.
    # A nova função será integrada no próximo passo.
    termo_busca = preparar_termo_busca(afirmacao)
 
    resultados = pesquisar_wikipedia(termo_busca)

    for resultado in resultados:

        pagina_id = resultado["pageid"]

        resumo = obter_resumo_wikipedia(pagina_id)

        fonte = {
            "titulo": resultado["title"],
            "descricao": resumo,
            "url": f"https://pt.wikipedia.org/?curid={pagina_id}"
        }

        fontes.append(fonte)

    return {
        "afirmacao": afirmacao,
        "fontes": fontes
    }


# PASSO 5 - Testar a nova função
if __name__ == "__main__":

    afirmacao = "O Brasil possui 30 estados."

    termo = preparar_termo_busca(afirmacao)

    print("Termo de busca:", termo)
