// Versão online (Netlify) do back-end de verificação.
// Faz o mesmo que verificador.py + buscador.py + ia.py: separa as frases,
// busca artigos na Wikipédia e pede para o Claude julgar se cada fonte
// confirma, contradiz ou é neutra. A chave fica na variável ANTHROPIC_API_KEY do Netlify.
import Anthropic from "@anthropic-ai/sdk"
import type { Config } from "@netlify/functions"

const URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"
const MODELO = "claude-opus-5-5"
const MAX_AFIRMACOES = 10

const PALAVRAS_IGNORADAS = new Set([
  "o", "a", "os", "as", "um", "uma", "de", "do", "da",
  "dos", "das", "em", "no", "na", "e", "possui", "tem", "é",
])

// Formato da resposta: a API garante que a IA devolve exatamente este JSON
const FORMATO = {
  type: "object",
  properties: {
    avaliacoes: {
      type: "array",
      items: {
        type: "object",
        properties: {
          indice: { type: "integer" },
          posicao: { type: "string", enum: ["confirma", "contradiz", "neutra"] },
          trecho: { type: "string" },
          justificativa: { type: "string" },
        },
        required: ["indice", "posicao", "trecho", "justificativa"],
        additionalProperties: false,
      },
    },
    chance_acerto: { type: "integer" },
    chance_conhecimento: { type: "integer" },
    justificativa_geral: { type: "string" },
  },
  required: ["avaliacoes", "chance_acerto", "chance_conhecimento", "justificativa_geral"],
  additionalProperties: false,
}

// Formato da resposta para uma pergunta
const FORMATO_PERGUNTA = {
  type: "object",
  properties: {
    encontrada: { type: "boolean" },
    resposta: { type: "string" },
    indice_fonte: { type: "integer" },
    trecho: { type: "string" },
    chance_acerto: { type: "integer" },
  },
  required: ["encontrada", "resposta", "indice_fonte", "trecho", "chance_acerto"],
  additionalProperties: false,
}

const INSTRUCOES = `Você é o verificador de fatos do Ptolomy.AI, um projeto acadêmico de checagem de fatos.

Você recebe uma afirmação e trechos de artigos da Wikipédia em português, numerados. Para cada fonte, decida a posição dela em relação à afirmação, usando só o texto daquela fonte:
- "confirma": o texto sustenta a afirmação.
- "contradiz": o texto diz algo incompatível com a afirmação.
- "neutra": o texto não fala do assunto ou não basta para decidir.

Julgue pelo que o texto diz, não pelo seu conhecimento próprio: se a fonte não trata do que a afirmação diz, ela é neutra, mesmo que você saiba a resposta. Isso mantém o resultado ligado às fontes que o site mostra.

Em "trecho", copie do texto da fonte a frase que sustenta a sua decisão, sem alterar; para "neutra", deixe vazio. Em "justificativa", explique em uma frase curta, em português, por que a fonte confirma, contradiz ou é neutra. Devolva uma avaliação para cada fonte recebida, com o mesmo número.

Por fim, em "chance_acerto", dê um número de 0 a 100 para a chance de a afirmação estar correta segundo essas fontes: perto de 100 quando as fontes confirmam com clareza, perto de 0 quando contradizem com clareza, e perto de 50 quando não dá para decidir.

Em "chance_conhecimento", dê de 0 a 100 a chance de a afirmação ser verdadeira segundo o seu próprio conhecimento, sem olhar as fontes. O site só usa esse número quando nenhuma fonte confirma nem contradiz, e avisa o usuário que ele não tem confirmação nas fontes. Afirmações inventadas ou exageradas, típicas de alucinação de IA, devem receber número baixo.

Em "justificativa_geral", explique em uma ou duas frases, em português, se a afirmação parece verdadeira ou alucinação e por quê. Se nenhuma fonte trata do assunto, diga isso e explique o que o seu conhecimento indica.`

const INSTRUCOES_PERGUNTA = `Você é o assistente de pesquisa do Ptolomy.AI, um projeto acadêmico de checagem de fatos.

Você recebe uma pergunta e trechos de artigos da Wikipédia em português, numerados. Responda sempre à pergunta, em uma ou duas frases curtas em português. Prefira o que os trechos dizem, porque assim a resposta fica ligada a uma fonte que o site mostra.

- Se algum trecho traz a resposta, ponha "encontrada" como true, indique em "indice_fonte" o número da fonte usada e copie em "trecho" a frase dela que traz a resposta, sem alterar.
- Se nenhum trecho traz a resposta, responda com o seu conhecimento, ponha "encontrada" como false, use -1 em "indice_fonte" e deixe "trecho" vazio. O site avisa o usuário que essa resposta não tem fonte.

Em "chance_acerto", dê de 0 a 100 a chance de a sua resposta estar correta: alta quando um trecho diz a resposta com todas as letras, mais baixa quando você precisou deduzir ou respondeu sem fonte, e baixa quando a pergunta não tem resposta clara.`

