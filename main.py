import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from verificador import analisar_texto
from banco import (
    STATUS_VALIDOS,
    criar_tabela,
    salvar_analise,
    buscar_analise,
    listar_analises,
    atualizar_analise,
    excluir_analise
)

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

# Confere o tamanho do texto: muito curto não dá contexto para buscar
def validar_texto(texto):
    if len(texto) < 15 or len(texto) > 2000:
        raise HTTPException(status_code=422, detail="O texto precisa ter entre 15 e 2000 caracteres")

# Dados que o site manda para salvar uma análise
class NovaAnalise(BaseModel):
    usuario_id: str = ""
    texto: str = Field(min_length=15, max_length=2000)
    ia_origem: str = Field(min_length=1, max_length=40)
    resultado: dict
    fontes: list

# Dados que podem ser editados depois
class EdicaoAnalise(BaseModel):
    status_validacao: str
    observacao: str = Field(default="", max_length=500)

@app.get("/")
def inicio():
    return {"mensagem": "API funcionando!"}

@app.post("/verificar")
def verificar(dados: dict):

    # O site manda um JSON como {"texto": "..."}, que chega como dicionário
    texto_recebido = str(dados.get("texto", ""))
    validar_texto(texto_recebido)

    try:
        resultado = analisar_texto(texto_recebido)
    except requests.RequestException:
        # Wikipédia fora do ar ou sem internet
        raise HTTPException(status_code=503, detail="Serviço de fontes indisponível")

    return resultado

# CRUD de análises ----------------------------------------------

@app.post("/analises", status_code=201)
def cadastrar_analise(dados: NovaAnalise):

    novo_id = salvar_analise(
        dados.usuario_id,
        dados.texto,
        dados.ia_origem,
        dados.resultado,
        dados.fontes
    )

    return buscar_analise(novo_id)

@app.get("/analises")
def listar(usuario_id: str = ""):
    return listar_analises(usuario_id)

@app.get("/analises/{analise_id}")
def detalhar(analise_id: int):

    analise = buscar_analise(analise_id)

    if analise is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    return analise

@app.put("/analises/{analise_id}")
def editar(analise_id: int, dados: EdicaoAnalise):

    if dados.status_validacao not in STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail="Status inválido")

    alterou = atualizar_analise(analise_id, dados.status_validacao, dados.observacao)

    if not alterou:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    return buscar_analise(analise_id)

@app.delete("/analises/{analise_id}", status_code=204)
def excluir(analise_id: int):

    if not excluir_analise(analise_id):
        raise HTTPException(status_code=404, detail="Análise não encontrada")
