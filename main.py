from fastapi import FastAPI
from pydantic import BaseModel
from verificador import analisar_texto

app = FastAPI()

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
