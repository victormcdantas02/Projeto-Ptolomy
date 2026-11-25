// Versão online (Netlify) do back-end de verificação.
// Faz o mesmo que verificador.py + buscador.py + ia.py: separa as frases,
// busca artigos na Wikipédia e pede para o Claude julgar se cada fonte
// confirma, contradiz ou é neutra. A chave fica na variável ANTHROPIC_API_KEY do Netlify.
import Anthropic from "@anthropic-ai/sdk"
import type { Config } from "@netlify/functions"

const URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"
const URL_IBGE_UFS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
const URL_WIKIDATA = "https://www.wikidata.org/w/api.php"
const MODELO = "claude-opus-5-5"
const MAX_AFIRMACOES = 10
const MAX_CONSULTAS_WIKIPEDIA = 3
const MAX_RESULTADOS_POR_CONSULTA = 8
const MAX_EXTRATOS_POR_LOTE = 20
const MAX_FONTES = 6
const MAX_CARACTERES_EXCERTO = 2500
const TEMPO_CACHE_MS = 10 * 60 * 1000
const INTERVALO_REQUISICOES_MS = 500
const MAX_TENTATIVAS_REQUISICAO = 2
const MAX_ESPERA_RETRY_MS = 5000
const MAX_ITENS_CACHE = 256

const PALAVRAS_IGNORADAS = new Set([
  "o", "a", "os", "as", "um", "uma", "de", "do", "da",
  "dos", "das", "em", "no", "na", "e", "possui", "tem", "é",
  "sao", "ser", "um", "uma", "por", "com", "para", "que",
  "qual", "como", "afirmacao", "informacao", "segundo",
])
const PALAVRAS_NUMERICAS = new Set([
  "zero", "um", "uma", "dois", "duas", "tres", "quatro", "cinco",
  "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze",
  "catorze", "quatorze", "quinze", "dezesseis", "dezassete", "dezessete",
  "dezoito", "dezenove", "vinte", "trinta", "quarenta", "cinquenta",
  "sessenta", "setenta", "oitenta", "noventa",
])

type Pagina = { pageid: number; title: string; index?: number; extract?: string }
type Fonte = { titulo: string; descricao: string; url: string; tipo_fonte?: string }

const cacheRespostas = new Map<string, { expira: number; dados: unknown }>()
let filaRequisicoes: Promise<unknown> = Promise.resolve()
let ultimaRequisicao = 0

function clonar<T>(valor: T): T {
  return JSON.parse(JSON.stringify(valor)) as T
}

async function obterJson<T>(url: string): Promise<T> {
  const cacheado = cacheRespostas.get(url)
  if (cacheado && cacheado.expira > Date.now()) return clonar(cacheado.dados as T)

  const requisicao = filaRequisicoes.then(async () => {
    const existente = cacheRespostas.get(url)
    if (existente && existente.expira > Date.now()) return clonar(existente.dados as T)

    const espera = Math.max(0, ultimaRequisicao + INTERVALO_REQUISICOES_MS - Date.now())
    if (espera) await new Promise((resolver) => setTimeout(resolver, espera))
    let resposta: Response | undefined
    for (let tentativa = 0; tentativa < MAX_TENTATIVAS_REQUISICAO; tentativa++) {
      resposta = await fetch(url, {
        headers: { "User-Agent": "ProjetoPtolomy/1.0 (projeto academico)" },
        signal: AbortSignal.timeout(10000),
      })
      ultimaRequisicao = Date.now()
      if (![429, 500, 502, 503, 504].includes(resposta.status)
        || tentativa + 1 === MAX_TENTATIVAS_REQUISICAO) break
      const retryAfter = Number(resposta.headers.get("Retry-After") ?? "1")
      const esperaRetry = Number.isFinite(retryAfter) ? retryAfter * 1000 : 1000
      await new Promise((resolver) =>
        setTimeout(resolver, Math.min(Math.max(esperaRetry, 1000), MAX_ESPERA_RETRY_MS)))
    }
    if (!resposta) throw new Error("A requisição externa não foi iniciada")
    if (!resposta.ok) throw new Error(`A fonte respondeu HTTP ${resposta.status}`)
    const dados = await resposta.json() as T

    for (const [chave, item] of cacheRespostas) {
      if (item.expira <= Date.now()) cacheRespostas.delete(chave)
    }
    if (cacheRespostas.size >= MAX_ITENS_CACHE) {
      const maisAntiga = cacheRespostas.keys().next()
      if (!maisAntiga.done) cacheRespostas.delete(maisAntiga.value)
    }
    cacheRespostas.set(url, { expira: Date.now() + TEMPO_CACHE_MS, dados: clonar(dados) })
    return dados
  })
  filaRequisicoes = requisicao.then(() => undefined, () => undefined)
  return requisicao as Promise<T>
}

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
    justificativa_geral: { type: "string" },
  },
  required: ["avaliacoes", "justificativa_geral"],
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
  },
  required: ["encontrada", "resposta", "indice_fonte", "trecho"],
  additionalProperties: false,
}