type Fonte = { titulo: string; descricao: string; url: string }
type Avaliacao = { indice: number; posicao: "confirma" | "contradiz" | "neutra"; trecho: string; justificativa: string }
type Julgamento = { avaliacoes: Avaliacao[]; chance_acerto: number; chance_conhecimento: number; justificativa_geral: string }
type RespostaIA = { encontrada: boolean; resposta: string; indice_fonte: number; trecho: string; chance_acerto: number }

const limitar = (n: number, min: number, max: number) => Math.min(max, Math.max(min, Math.round(n)))

// Margem de erro (em pontos) da chance de acerto. Regra fixa e explicável:
// começa em 35 e cai 10 para cada fonte que confirma ou contradiz (mínimo 5);
// sobe 15 quando as fontes discordam entre si. Fica sempre entre 5 e 40.
function calcularMargem(decisivas: number, discordam: boolean): number {
  return limitar(35 - 10 * decisivas + (discordam ? 15 : 0), 5, 40)
}

// Mesmo critério do comparador.py: o ponto antes de um dígito ("5.571") não fecha a frase
function separarFrases(texto: string): string[] {
  const frases: string[] = []
  let atual = ""
  for (let i = 0; i < texto.length; i++) {
    const letra = texto[i]
    atual += letra
    if (".!?".includes(letra)) {
      if (i + 1 < texto.length && /\d/.test(texto[i + 1])) continue
      frases.push(atual.trim())
      atual = ""
    }
  }
  if (atual.trim() !== "") frases.push(atual.trim())
  return frases.filter(Boolean)
}

function palavrasChave(afirmacao: string): string[] {
  const palavras = afirmacao.toLowerCase().match(/[a-zA-ZÀ-ÿ]+/g) ?? []
  return palavras.filter((p) => !PALAVRAS_IGNORADAS.has(p))
}

async function buscarFontes(afirmacao: string): Promise<Fonte[]> {
  const termo = palavrasChave(afirmacao).join(" ")
  if (!termo) return []

  const parametros = new URLSearchParams({
    action: "query",
    generator: "search",
    gsrsearch: termo,
    gsrlimit: "3",
    prop: "extracts",
    exintro: "1",
    explaintext: "1",
    format: "json",
  })

  const resposta = await fetch(`${URL_WIKIPEDIA}?${parametros}`, {
    headers: { "User-Agent": "ProjetoPtolomy/1.0 (projeto academico)" },
    signal: AbortSignal.timeout(10000),
  })
  if (!resposta.ok) throw new Error(`Wikipédia respondeu ${resposta.status}`)

  const dados = await resposta.json()
  if (!dados.query) return []

  const paginas = Object.values(dados.query.pages) as Array<{ pageid: number; title: string; index: number; extract?: string }>
  paginas.sort((a, b) => a.index - b.index)

  return paginas.map((p) => ({
    titulo: p.title,
    descricao: (p.extract ?? "").slice(0, 500),
    url: `https://pt.wikipedia.org/?curid=${p.pageid}`,
  }))
}

function montarPedido(afirmacao: string, fontes: Fonte[]): string {
  const partes = [`<afirmacao>${afirmacao}</afirmacao>`]
  fontes.forEach((f, indice) => {
    partes.push(`<fonte indice="${indice}" titulo="${f.titulo}">\n${f.descricao}\n</fonte>`)
  })
  return partes.join("\n\n")
}

// Uma chamada à IA com resposta em JSON garantido pelo formato. Devolve null se a IA recusar.
async function perguntarIA<T>(cliente: Anthropic, instrucoes: string, formato: { [chave: string]: unknown }, pedido: string): Promise<T | null> {
  const resposta = await cliente.beta.messages.create({
    model: MODELO,
    max_tokens: 8000,
    // Se a IA recusar por engano, a própria API tenta de novo com outro modelo
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    output_config: { effort: "low", format: { type: "json_schema", schema: formato } },
    system: instrucoes,
    messages: [{ role: "user", content: pedido }],
  })

  if (resposta.stop_reason === "refusal") return null

  const bloco = resposta.content.find((b) => b.type === "text")
  if (!bloco || bloco.type !== "text") return null

  return JSON.parse(bloco.text) as T
}

