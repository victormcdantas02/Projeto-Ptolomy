// Versão online (Netlify) do CRUD de análises (main.py + banco.py).
// Em vez do SQLite, cada análise fica guardada no Netlify Blobs, com o id como chave.
import { getStore } from "@netlify/blobs"
import type { Config, Context } from "@netlify/functions"

const STATUS_VALIDOS = ["não verificado", "confirmado", "falso"]

type Analise = {
  id: number
  usuario_id: string
  texto: string
  ia_origem: string
  resultado: unknown
  fontes: unknown
  status_validacao: string
  observacao: string
  data: string
  conclusao_usuario: string
  fontes_consultadas: string[]
}

const loja = () => getStore({ name: "analises", consistency: "strong" })
const erro = (status: number, detail: string) => Response.json({ detail }, { status })
const CONCLUSOES_USUARIO_VALIDAS = ["", "confirmada", "contradita", "evidencias_insuficientes", "necessita_pesquisa"]

async function lerCorpo(req: Request): Promise<Record<string, unknown> | null> {
  try {
    const corpo = await req.json()
    return corpo && typeof corpo === "object" ? corpo : null
  } catch {
    return null
  }
}

async function listar(usuarioId: string): Promise<Analise[]> {
  const analises = loja()
  const { blobs } = await analises.list()
  const todas = await Promise.all(blobs.map((b) => analises.get(b.key, { type: "json" }) as Promise<Analise | null>))
  return todas
    .filter((a): a is Analise => a !== null)
    .filter((a) => !usuarioId || a.usuario_id === usuarioId)
    .sort((a, b) => b.id - a.id)
}

async function cadastrar(req: Request): Promise<Response> {
  const dados = await lerCorpo(req)
  if (!dados) return erro(400, "Envie os dados da análise em JSON")

  const texto = String(dados.texto ?? "")
  const iaOrigem = String(dados.ia_origem ?? "")

  if (texto.length < 15 || texto.length > 2000) return erro(422, "O texto precisa ter entre 15 e 2000 caracteres")
  if (iaOrigem === "" || iaOrigem.length > 40) return erro(422, "Informe qual IA gerou o texto")

  const analises = loja()

  // O id é o momento do cadastro em milissegundos; se repetir, tenta o seguinte
  for (let tentativa = 0; tentativa < 5; tentativa++) {
    const id = Date.now() + tentativa
    const analise: Analise = {
      id,
      usuario_id: String(dados.usuario_id ?? ""),
      texto,
      ia_origem: iaOrigem,
      resultado: dados.resultado ?? {},
      fontes: dados.fontes ?? [],
      status_validacao: "não verificado",
      observacao: "",
      data: new Date().toISOString().slice(0, 19),
      conclusao_usuario: "",
      fontes_consultadas: [],
    }
    const { modified } = await analises.setJSON(String(id), analise, { onlyIfNew: true })
    if (modified) return Response.json(analise, { status: 201 })
  }

  return erro(409, "Não foi possível salvar a análise. Tente de novo.")
}

export default async (req: Request, context: Context) => {
  const id = context.params.id

  // /analises
  if (!id) {
    if (req.method === "GET") {
      const usuarioId = new URL(req.url).searchParams.get("usuario_id") ?? ""
      return Response.json(await listar(usuarioId))
    }
    if (req.method === "POST") return cadastrar(req)
    return erro(405, "Método não permitido")
  }

  // /analises/{id}
  if (!/^\d+$/.test(id)) return erro(404, "Análise não encontrada")

  const analises = loja()
  const atual = (await analises.get(id, { type: "json" })) as Analise | null
  if (atual === null) return erro(404, "Análise não encontrada")

  if (req.method === "GET") return Response.json(atual)

  if (req.method === "PUT") {
    const dados = await lerCorpo(req)
    if (!dados) return erro(400, "Envie os dados em JSON")

    const status = String(dados.status_validacao ?? "")
    const observacao = String(dados.observacao ?? "")
    const conclusaoUsuario = dados.conclusao_usuario
    const fontesConsultadas = dados.fontes_consultadas

    if (!STATUS_VALIDOS.includes(status)) return erro(400, "Status inválido")
    if (observacao.length > 500) return erro(422, "A observação pode ter no máximo 500 caracteres")
    if (conclusaoUsuario !== undefined && (typeof conclusaoUsuario !== "string" || !CONCLUSOES_USUARIO_VALIDAS.includes(conclusaoUsuario))) {
      return erro(400, "Conclusão do usuário inválida")
    }
    if (fontesConsultadas !== undefined && (
      !Array.isArray(fontesConsultadas)
      || fontesConsultadas.length > 20
      || fontesConsultadas.some((fonte) => typeof fonte !== "string" || fonte.length > 100)
    )) {
      return erro(422, "Lista de fontes consultadas inválida")
    }

    const atualizada = {
      ...atual,
      status_validacao: status,
      observacao,
      ...(conclusaoUsuario !== undefined ? { conclusao_usuario: conclusaoUsuario } : {}),
      ...(fontesConsultadas !== undefined ? { fontes_consultadas: fontesConsultadas } : {}),
    }
    await analises.setJSON(id, atualizada)
    return Response.json(atualizada)
  }

  if (req.method === "DELETE") {
    await analises.delete(id)
    return new Response(null, { status: 204 })
  }

  return erro(405, "Método não permitido")
}

export const config: Config = {
  path: ["/analises", "/analises/:id"],
}
