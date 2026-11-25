# Ptolomy.AI

**Questione. Verifique. Aprenda.**

Projeto acadêmico de letramento em inteligência artificial generativa. A plataforma ajuda a comparar uma afirmação ou resposta de IA com fontes consultadas, incentiva a verificação cruzada (cross-checking) e deixa a conclusão final com o usuário.

## Problema e proposta

Modelos generativos podem produzir informações convincentes, mas incorretas (alucinações). A Ptolomy.AI apresenta os trechos e links consultados, distingue evidências favoráveis, contraditórias e inconclusivas e oferece buscas independentes para apoiar o pensamento crítico. A ferramenta não é uma autoridade factual nem substitui o julgamento humano.

## Tecnologias e arquitetura

- **Interface:** HTML, CSS e JavaScript em `index.html` (SPA responsiva, login demonstrativo e histórico).
- **Backend local:** Python, FastAPI e SQLite (`main.py`, `banco.py`).
- **Busca:** API da Wikipédia em português; API de Localidades do IBGE para unidades federativas brasileiras; Wikidata para relações de capital (`buscador.py`).
- **Análise local:** Claude via Anthropic SDK, se configurado; senão, comparação contextual de quantidades e relações suportadas (`ia.py`, `comparador.py`, `verificador.py`).
- **Backend publicado:** funções TypeScript no Netlify; análises no Netlify Blobs.
- **Testes:** pytest e FastAPI TestClient.

O navegador chama `POST /verificar` e salva/consulta análises nas rotas `/analises`. O site no Netlify usa as funções equivalentes em `netlify/functions/`. A classificação automatizada é orientativa. O índice existente é uma heurística operacional com pesos definidos no projeto; não foi validado estatística ou cientificamente e **não representa uma probabilidade**. Pontuação elevada não garante veracidade.

## Requisitos

- Windows 10/11, VS Code e Git.
- Python 3.10 ou superior, com `pip`.
- Node.js e npm para validar/usar as funções Netlify.
- Chave Anthropic opcional para a análise semântica por Claude.

## Instalação e execução local (Windows / PowerShell)

Na pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Em outro terminal, abra `index.html` no navegador. A interface local chama o backend em `http://127.0.0.1:8000`. A documentação interativa da API fica em <http://127.0.0.1:8000/docs>. O arquivo `ptolomy.db` é criado automaticamente.

Se o comando `py` não existir, instale Python 3.10+ e marque a opção para adicioná-lo ao PATH durante a instalação.

### Chave da Anthropic (opcional)

Copie `.env.example` para `.env`, preencha `ANTHROPIC_API_KEY` e reinicie o servidor. O `.env` está no `.gitignore`; nunca publique a chave.

- Com chave e serviço disponível, o backend local usa trechos consultados para classificar evidências.
- Sem chave ou se a API falhar, o backend local tenta a comparação numérica. Sem correspondências conclusivas, apresenta evidências insuficientes.
- No Netlify sem uma chave/gateway, a função busca resumos da Wikipédia, mas não os classifica; o resultado não recebe índice quando não há evidências decisivas.

### Executar o site/funções no Netlify

```powershell
npm.cmd install
npx netlify-cli dev
```

No deploy, configure `ANTHROPIC_API_KEY` como variável de ambiente do projeto Netlify, ou habilite o AI Gateway. Não grave segredos no repositório.

## Cross-checking e fontes

As fontes apresentadas como consultadas são os artigos e registros que a busca automática realmente recuperou. A busca também consulta o IBGE para afirmações sobre estados/unidades federativas do Brasil e o Wikidata para a propriedade de capital; os links apontam para os registros consultados. A descrição do Wikidata identifica a propriedade P36 e é uma representação legível dos dados estruturados, não uma citação literal. A classificação automatizada é exibida junto do trecho; citações atribuídas ao modelo que não aparecem no conteúdo consultado são rebaixadas para neutras. Links para Google Acadêmico, SciELO, Gov.br, IBGE e Wikipédia que apareçam como sugestões de pesquisa independente **não são evidências verificadas**. O usuário pode registrar quais consultou e salvar uma conclusão independente do resultado automatizado.

## Metodologia e limitações

- O sistema divide o texto em afirmações e perguntas; a busca automática usa a Wikipédia em português e, para os temas suportados, as APIs do IBGE e do Wikidata. Busca por palavras-chave pode recuperar páginas apenas parcialmente relacionadas.
- Com Claude, o modelo classifica a relação de cada fonte como confirma, contradiz ou neutra. Sem Claude no backend Python, o comparador procura correspondências numéricas e algumas relações explícitas (como capital e composição); não avalia o significado geral da afirmação.
- O índice reaproveita pesos e faixas preexistentes no projeto. São decisões heurísticas não validadas; a quantidade, qualidade e independência das fontes disponíveis são limitadas. Evidências apenas neutras ou ausentes resultam em **Evidências insuficientes**, sem índice.
- A classificação local e os dados estruturados do Wikidata não substituem a leitura e o cruzamento com fontes independentes. Ausência de evidência não é evidência de falsidade; uma pontuação elevada não garante que a informação seja verdadeira.
- Login e cadastro são demonstrativos, armazenados no navegador. A API não tem autenticação/autorização real e seus endpoints CRUD não devem ser expostos como serviço multiusuário ou usados com dados pessoais sem proteção de acesso no servidor.
- O histórico SQLite é local; no Netlify, o armazenamento é Netlify Blobs. Os backends são implementações paralelas, não uma única API compartilhada.

## Rotas principais

| Método | Rota | Função |
|---|---|---|
| POST | `/verificar` | Consulta fontes e analisa afirmações |
| POST | `/analises` | Salva uma análise |
| GET | `/analises?usuario_id=...` | Lista análises |
| GET | `/analises/{id}` | Lê uma análise |
| PUT | `/analises/{id}` | Atualiza validação, fontes consultadas e conclusão do usuário |
| DELETE | `/analises/{id}` | Exclui uma análise |

A tabela SQLite recebe as colunas de conclusão e fontes consultadas automaticamente, preservando as análises existentes.

## Testes

Instale as dependências Python da seção de instalação e execute:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Os testes existentes cobrem rotas da API, CRUD, busca, comparação numérica, análise por IA e evidências insuficientes/citações não confirmadas. Os testes não validam a qualidade factual da Wikipédia ou do Claude, nem substituem testes de integração com credenciais reais.

## Roteiro técnico de demonstração acadêmica

1. Inicie o backend e abra a interface; explique a arquitetura local/Netlify e que o login é demonstrativo.
2. Envie uma afirmação curta com evidência numérica verificável. Mostre o trecho, a classificação, o link da fonte original e a limitação do índice heurístico.
3. Envie uma afirmação para a qual a busca não encontre apoio decisivo. Mostre **Evidências insuficientes** e explique que ausência de evidência não confirma falsidade.
4. Abra uma sugestão do Google Acadêmico, SciELO, Gov.br ou IBGE; retorne e marque a fonte somente depois de consultá-la.
5. Registre uma conclusão própria e mostre que ela é independente da classificação automatizada.
6. Abra o histórico e confirme que fontes consultadas e conclusão ficaram salvas.
7. Explique alucinações, a importância de fontes independentes e os limites da ferramenta; não apresente links sugeridos como verificados.

## Estrutura

- `main.py`, `banco.py`: API e persistência SQLite.
- `verificador.py`, `buscador.py`, `comparador.py`, `ia.py`: busca e análise local.
- `index.html`: interface, cross-checking e conclusão do usuário.
- `netlify/functions/`: funções TypeScript de verificação e CRUD.
- `tests/`: testes automatizados Python.