const INSTRUCOES = `Você é o assistente de análise de evidências do Ptolomy.AI, um projeto acadêmico de letramento em IA.

Você recebe uma afirmação e trechos de artigos da Wikipédia em português, numerados. Para cada fonte, decida a posição dela em relação à afirmação, usando só o texto daquela fonte:
- "confirma": o texto sustenta a afirmação.
- "contradiz": o texto diz algo incompatível com a afirmação.
- "neutra": o texto não fala do assunto ou não basta para decidir.

Julgue pelo que o texto diz, não pelo seu conhecimento próprio: se a fonte não trata do que a afirmação diz, ela é neutra, mesmo que você saiba a resposta. Isso mantém o resultado ligado às fontes que o site mostra.

Em "trecho", copie do texto da fonte a frase que sustenta a sua decisão, sem alterar; para "neutra", deixe vazio. Em "justificativa", explique em uma frase curta, em português, por que a fonte confirma, contradiz ou é neutra. Devolva uma avaliação para cada fonte recebida, com o mesmo número.

Em "justificativa_geral", resuma em uma ou duas frases o que as fontes consultadas sustentam, contradizem ou não permitem concluir. Não use conhecimento externo às fontes.`

const INSTRUCOES_PERGUNTA = `Você é o assistente de pesquisa do Ptolomy.AI, um projeto acadêmico de checagem de fatos.

Você recebe uma pergunta e trechos de artigos da Wikipédia em português, numerados. Responda sempre à pergunta, em uma ou duas frases curtas em português. Prefira o que os trechos dizem, porque assim a resposta fica ligada a uma fonte que o site mostra.

- Se algum trecho traz a resposta, ponha "encontrada" como true, indique em "indice_fonte" o número da fonte usada e copie em "trecho" a frase dela que traz a resposta, sem alterar.
- Se nenhum trecho traz a resposta, responda com o seu conhecimento, ponha "encontrada" como false, use -1 em "indice_fonte" e deixe "trecho" vazio. O site avisa o usuário que essa resposta não tem fonte.

`

type Avaliacao = { indice: number; posicao: "confirma" | "contradiz" | "neutra"; trecho: string; justificativa: string }
type Julgamento = { avaliacoes: Avaliacao[]; justificativa_geral: string }
type RespostaIA = { encontrada: boolean; resposta: string; indice_fonte: number; trecho: string }

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
  const palavras = afirmarNormalizado(afirmacao).match(/[a-z]+/g) ?? []
  return [...new Set(palavras.filter((p) => !PALAVRAS_IGNORADAS.has(p) && !PALAVRAS_NUMERICAS.has(p)))]
}

function afirmarNormalizado(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
}

