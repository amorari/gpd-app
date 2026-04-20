export type ConfigInvalidError = {
  name: "ConfigInvalidError"
  data: {
    path?: string
    message?: string
    issues?: Array<{ message: string; path: string[] }>
  }
}

export type ProviderModelNotFoundError = {
  name: "ProviderModelNotFoundError"
  data: {
    providerID: string
    modelID: string
    suggestions?: string[]
  }
}

export type UnknownError = {
  name: "UnknownError"
  data: {
    message: string
  }
}

type Translator = (key: string, vars?: Record<string, string | number>) => string

function tr(translator: Translator | undefined, key: string, text: string, vars?: Record<string, string | number>) {
  if (!translator) return text
  const out = translator(key, vars)
  if (!out || out === key) return text
  return out
}

export function formatServerError(error: unknown, translate?: Translator, fallback?: string) {
  if (isConfigInvalidErrorLike(error)) return parseReadableConfigInvalidError(error, translate)
  if (isProviderModelNotFoundErrorLike(error)) return parseReadableProviderModelNotFoundError(error, translate)
  if (isUnknownErrorLike(error)) return parseReadableUnknownError(error)
  if (isPermissionError(error))
    return tr(
      translate,
      "error.chain.permissionDenied",
      "GPD needs permission to access this folder. Open System Settings → Privacy & Security → Files and Folders to grant access.",
    )
  if (error instanceof Error && error.message) return error.message
  if (typeof error === "string" && error) return error
  if (fallback) return fallback
  return tr(translate, "error.chain.unknown", "Unknown error")
}

function isPermissionError(error: unknown): boolean {
  if (error instanceof Error) return error.message.includes("EPERM") || error.message.includes("operation not permitted")
  if (typeof error === "object" && error !== null) {
    const o = error as Record<string, unknown>
    // Check top-level message field
    const msg = String(o.message ?? "")
    if (msg.includes("EPERM") || msg.includes("operation not permitted")) return true
    // Check nested data.message field (UnknownError shape from ErrorMiddleware)
    if (typeof o.data === "object" && o.data !== null) {
      const dataMsg = String((o.data as Record<string, unknown>).message ?? "")
      if (dataMsg.includes("EPERM") || dataMsg.includes("operation not permitted")) return true
    }
    return false
  }
  if (typeof error === "string") return error.includes("EPERM") || error.includes("operation not permitted")
  return false
}

function isConfigInvalidErrorLike(error: unknown): error is ConfigInvalidError {
  if (typeof error !== "object" || error === null) return false
  const o = error as Record<string, unknown>
  return o.name === "ConfigInvalidError" && typeof o.data === "object" && o.data !== null
}

function isProviderModelNotFoundErrorLike(error: unknown): error is ProviderModelNotFoundError {
  if (typeof error !== "object" || error === null) return false
  const o = error as Record<string, unknown>
  return o.name === "ProviderModelNotFoundError" && typeof o.data === "object" && o.data !== null
}

function isUnknownErrorLike(error: unknown): error is UnknownError {
  if (typeof error !== "object" || error === null) return false
  const o = error as Record<string, unknown>
  if (o.name !== "UnknownError") return false
  if (typeof o.data !== "object" || o.data === null) return false
  return typeof (o.data as Record<string, unknown>).message === "string"
}

function parseReadableUnknownError(error: UnknownError): string {
  // Strip stack trace: take only the first line of the message
  return error.data.message.split("\n")[0].trim()
}

export function parseReadableConfigInvalidError(errorInput: ConfigInvalidError, translator?: Translator) {
  const file = errorInput.data.path && errorInput.data.path !== "config" ? errorInput.data.path : "config"
  const detail = errorInput.data.message?.trim() ?? ""
  const issues = (errorInput.data.issues ?? [])
    .map((issue) => {
      const msg = issue.message.trim()
      if (!issue.path.length) return msg
      return `${issue.path.join(".")}: ${msg}`
    })
    .filter(Boolean)
  const msg = issues.length ? issues.join("\n") : detail
  if (!msg) return tr(translator, "error.chain.configInvalid", `Config file at ${file} is invalid`, { path: file })
  return tr(translator, "error.chain.configInvalidWithMessage", `Config file at ${file} is invalid: ${msg}`, {
    path: file,
    message: msg,
  })
}

function parseReadableProviderModelNotFoundError(errorInput: ProviderModelNotFoundError, translator?: Translator) {
  const p = errorInput.data.providerID.trim()
  const m = errorInput.data.modelID.trim()
  const list = (errorInput.data.suggestions ?? []).map((v) => v.trim()).filter(Boolean)
  const body = tr(translator, "error.chain.modelNotFound", `Model not found: ${p}/${m}`, { provider: p, model: m })
  const tail = tr(translator, "error.chain.checkConfig", "Check your GPD settings for correct provider/model names")
  if (list.length) {
    const suggestions = list.slice(0, 5).join(", ")
    return [body, tr(translator, "error.chain.didYouMean", `Did you mean: ${suggestions}`, { suggestions }), tail].join(
      "\n",
    )
  }
  return [body, tail].join("\n")
}
