from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from verificador import analisar_texto

app = FastAPI()

# Libera o index.html (aberto no navegador) para chamar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class TextoIA(BaseModel):
    texto: str

@app.get("/")
def inicio():
    return {"mensagem": "API funcionando!"}

@app.post("/verificar")
def verificar(dados: TextoIA):

    texto_recebido = dados.texto

    resultado = analisar_texto(texto_recebido)

    return resultado