function entidadeDaCapital(afirmacao: string): string | null {
  const normalizada = afirmarNormalizado(afirmacao).replace(/[.!?;:]+$/, "").trim()
  const direta = normalizada.match(/\bcapital\s+(?:do|da|de)\s+(.+?)\s+(?:e|eh)\s+(.+)$/)
  if (direta) return direta[1].replace(/^(?:o|a|os|as)\s+/, "").trim()
  const inversa = normalizada.match(/^(.+?)\s+(?:e|eh)\s+(?:a\s+)?capital(?:\s+federal)?\s+(?:do|da|de)\s+(.+)$/)
  return inversa ? inversa[2].replace(/^(?:o|a|os|as)\s+/, "").trim() : null
}

function valorDaCapital(afirmacao: string): string | null {
  const normalizada = afirmarNormalizado(afirmacao).replace(/[.!?;:]+$/, "").trim()
  const direta = normalizada.match(/\bcapital\s+(?:do|da|de)\s+(.+?)\s+(?:e|eh)\s+(.+)$/)
  if (direta) return direta[2].trim()
  const inversa = normalizada.match(/^(.+?)\s+(?:e|eh)\s+(?:a\s+)?capital(?:\s+federal)?\s+(?:do|da|de)\s+(.+)$/)
  return inversa ? inversa[1].trim() : null
}

function termosBusca(afirmacao: string): Set<string> {
  const termos = termosNormalizados(afirmacao)
  const entidade = entidadeDaCapital(afirmacao)
  const valor = valorDaCapital(afirmacao)
  if (entidade && valor) {
    const termosEntidade = termosNormalizados(entidade)
    for (const termo of termosNormalizados(valor)) {
      if (!termosEntidade.has(termo)) termos.delete(termo)
    }
  }
  return termos
}

function gerarConsultas(afirmacao: string): string[] {
  const termos = palavrasChave(afirmacao)
  if (!termos.length) return []

  const consultas = [termos.join(" ")]
  const conceitosEstado = new Set(["estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"])
  const conceitosAssunto = new Set([
    "capital", "capitais", "satelite", "satelites", "natural", "naturais",
    "composicao", "composta", "composto", "hidrogenio", "oxigenio",
    "elemento", "elementos",
  ])
  const falaDeEstados = termos.some((termo) => conceitosEstado.has(termo))
  const entidade = termos.find((termo) => !conceitosEstado.has(termo) && !conceitosAssunto.has(termo))
  if (falaDeEstados && entidade) {
    consultas.push(`estados do ${entidade}`, `unidades federativas do ${entidade}`)
  }
  if ((termos.includes("capital") || termos.includes("capitais")) && entidade) {
    consultas.push(`capital do ${entidade}`)
  }
  if (termos.some((termo) => ["satelite", "satelites"].includes(termo))) {
    consultas.push(entidade ? `satelites naturais da ${entidade}` : "satelites naturais")
  }
  if (termos.some((termo) => ["composicao", "composta", "composto", "hidrogenio", "oxigenio"].includes(termo))) {
    consultas.push(`composicao ${termos.join(" ")}`)
  }
  return [...new Set(consultas.map((consulta) => consulta.trim().replace(/\s+/g, " ")))]
    .slice(0, MAX_CONSULTAS_WIKIPEDIA)
}

function termosNormalizados(texto: string): Set<string> {
  return new Set(afirmarNormalizado(texto).match(/[a-z0-9]+/g) ?? [])
}