async function avaliarFontes(cliente: Anthropic, afirmacao: string, fontes: Fonte[]): Promise<Julgamento | null> {
  if (fontes.length === 0) return null

  const julgamento = await perguntarIA<Julgamento>(cliente, INSTRUCOES, FORMATO, montarPedido(afirmacao, fontes))
  if (!julgamento) return null

  return {
    avaliacoes: julgamento.avaliacoes.filter((a) => a.indice >= 0 && a.indice < fontes.length),
    chance_acerto: limitar(julgamento.chance_acerto, 0, 100),
    chance_conhecimento: limitar(julgamento.chance_conhecimento, 0, 100),
    justificativa_geral: julgamento.justificativa_geral,
  }
}

async function responderPergunta(cliente: Anthropic, pergunta: string) {
  const fontes = await buscarFontes(pergunta)
  // Mesmo sem fontes da Wikipédia, a IA ainda é chamada para responder (sem fonte)
  const semResposta = {
    pergunta,
    encontrada: false,
    resposta: "As fontes consultadas não trazem essa informação.",
    fonte: null as null | { titulo: string; url: string },
    trecho: "",
    chance_acerto: 0,
    margem: 40,
    base: "conhecimento" as "fontes" | "conhecimento",
  }

  const pedido = montarPedido(pergunta, fontes).replace(/^<afirmacao>(.*)<\/afirmacao>/, "<pergunta>$1</pergunta>")
  const r = await perguntarIA<RespostaIA>(cliente, INSTRUCOES_PERGUNTA, FORMATO_PERGUNTA, pedido)
  if (!r) return semResposta

  const fonte = r.encontrada ? fontes[r.indice_fonte] : undefined
  if (!fonte) {
    // A IA respondeu sem apoio nas fontes: a resposta aparece, mas com margem máxima
    return { ...semResposta, resposta: r.resposta, chance_acerto: limitar(r.chance_acerto, 0, 100) }
  }

  return {
    pergunta,
    encontrada: true,
    resposta: r.resposta,
    fonte: { titulo: fonte.titulo, url: fonte.url },
    trecho: r.trecho,
    chance_acerto: limitar(r.chance_acerto, 0, 100),
    // A resposta vem de uma fonte só: margem de uma fonte decisiva
    margem: calcularMargem(1, false),
    base: "fontes" as "fontes" | "conhecimento",
  }
}

function montarEvidencias(avaliacoes: Avaliacao[], fontes: Fonte[]) {
  return avaliacoes.map((a) => {
    const fonte = fontes[a.indice]
    return {
      titulo: fonte.titulo,
      url: fonte.url,
      posicao: a.posicao,
      // Sem trecho (fonte neutra), mostra o começo do resumo do artigo
      trecho: a.trecho.trim() || fonte.descricao.slice(0, 200),
      justificativa: a.justificativa,
    }
  })
}

const erro = (status: number, detail: string) => Response.json({ detail }, { status })

// Só o tipo da chave (nunca a chave), para saber de que serviço ela é
function tipoDaChave(chave: string): string {
  if (chave.startsWith("sk-ant-")) return "Anthropic"
  if (chave.startsWith("sk-proj-") || chave.startsWith("sk-")) return "OpenAI (ChatGPT)"
  if (chave.startsWith("AIza")) return "Google Gemini"
  if (chave.startsWith("nfp_") || chave.startsWith("nfc_")) return "Netlify"
  return "desconhecido"
}

// Decide como falar com o Claude:
// 1. ANTHROPIC_API_KEY com uma chave da Anthropic (sk-ant-...) → direto na Anthropic, com a sua chave
// 2. senão → AI Gateway do Netlify, cujo par NETLIFY_AI_GATEWAY_KEY / NETLIFY_AI_GATEWAY_URL
//    o Netlify sempre injeta e nunca é sobrescrito por variáveis suas (gasta créditos do Netlify)
function escolherConexao(): { opcoes: ConstructorParameters<typeof Anthropic>[0]; origem: string } | null {
  // trim(): espaços ou quebra de linha colados junto com a chave fazem a Anthropic recusar
  const chave = Netlify.env.get("ANTHROPIC_API_KEY")?.trim() ?? ""

  if (chave.startsWith("sk-ant-")) {
    return {
      // authToken: null impede que um token do Gateway (ANTHROPIC_AUTH_TOKEN) vá junto com a chave
      opcoes: { apiKey: chave, baseURL: "https://api.anthropic.com", authToken: null },
      origem: "sua chave da Anthropic",
    }
  }

  const chaveGateway = Netlify.env.get("NETLIFY_AI_GATEWAY_KEY")
  const urlGateway = Netlify.env.get("NETLIFY_AI_GATEWAY_URL")
  if (chaveGateway && urlGateway) {
    const aviso = chave ? ` (a ANTHROPIC_API_KEY salva é do tipo ${tipoDaChave(chave)}, não da Anthropic, e foi ignorada)` : ""
    // O Gateway injeta ANTHROPIC_BASE_URL com o endereço dele para a Anthropic; se não houver, usa a URL geral
    const baseURL = Netlify.env.get("ANTHROPIC_BASE_URL") || urlGateway
    return {
      opcoes: { apiKey: chaveGateway, authToken: null, baseURL },
      origem: `AI Gateway do Netlify em ${baseURL}${aviso}`,
    }
  }

  return null
}

