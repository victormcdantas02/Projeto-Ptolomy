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

## IA na checagem (Claude)

Com uma chave da API da Anthropic, o backend manda a afirmação e os trechos da Wikipédia
para o Claude (`claude-opus-5-5`), que decide se cada fonte confirma, contradiz ou é neutra
e explica o porquê. Assim, frases sem número (como "O Brasil é um país") também são verificadas.

1. Crie uma chave em <https://console.anthropic.com/settings/keys> (a conta precisa ter crédito).
2. Copie `.env.example` para `.env` e cole a chave em `ANTHROPIC_API_KEY`. O `.env` não vai para o Git.
3. Reinicie o `uvicorn`.

Sem a chave, ou se a IA falhar, o Ptolomy continua funcionando com a comparação de números
(`comparador.py`). A resposta de `/verificar` diz qual foi usada no campo `metodo` (`ia` ou `numerico`).

## Site publicado (Netlify)

O site também roda no Netlify. Como o Netlify não roda Python, lá o backend são duas
funções em TypeScript que fazem o mesmo papel do `main.py`:

- `netlify/functions/verificar.mts` — busca na Wikipédia e pede para o Claude julgar as fontes,
  dar a veracidade (0 a 100%) com margem de erro e responder perguntas
- `netlify/functions/analises.mts` — CRUD de análises, guardado no Netlify Blobs

Para publicar: `npm install`, depois `npx netlify-cli deploy --build --prod`.
A chave da IA vai em **Project configuration > Environment variables** do Netlify, com o nome
`ANTHROPIC_API_KEY`. Sem ela, as funções usam o AI Gateway do Netlify (gasta créditos do Netlify).

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
- `ia.py` — pede para o Claude julgar se cada fonte confirma ou contradiz a afirmação
- `index.html` — site (login, checagem, histórico, painel)