function relevancia(pagina: Pagina, termosAfirmacao: Set<string>, consultas: string[], falaDeEstados: boolean): number {
  const termosTitulo = termosNormalizados(pagina.title)
  const termosTexto = termosNormalizados(pagina.extract ?? "")
  let pontos = 5 * [...termosAfirmacao].filter((termo) => termosTitulo.has(termo)).length
    + 2 * [...termosAfirmacao].filter((termo) => termosTexto.has(termo)).length
  const titulo = afirmarNormalizado(pagina.title)
  if (falaDeEstados && titulo.includes("unidades federativas") && titulo.includes("brasil")) pontos += 20
  if (falaDeEstados && titulo.includes("estados do brasil")) pontos += 15
  if (/\b(?:18|19|20)\d{2}\s*[-–—]\s*(?:18|19|20)?\d{0,4}\b/.test(titulo)
    || ["historico", "historia do", "extinto"].some((termo) => titulo.includes(termo))) pontos -= 25
  if (titulo.includes("lista de")) pontos -= 15
  if (falaDeEstados && titulo.startsWith("estado do brasil")) pontos -= 20
  if (falaDeEstados && titulo.includes("distrito federal") && !titulo.includes("brasil")) pontos -= 8
  if (consultas.some((consulta) => consulta.includes("unidades federativas do brasil"))
    && titulo.includes("unidades federativas")) pontos += 10
  return pontos
}

async function buscarPaginasWikipedia(consulta: string): Promise<Pagina[]> {
  const parametros = new URLSearchParams({
    action: "query",
    generator: "search",
    gsrsearch: consulta,
    gsrnamespace: "0",
    gsrlimit: String(MAX_RESULTADOS_POR_CONSULTA),
    prop: "extracts",
    exlimit: "max",
    exintro: "1",
    explaintext: "1",
    exchars: String(MAX_CARACTERES_EXCERTO),
    format: "json",
  })
  const dados = await obterJson<{ query?: { pages?: Record<string, Pagina> } }>(
    `${URL_WIKIPEDIA}?${parametros}`,
  )
  return Object.values(dados.query?.pages ?? {})
}

async function completarExtratos(paginas: Pagina[]): Promise<void> {
  const ids = paginas
    .filter((pagina) => !pagina.extract)
    .map((pagina) => String(pagina.pageid))
    .slice(0, MAX_EXTRATOS_POR_LOTE)
  if (!ids.length) return

  const parametros = new URLSearchParams({
    action: "query",
    pageids: ids.join("|"),
    prop: "extracts",
    exlimit: "max",
    exintro: "1",
    explaintext: "1",
    exchars: String(MAX_CARACTERES_EXCERTO),
    format: "json",
  })
  const dados = await obterJson<{ query?: { pages?: Record<string, Pagina> } }>(
    `${URL_WIKIPEDIA}?${parametros}`,
  )
  for (const pagina of paginas) {
    const extraida = dados.query?.pages?.[String(pagina.pageid)]
    if (extraida?.extract) pagina.extract = extraida.extract
  }
}

async function buscarUfsIBGE(afirmacao: string): Promise<Fonte | null> {
  const termos = palavrasChave(afirmacao)
  const falaDeEstados = termos.some((termo) =>
    ["estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"].includes(termo))
  if (!falaDeEstados || !termos.some((termo) => ["brasil", "brasileiro", "brasileira"].includes(termo))) return null

  try {
    const unidades = await obterJson<Array<{ sigla?: string; nome?: string }>>(URL_IBGE_UFS)
    const validas = unidades.filter((unidade) => typeof unidade.sigla === "string" && typeof unidade.nome === "string")
    if (!validas.length) throw new Error("Formato de resposta do IBGE inválido")
    const distritoFederal = validas.find((unidade) => unidade.sigla?.toUpperCase() === "DF")
    const estados = validas.filter((unidade) => unidade.sigla?.toUpperCase() !== "DF")
    let descricao = `A API de Localidades do IBGE lista ${validas.length} unidades da Federação do Brasil, incluindo ${estados.length} estados`
    if (distritoFederal) descricao += ` e o Distrito Federal (${distritoFederal.sigla})`
    descricao += `. Unidades listadas: ${validas.map((unidade) => `${unidade.nome} (${unidade.sigla})`).sort().join(", ")}.`
    return {
      titulo: "Unidades da Federação do Brasil — IBGE (API de Localidades)",
      descricao,
      url: URL_IBGE_UFS,
      tipo_fonte: "oficial",
    }
  } catch (error) {
    console.warn("API de Localidades do IBGE indisponível:", error instanceof Error ? error.name : "erro desconhecido")
    return null
  }
}