export default async (req: Request) => {
  let corpo: { texto?: unknown }
  try {
    corpo = await req.json()
  } catch {
    return erro(400, "Envie um JSON como {\"texto\": \"...\"}")
  }

  const texto = String(corpo.texto ?? "")
  if (texto.length < 15 || texto.length > 2000) {
    return erro(422, "O texto precisa ter entre 15 e 2000 caracteres")
  }

  const conexao = escolherConexao()
  if (!conexao) return erro(503, "Nenhuma chave de IA disponível: configure ANTHROPIC_API_KEY ou ative o AI Gateway do Netlify")
  const cliente = new Anthropic({ ...conexao.opcoes, timeout: 45000, maxRetries: 1 })
  const origem = conexao.origem

  const frases = separarFrases(texto)
  const perguntas = frases.filter((f) => f.endsWith("?")).slice(0, MAX_AFIRMACOES)
  const afirmacoesTexto = frases.filter((f) => !f.endsWith("?")).slice(0, MAX_AFIRMACOES)

  try {
    // Afirmações e perguntas são processadas ao mesmo tempo, para caber no limite de 60s do Netlify
    const [afirmacoes, respostas] = await Promise.all([
      Promise.all(
        afirmacoesTexto.map(async (frase, i) => {
          const fontes = await buscarFontes(frase)
          const julgamento = await avaliarFontes(cliente, frase, fontes)
          const avaliacoes = julgamento?.avaliacoes ?? []
          const confirmam = avaliacoes.filter((a) => a.posicao === "confirma").length
          const contradizem = avaliacoes.filter((a) => a.posicao === "contradiz").length
          const decisivas = confirmam + contradizem

          // Veracidade: vem das fontes quando alguma confirma ou contradiz; senão, do conhecimento
          // da IA (sem confirmação nas fontes, margem máxima). Sem julgamento nenhum, fica em 50.
          let base: "fontes" | "conhecimento" | "nenhuma" = "nenhuma"
          let chance = 50
          let margem = 40
          if (julgamento && decisivas > 0) {
            base = "fontes"
            chance = julgamento.chance_acerto
            margem = calcularMargem(decisivas, confirmam > 0 && contradizem > 0)
          } else if (julgamento) {
            base = "conhecimento"
            chance = julgamento.chance_conhecimento
          }

          return {
            id: i + 1,
            texto: frase,
            status_verificacao: "concluida",
            fontes,
            evidencias: montarEvidencias(avaliacoes, fontes),
            chance_acerto: chance,
            margem,
            base,
            justificativa_geral: julgamento?.justificativa_geral ?? "Não foi possível avaliar esta afirmação com as fontes encontradas.",
            metodo: "ia",
          }
        }),
      ),
      Promise.all(perguntas.map((p) => responderPergunta(cliente, p))),
    ])

    return Response.json({
      status: "sucesso",
      texto_analisado: texto,
      afirmacoes,
      perguntas,
      respostas,
      quantidade_afirmacoes: afirmacoes.length,
      quantidade_perguntas: perguntas.length,
      conexao_ia: origem,
    })
  } catch (e) {
    if (e instanceof Anthropic.APIError) {
      console.error("Erro na API da Anthropic:", e.status, e.message)
      // Mostra o código e o tipo do erro (nunca a chave), para dar para saber o que corrigir
      const tipo = (e.error as { error?: { type?: string; message?: string } } | undefined)?.error
      return erro(503, `Serviço de IA indisponível (Anthropic ${e.status ?? "sem resposta"}: ${tipo?.type ?? "erro"} — ${tipo?.message ?? e.message}; usando ${origem})`)
    }
    console.error("Erro na verificação:", e)
    return erro(503, "Serviço de fontes indisponível")
  }
}

export const config: Config = {
  path: "/verificar",
  method: "POST",
}
