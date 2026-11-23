# Ptolomy.AI

Checagem de fatos: o usuário cola uma afirmação, o backend em Python busca fontes na
Wikipédia e compara com a afirmação, e o site mostra um score de confiabilidade.
Cada análise fica salva num banco SQLite (`ptolomy.db`, criado sozinho na primeira execução).

## Como rodar

```
pip install -r requirements.txt
uvicorn main:app --reload
```

Depois abra o arquivo `index.html` no navegador.

## Testes

```
python -m pytest
```

## Rotas da API

| Método | Rota | O que faz |
|---|---|---|
| POST | `/verificar` | busca fontes na Wikipédia para o texto |
| POST | `/analises` | salva uma análise (texto, IA de origem, resultado e fontes) |
| GET | `/analises` | lista as análises (opcional: `?usuario_id=...`) |
| GET | `/analises/{id}` | mostra uma análise |
| PUT | `/analises/{id}` | altera o status (`não verificado`, `confirmado`, `falso`) e a observação |
| DELETE | `/analises/{id}` | exclui uma análise |

Com o servidor rodando, dá para testar as rotas em <http://127.0.0.1:8000/docs>.

## Arquivos

- `main.py` — API (FastAPI) com as rotas acima
- `banco.py` — banco SQLite e as funções do CRUD de análises
- `verificador.py` — separa o texto em frases e monta o resultado
- `buscador.py` — busca artigos na Wikipédia
- `comparador.py` — compara os números da afirmação com os das fontes
- `index.html` — site (login, checagem, histórico, painel)