async function buscarCapitalWikidata(afirmacao: string): Promise<Fonte | null> {
  const entidade = entidadeDaCapital(afirmacao)
  if (!entidade) return null

  try {
    const parametrosBusca = new URLSearchParams({
      action: "wbsearchentities",
      search: entidade,
      language: "pt",
      format: "json",
      limit: "10",
    })
    const busca = await obterJson<{
      search?: Array<{
        id?: string
        label?: string
        aliases?: string[]
        match?: { text?: string }
      }>
    }>(`${URL_WIKIDATA}?${parametrosBusca}`)
    const normalizada = afirmarNormalizado(entidade)
    const resultado = busca.search?.find((item) =>
      afirmarNormalizado(item.match?.text ?? "") === normalizada
      || afirmarNormalizado(item.label ?? "") === normalizada
      || item.aliases?.some((alias) => afirmarNormalizado(alias) === normalizada))
    if (!resultado?.id) return null

    type Declaracao = {
      rank?: string
      qualifiers?: Record<string, unknown>
      mainsnak?: { datavalue?: { type?: string; value?: { id?: string } } }
    }
    const parametrosEntidade = new URLSearchParams({
      action: "wbgetentities",
      ids: resultado.id,
      props: "labels|claims",
      languages: "pt|en",
      format: "json",
    })
    const dados = await obterJson<{
      entities?: Record<string, {
        labels?: Record<string, { value?: string }>
        claims?: Record<string, Declaracao[]>
      }>
    }>(`${URL_WIKIDATA}?${parametrosEntidade}`)
    const entidadeDados = dados.entities?.[resultado.id]
    const declaracoes = entidadeDados?.claims?.P36 ?? []
    const preferidas = declaracoes.filter((declaracao) => declaracao.rank === "preferred")
    const atuais = preferidas.length
      ? preferidas
      : declaracoes.filter((declaracao) => !declaracao.qualifiers?.P582)
    const capitaisIds = [...new Set(atuais
      .filter((declaracao) => declaracao.mainsnak?.datavalue?.type === "wikibase-entityid")
      .map((declaracao) => declaracao.mainsnak?.datavalue?.value?.id)
      .filter((id): id is string => Boolean(id)))]
    if (!capitaisIds.length) return null

    const parametrosRotulos = new URLSearchParams({
      action: "wbgetentities",
      ids: [resultado.id, ...capitaisIds].join("|"),
      props: "labels",
      languages: "pt|en",
      format: "json",
    })
    const rotulos = await obterJson<{
      entities?: Record<string, { labels?: Record<string, { value?: string }> }>
    }>(`${URL_WIKIDATA}?${parametrosRotulos}`)
    const rotuloEntidade = entidadeDados?.labels?.pt?.value
      ?? entidadeDados?.labels?.en?.value
      ?? resultado.label
      ?? entidade
    const capitais = capitaisIds
      .map((id) => rotulos.entities?.[id]?.labels?.pt?.value ?? rotulos.entities?.[id]?.labels?.en?.value)
      .filter((rotulo): rotulo is string => Boolean(rotulo))
    if (!capitais.length) return null

    return {
      titulo: `${rotuloEntidade} — Wikidata`,
      descricao: `Registro estruturado do Wikidata (propriedade P36): ${capitais.map((capital) => `A capital do ${rotuloEntidade} é ${capital}.`).join(" ")}`,
      url: `https://www.wikidata.org/wiki/${resultado.id}`,
      tipo_fonte: "base_dados_aberta",
    }
  } catch (error) {
    console.warn("Propriedade de capital do Wikidata indisponível:", error instanceof Error ? error.name : "erro desconhecido")
    return null
  }
}

