# Ptolomy.AI

Checagem de fatos: o usuário cola uma afirmação, o backend em Python busca fontes na
Wikipédia e compara com a afirmação, e o site mostra um score de confiabilidade.

## Como rodar

```
pip install -r requirements.txt
uvicorn main:app --reload
```

Depois abra o arquivo `index.html` no navegador.

## Arquivos

- `main.py` — API (FastAPI) com a rota `POST /verificar`
- `verificador.py` — separa o texto em frases e monta o resultado
- `buscador.py` — busca artigos na Wikipédia
- `comparador.py` — compara os números da afirmação com os das fontes
- `index.html` — site (login, checagem, histórico, painel)