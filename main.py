import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from verificador import analisar_texto
from banco import (
    STATUS_VALIDOS,
    CONCLUSOES_USUARIO_VALIDAS,
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
def cadastrar_analise(dados: dict):

    texto = str(dados.get("texto", ""))
    ia_origem = str(dados.get("ia_origem", ""))

    validar_texto(texto)

    if ia_origem == "" or len(ia_origem) > 40:
        raise HTTPException(status_code=422, detail="Informe qual IA gerou o texto")

    novo_id = salvar_analise(
        str(dados.get("usuario_id", "")),
        texto,
        ia_origem,
        dados.get("resultado", {}),
        dados.get("fontes", [])
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
def editar(analise_id: int, dados: dict):

    status_validacao = dados.get("status_validacao", "")
    observacao = str(dados.get("observacao", ""))
    conclusao_usuario = dados.get("conclusao_usuario")
    fontes_consultadas = dados.get("fontes_consultadas")

    if status_validacao not in STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail="Status inválido")

    if len(observacao) > 500:
        raise HTTPException(status_code=422, detail="A observação pode ter no máximo 500 caracteres")

    if conclusao_usuario is not None and conclusao_usuario not in CONCLUSOES_USUARIO_VALIDAS:
        raise HTTPException(status_code=400, detail="Conclusão do usuário inválida")

    if fontes_consultadas is not None and (
        not isinstance(fontes_consultadas, list)
        or len(fontes_consultadas) > 20
        or any(not isinstance(fonte, str) or len(fonte) > 100 for fonte in fontes_consultadas)
    ):
        raise HTTPException(status_code=422, detail="Lista de fontes consultadas inválida")

    alterou = atualizar_analise(
        analise_id,
        status_validacao,
        observacao,
        conclusao_usuario,
        fontes_consultadas,
    )

    if not alterou:
        raise HTTPException(status_code=404, detail="Análise não encontrada")

    return buscar_analise(analise_id)

@app.delete("/analises/{analise_id}", status_code=204)
def excluir(analise_id: int):

    if not excluir_analise(analise_id):
        raise HTTPException(status_code=404, detail="Análise não encontrada")
