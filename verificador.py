import re
from buscador import buscar_fontes

def analisar_texto(texto):

    if not texto.strip():
        return {
            "status": "erro",
            "mensagem": "O texto não pode estar vazio."
        }

    frases = re.findall(r"[^.!?]+[.!?]?", texto)

    afirmacoes = []
    perguntas = []

    for frase in frases:
        frase = frase.strip()

        if not frase:
            continue

        if frase.endswith("?"):
            perguntas.append(frase)
            
        else:
            resultado_busca = buscar_fontes(frase)

            afirmacao = {
                "id": len(afirmacoes) + 1,
                "texto": frase,
                "status_verificacao": "pendente",
                "fontes": resultado_busca["fontes"]
            }
            
            afirmacoes.append(afirmacao)

    return {
        "status": "sucesso",
        "texto_analisado": texto,
        "afirmacoes": afirmacoes,
        "perguntas": perguntas,
        "quantidade_afirmacoes": len(afirmacoes),
        "quantidade_perguntas": len(perguntas)
    }
    
