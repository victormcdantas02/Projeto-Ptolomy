import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from verificador import analisar_texto
from banco import criar_tabela

app = FastAPI()

# Garante que a tabela de análises existe
criar_tabela()

# Libera o index.html (aberto no navegador) para chamar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class TextoIA(BaseModel):
    # Texto muito curto não dá contexto para buscar
    texto: str = Field(min_length=15, max_length=2000)

@app.get("/")
def inicio():
    return {"mensagem": "API funcionando!"}

@app.post("/verificar")
def verificar(dados: TextoIA):

    texto_recebido = dados.texto

    try:
        resultado = analisar_texto(texto_recebido)
    except requests.RequestException:
        # Wikipédia fora do ar ou sem internet
        raise HTTPException(status_code=503, detail="Serviço de fontes indisponível")

    return resultado
