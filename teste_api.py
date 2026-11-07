import requests

def consultar_cep(cep):

    url = f"https://viacep.com.br/ws/{cep}/json/"

    resposta = requests.get(url, timeout=10)

    if resposta.status_code == 200:

        dados = resposta.json()

        return {
            "cep": dados["cep"],
            "cidade": dados["localidade"],
            "estado": dados["uf"]
        }

    else:
        return {
            "erro": "Não foi possível consultar o CEP"
        }


resultado = consultar_cep("01001000")

print(resultado)