async function buscarFontes(afirmacao: string): Promise<Fonte[]> {
  const consultas = gerarConsultas(afirmacao)
  if (!consultas.length) return []

  const termos = palavrasChave(afirmacao)
  const termosRankeados = termosBusca(afirmacao)
  const falaDeEstados = termos.some((termo) =>
    ["estado", "estados", "federativa", "federativas", "distrito", "federal", "uf"].includes(termo))
  const fontesPorId = new Map<number, Pagina>()
  const fontesAdicionais = [
    await buscarUfsIBGE(afirmacao),
    await buscarCapitalWikidata(afirmacao),
  ].filter((fonte): fonte is Fonte => fonte !== null)
  let falhaWikipedia: unknown = null
  for (const consulta of consultas) {
    let paginas: Pagina[]
    try {
      paginas = await buscarPaginasWikipedia(consulta)
    } catch (error) {
      falhaWikipedia = error
      console.warn("Pesquisa na Wikipédia indisponível:", error instanceof Error ? error.name : "erro desconhecido")
      break
    }
    for (const pagina of paginas) {
      const anterior = fontesPorId.get(pagina.pageid)
      if (!anterior || relevancia(pagina, termosRankeados, consultas, falaDeEstados)
        > relevancia(anterior, termosRankeados, consultas, falaDeEstados)) {
        fontesPorId.set(pagina.pageid, pagina)
      }
    }
  }

  const paginas = [...fontesPorId.values()].sort((a, b) =>
    relevancia(b, termosRankeados, consultas, falaDeEstados)
      - relevancia(a, termosRankeados, consultas, falaDeEstados)
    || (a.index ?? 999) - (b.index ?? 999)
    || a.title.localeCompare(b.title))
  await completarExtratos(paginas)
  let listasAdicionadas = 0
  const wikis = paginas
    .filter((pagina) => pagina.extract?.trim())
    .sort((a, b) =>
      relevancia(b, termosRankeados, consultas, falaDeEstados)
        - relevancia(a, termosRankeados, consultas, falaDeEstados)
      || (a.index ?? 999) - (b.index ?? 999)
      || a.title.localeCompare(b.title))
    .filter((pagina) => {
      if (!afirmarNormalizado(pagina.title).startsWith("lista de")) return true
      listasAdicionadas++
      return listasAdicionadas === 1
    })
    .slice(0, MAX_FONTES)
    .map((pagina) => ({
      titulo: pagina.title,
      descricao: pagina.extract!.slice(0, MAX_CARACTERES_EXCERTO),
      url: `https://pt.wikipedia.org/?curid=${pagina.pageid}`,
      tipo_fonte: "enciclopedia",
    }))

  const limiteWikipedia = MAX_FONTES - fontesAdicionais.length
  const fontes = [...fontesAdicionais, ...wikis.slice(0, limiteWikipedia)]
  if (!fontes.length && falhaWikipedia) throw falhaWikipedia
  return fontes
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

  let julgamento: Julgamento | null
  try {
    julgamento = await perguntarIA<Julgamento>(cliente, INSTRUCOES, FORMATO, montarPedido(afirmacao, fontes))
  } catch (error) {
    if (!(error instanceof Anthropic.APIError)) throw error
    console.warn("Análise por IA indisponível; fontes consultadas serão exibidas sem classificação.", error.status)
    return null
  }
  if (!julgamento) return null

  return {
    avaliacoes: julgamento.avaliacoes.filter((a) => a.indice >= 0 && a.indice < fontes.length),
    justificativa_geral: julgamento.justificativa_geral,
  }
}

