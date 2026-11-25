import anthropic
import httpx
import pytest

import ia
import verificador

# Fonte de mentira, para o teste não depender da internet nem da IA de verdade
FONTE = {
    "titulo": "Brasil",
    "url": "https://pt.wikipedia.org/?curid=1",
    "descricao": "O Brasil, oficialmente República Federativa do Brasil, é um país da América do Sul."
}


def busca_falsa(afirmacao):
    return {"afirmacao": afirmacao, "fontes": [FONTE]}


def ia_ligada():
    return True


def ia_desligada():
    return False


# Respostas falsas da IA, uma para cada situação
def ia_que_confirma(afirmacao, fontes):
    return [{
        "indice": 0,
        "posicao": "confirma",
        "trecho": "O Brasil, oficialmente República Federativa do Brasil, é um país da América do Sul.",
        "justificativa": "O artigo diz que o Brasil é um país."
    }]


def ia_neutra(afirmacao, fontes):
    return [{"indice": 0, "posicao": "neutra", "trecho": "", "justificativa": "Não trata do assunto."}]


def ia_que_falha(afirmacao, fontes):
    raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


def ia_que_recusa(afirmacao, fontes):
    return None


# Coloca as funções falsas no lugar das de verdade, roda a análise e devolve as originais
def analisar_com(disponivel, avaliar, texto):

    busca_original = verificador.buscar_fontes
    disponivel_original = ia.ia_disponivel
    avaliar_original = ia.avaliar_fontes

    verificador.buscar_fontes = busca_falsa
    ia.ia_disponivel = disponivel
    ia.avaliar_fontes = avaliar

    resultado = verificador.analisar_texto(texto)

    verificador.buscar_fontes = busca_original
    ia.ia_disponivel = disponivel_original
    ia.avaliar_fontes = avaliar_original

    return resultado["afirmacoes"][0]


def test_ia_confirma_frase_sem_numero():
    afirmacao = analisar_com(ia_ligada, ia_que_confirma, "Brasil é um país.")
    assert afirmacao["metodo"] == "ia"
    assert afirmacao["evidencias"][0]["posicao"] == "confirma"
    assert afirmacao["evidencias"][0]["justificativa"] != ""


def test_sem_chave_usa_comparacao_numerica():
    afirmacao = analisar_com(ia_desligada, ia_que_confirma, "Brasil é um país.")
    assert afirmacao["metodo"] == "numerico"


def test_erro_da_ia_usa_comparacao_numerica():
    afirmacao = analisar_com(ia_ligada, ia_que_falha, "Brasil é um país.")
    assert afirmacao["metodo"] == "numerico"
    assert afirmacao["diagnostico_ia"] == "falha_conexao"


def test_recusa_da_ia_usa_comparacao_numerica():
    afirmacao = analisar_com(ia_ligada, ia_que_recusa, "Brasil é um país.")
    assert afirmacao["metodo"] == "numerico"
    assert afirmacao["diagnostico_ia"] == "resposta_indisponivel"


def test_fonte_neutra_mostra_comeco_do_artigo():
    evidencia = analisar_com(ia_ligada, ia_neutra, "Brasil é um país.")["evidencias"][0]
    assert evidencia["posicao"] == "neutra"
    assert evidencia["trecho"].startswith("O Brasil")


def test_pedido_tem_afirmacao_e_fontes():
    pedido = ia.montar_pedido("Brasil é um país.", [FONTE])
    assert "<afirmacao>Brasil é um país.</afirmacao>" in pedido
    assert 'indice="0"' in pedido
    assert "América do Sul" in pedido


def test_trecho_inventado_nao_e_apresentado_como_evidencia():
    fonte = {"titulo": "Brasil", "url": "https://exemplo.com", "descricao": "Texto real consultado."}
    evidencia = verificador.montar_evidencias_ia(
        [{
            "indice": 0,
            "posicao": "confirma",
            "trecho": "Trecho que não existe na fonte.",
            "justificativa": "A fonte confirma.",
        }],
        [fonte],
    )[0]

    assert evidencia["posicao"] == "neutra"
    assert evidencia["trecho"] == fonte["descricao"]


@pytest.mark.parametrize(
    ("classe", "atributos", "esperado"),
    [
        (anthropic.APITimeoutError, {"request": httpx.Request("POST", "https://api.anthropic.com")}, "timeout"),
        (anthropic.APIConnectionError, {"request": httpx.Request("POST", "https://api.anthropic.com")}, "falha_conexao"),
    ],
)
def test_diagnosticos_de_rede_ia(classe, atributos, esperado):
    assert verificador._categoria_falha_ia(classe(**atributos)) == esperado


def test_diagnosticos_de_autenticacao_e_creditos():
    resposta = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com"))
    erro_auth = anthropic.AuthenticationError("autenticação", response=resposta, body=None)
    erro_creditos = anthropic.APIStatusError(
        "cota",
        response=httpx.Response(402, request=httpx.Request("POST", "https://api.anthropic.com")),
        body={"error": {"type": "billing_error"}},
    )

    assert verificador._categoria_falha_ia(erro_auth) == "erro_autenticacao"
    assert verificador._categoria_falha_ia(erro_creditos) == "creditos_insuficientes"


def test_chave_de_api_e_detectada_sem_expor_o_valor(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "valor-de-teste-nao-real")
    assert ia.ia_disponivel()
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert not ia.ia_disponivel()