async function responderPergunta(cliente: Anthropic | null, pergunta: string) {
  const fontes = await buscarFontes(pergunta)
  const semResposta = {
    pergunta,
    encontrada: false,
    resposta: "Não foi possível gerar uma resposta com apoio confirmado nas fontes consultadas.",
    fonte: null as null | { titulo: string; url: string },
    trecho: "",
  }

  if (!cliente) return semResposta
  const pedido = montarPedido(pergunta, fontes).replace(/^<afirmacao>(.*)<\/afirmacao>/, "<pergunta>$1</pergunta>")
  const r = await perguntarIA<RespostaIA>(cliente, INSTRUCOES_PERGUNTA, FORMATO_PERGUNTA, pedido)
  if (!r) return semResposta

  const fonte = r.encontrada ? fontes[r.indice_fonte] : undefined
  if (!fonte) {
    return { ...semResposta, resposta: r.resposta }
  }

  const trechoValido = !!r.trecho.trim() && fonte.descricao.includes(r.trecho.trim())
  return {
    pergunta,
    encontrada: trechoValido,
    resposta: r.resposta,
    fonte: trechoValido ? { titulo: fonte.titulo, url: fonte.url } : null,
    trecho: trechoValido ? r.trecho : "",
  }
}

function montarEvidencias(avaliacoes: Avaliacao[], fontes: Fonte[]) {
  return avaliacoes.map((a) => {
    const fonte = fontes[a.indice]
    const trecho = a.trecho.trim()
    const trechoValido = !!trecho && fonte.descricao.includes(trecho)
    return {
      titulo: fonte.titulo,
      url: fonte.url,
      tipo_fonte: fonte.tipo_fonte ?? "enciclopedia",
      posicao: trechoValido ? a.posicao : "neutra",
      comparada: trechoValido,
      trecho: trechoValido ? trecho : fonte.descricao.slice(0, 200),
      justificativa: trechoValido
        ? a.justificativa
        : trecho
          ? "O trecho atribuído à fonte não pôde ser confirmado no conteúdo consultado."
          : a.justificativa,
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
  const cliente = conexao ? new Anthropic({ ...conexao.opcoes, timeout: 45000, maxRetries: 1 }) : null
  const origem = conexao?.origem ?? null

  const frases = separarFrases(texto)
  const perguntas = frases.filter((f) => f.endsWith("?")).slice(0, MAX_AFIRMACOES)
  const afirmacoesTexto = frases.filter((f) => !f.endsWith("?")).slice(0, MAX_AFIRMACOES)

  try {
    // Afirmações e perguntas são processadas ao mesmo tempo, para caber no limite de 60s do Netlify
    const [afirmacoes, respostas] = await Promise.all([
      Promise.all(
        afirmacoesTexto.map(async (frase, i) => {
          const fontes = await buscarFontes(frase)
          const julgamento = cliente ? await avaliarFontes(cliente, frase, fontes) : null
          const avaliacoes = julgamento?.avaliacoes ?? fontes.map((_, indice) => ({
            indice,
            posicao: "neutra" as const,
            trecho: "",
            justificativa: cliente
              ? "Fonte consultada, mas não classificada porque a análise por IA não ficou disponível."
              : "Fonte consultada, mas não classificada porque a análise por IA não está configurada.",
          }))
          const avaliados = new Set(avaliacoes.map((avaliacao) => avaliacao.indice))
          fontes.forEach((_, indice) => {
            if (!avaliados.has(indice)) {
              avaliacoes.push({
                indice,
                posicao: "neutra",
                trecho: "",
                justificativa: "Fonte consultada, mas não foi possível validar uma classificação para ela.",
              })
            }
          })

          return {
            id: i + 1,
            texto: frase,
            status_verificacao: "concluida",
            fontes,
            evidencias: montarEvidencias(avaliacoes, fontes),
            justificativa_geral: julgamento?.justificativa_geral
              ?? (cliente ? "A análise automática não ficou disponível; as fontes foram consultadas, mas não classificadas." : "Apenas os resumos das fontes foram consultados. Configure uma chave de IA para classificá-los."),
            metodo: julgamento ? "ia" : "sem_ia",
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
      metodo: cliente ? "ia" : "sem_ia",
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
