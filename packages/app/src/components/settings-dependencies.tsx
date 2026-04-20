import { Component, For, Show, createMemo, createResource, createSignal } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { Icon } from "@opencode-ai/ui/icon"
import { Tag } from "@opencode-ai/ui/tag"
import { showToast } from "@opencode-ai/ui/toast"
import { useLanguage } from "@/context/language"
import { usePlatform } from "@/context/platform"
import { useServer } from "@/context/server"
import { SettingsList } from "./settings-list"

type Status = "ok" | "warn" | "fail"

type InstallHint = {
  macos?: string
  windows?: string
  linux?: string
  url?: string
}

type Check = {
  id: string
  label: string
  status: Status
  category: "runtime" | "core" | "optional"
  details?: string
  version?: string
  path?: string
  installHint?: InstallHint
}

type DoctorResponse = {
  overall: Status
  summary: { ok: number; warn: number; fail: number; total: number }
  checks: Check[]
  rawOutput?: string
  pythonExecutable?: string
}

type PresetStatus = {
  id: string
  label: string
  description: string
  status: Status
  missing: string[]
}

type PresetsResponse = {
  presets: PresetStatus[]
  rawOutput?: string
}

function statusIcon(status: Status) {
  if (status === "ok") return "circle-check"
  if (status === "warn") return "warning"
  return "circle-x"
}

function statusClass(status: Status) {
  if (status === "ok") return "text-icon-success-base"
  if (status === "warn") return "text-icon-warning-base"
  return "text-text-danger-base"
}

export const SettingsDependencies: Component = () => {
  const language = useLanguage()
  const platform = usePlatform()
  const server = useServer()

  const [refreshKey, setRefreshKey] = createSignal(0)
  const [detailsOpen, setDetailsOpen] = createSignal(false)

  const currentServer = () => server.current
  const auth = createMemo(() => {
    const s = currentServer()
    if (!s) return undefined
    const pw = s.http.password
    if (!pw) return undefined
    return `Basic ${btoa(`${s.http.username ?? "opencode"}:${pw}`)}`
  })

  async function call<T>(path: string): Promise<T> {
    const s = currentServer()
    if (!s) throw new Error(language.t("error.globalSDK.noServerAvailable"))
    const headers: Record<string, string> = { Accept: "application/json" }
    const a = auth()
    if (a) headers.Authorization = a
    const fetcher = platform.fetch ?? fetch
    const res = await fetcher(new URL(path, s.http.url).toString(), { headers })
    if (!res.ok) {
      throw new Error(`${res.status} ${res.statusText}`)
    }
    return (await res.json()) as T
  }

  const [doctor] = createResource<DoctorResponse, number>(refreshKey, async () => {
    try {
      return await call<DoctorResponse>("/health/doctor")
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      return {
        overall: "fail" as const,
        summary: { ok: 0, warn: 0, fail: 1, total: 1 },
        checks: [
          {
            id: "python",
            label: "Python",
            status: "fail" as const,
            category: "runtime" as const,
            details: message,
          },
        ],
      }
    }
  })

  const [presets] = createResource<PresetsResponse, number>(refreshKey, async () => {
    try {
      return await call<PresetsResponse>("/health/presets")
    } catch {
      return { presets: [] }
    }
  })

  const runtimeChecks = createMemo(() => doctor()?.checks.filter((c) => c.category === "runtime") ?? [])
  const coreChecks = createMemo(() => doctor()?.checks.filter((c) => c.category === "core") ?? [])
  const optionalChecks = createMemo(() => doctor()?.checks.filter((c) => c.category === "optional") ?? [])

  const refetch = () => {
    setRefreshKey(refreshKey() + 1)
  }

  const confirmAndRun = async (
    toolLabel: string,
    run: () => Promise<{ launched: boolean; message: string }>,
  ) => {
    const ok = window.confirm(
      language.t("settings.dependencies.confirm.install", { tool: toolLabel }),
    )
    if (!ok) return
    try {
      const result = await run()
      showToast({
        variant: result.launched ? "success" : undefined,
        icon: result.launched ? "circle-check" : undefined,
        title: language.t("settings.dependencies.toast.installLaunched", { tool: toolLabel }),
        description: result.message,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast({
        title: language.t("settings.dependencies.toast.installFailed", { tool: toolLabel }),
        description: message,
      })
    }
  }

  const copyHint = async (hint: string) => {
    const writer = platform.writeClipboard
      ? platform.writeClipboard
      : async (text: string) => {
          await navigator.clipboard.writeText(text)
        }
    try {
      await writer(hint)
      showToast({
        variant: "success",
        icon: "circle-check",
        title: language.t("settings.dependencies.toast.copied"),
        description: hint,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      showToast({ title: language.t("common.requestFailed"), description: message })
    }
  }

  const openUrl = (url: string) => {
    try {
      platform.openLink(url)
    } catch {
      window.open(url, "_blank", "noopener,noreferrer")
    }
  }

  const installAction = (check: Check) => {
    const hint = check.installHint
    if (!hint) return null

    const os = platform.os

    // macOS: xcode-select for git, or URL open for others.
    if (os === "macos") {
      if (check.id === "git" && platform.installGitMacos) {
        return (
          <Button
            size="small"
            variant="secondary"
            icon="download"
            onClick={() => void confirmAndRun(check.label, () => platform.installGitMacos!())}
          >
            {language.t("settings.dependencies.install")}
          </Button>
        )
      }
      if (hint.macos) {
        return (
          <Button size="small" variant="secondary" icon="copy" onClick={() => void copyHint(hint.macos!)}>
            {language.t("settings.dependencies.copyCommand")}
          </Button>
        )
      }
    }

    // Windows: winget for git, copy for others.
    if (os === "windows") {
      if (check.id === "git" && platform.installGitWindows) {
        return (
          <Button
            size="small"
            variant="secondary"
            icon="download"
            onClick={() => void confirmAndRun(check.label, () => platform.installGitWindows!())}
          >
            {language.t("settings.dependencies.install")}
          </Button>
        )
      }
      if (hint.windows) {
        return (
          <Button size="small" variant="secondary" icon="copy" onClick={() => void copyHint(hint.windows!)}>
            {language.t("settings.dependencies.copyCommand")}
          </Button>
        )
      }
    }

    // Linux: never execute. Only copy.
    if (os === "linux" && hint.linux) {
      return (
        <Button size="small" variant="secondary" icon="copy" onClick={() => void copyHint(hint.linux!)}>
          {language.t("settings.dependencies.copyCommand")}
        </Button>
      )
    }

    if (hint.url) {
      return (
        <Button size="small" variant="secondary" icon="square-arrow-top-right" onClick={() => openUrl(hint.url!)}>
          {language.t("settings.dependencies.learnMore")}
        </Button>
      )
    }

    return null
  }

  const CheckRow: Component<{ check: Check }> = (props) => (
    <div class="flex flex-wrap items-start justify-between gap-4 min-h-16 py-3 border-b border-border-weak-base last:border-none">
      <div class="flex items-start gap-3 min-w-0 flex-1">
        <span class={`mt-0.5 shrink-0 ${statusClass(props.check.status)}`}>
          <Icon name={statusIcon(props.check.status)} />
        </span>
        <div class="flex flex-col min-w-0 gap-0.5">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-14-medium text-text-strong">{props.check.label}</span>
            <Show when={props.check.version}>
              <Tag>{props.check.version}</Tag>
            </Show>
          </div>
          <Show when={props.check.details}>
            <span class="text-12-regular text-text-weak break-all">{props.check.details}</span>
          </Show>
          <Show when={props.check.path}>
            <span class="text-11-regular text-text-weak font-mono break-all">{props.check.path}</span>
          </Show>
        </div>
      </div>
      <Show when={props.check.status !== "ok"}>
        <div class="shrink-0">{installAction(props.check)}</div>
      </Show>
    </div>
  )

  return (
    <div class="flex flex-col h-full overflow-y-auto no-scrollbar px-4 pb-10 sm:px-10 sm:pb-10">
      <div class="sticky top-0 z-10 bg-[linear-gradient(to_bottom,var(--surface-stronger-non-alpha)_calc(100%_-_24px),transparent)]">
        <div class="flex flex-col gap-1 pt-6 pb-8 max-w-[720px]">
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <h2 class="text-16-medium text-text-strong">{language.t("settings.dependencies.title")}</h2>
            <Button
              size="small"
              variant="secondary"
              icon="reset"
              disabled={doctor.loading}
              onClick={refetch}
            >
              {doctor.loading
                ? language.t("settings.dependencies.checking")
                : language.t("settings.dependencies.checkNow")}
            </Button>
          </div>
          <Show when={doctor()}>
            {(d) => (
              <div class="flex items-center gap-3 text-12-regular text-text-weak">
                <span class={statusClass(d().overall)}>
                  <Icon name={statusIcon(d().overall)} size="small" />
                </span>
                <span>
                  {language.t("settings.dependencies.summary", {
                    ok: d().summary.ok,
                    warn: d().summary.warn,
                    fail: d().summary.fail,
                    total: d().summary.total,
                  })}
                </span>
              </div>
            )}
          </Show>
        </div>
      </div>

      <div class="flex flex-col gap-8 max-w-[720px]">
        <Section title={language.t("settings.dependencies.runtimeStatus")}>
          <Show
            when={runtimeChecks().length > 0}
            fallback={
              <div class="py-4 text-14-regular text-text-weak">
                {doctor.loading ? language.t("settings.dependencies.loading") : language.t("settings.dependencies.noData")}
              </div>
            }
          >
            <SettingsList>
              <For each={runtimeChecks()}>{(check) => <CheckRow check={check} />}</For>
            </SettingsList>
          </Show>
        </Section>

        <Section title={language.t("settings.dependencies.coreRequirements")}>
          <Show
            when={coreChecks().length > 0}
            fallback={
              <div class="py-4 text-14-regular text-text-weak">
                {doctor.loading ? language.t("settings.dependencies.loading") : language.t("settings.dependencies.noData")}
              </div>
            }
          >
            <SettingsList>
              <For each={coreChecks()}>{(check) => <CheckRow check={check} />}</For>
            </SettingsList>
          </Show>
        </Section>

        <Section title={language.t("settings.dependencies.optionalFeatures")}>
          <Show
            when={optionalChecks().length > 0}
            fallback={
              <div class="py-4 text-14-regular text-text-weak">
                {doctor.loading ? language.t("settings.dependencies.loading") : language.t("settings.dependencies.noData")}
              </div>
            }
          >
            <SettingsList>
              <For each={optionalChecks()}>{(check) => <CheckRow check={check} />}</For>
            </SettingsList>
          </Show>
        </Section>

        <Section title={language.t("settings.dependencies.workflowReadiness")}>
          <Show
            when={presets()?.presets && presets()!.presets.length > 0}
            fallback={
              <div class="py-4 text-14-regular text-text-weak">
                {presets.loading
                  ? language.t("settings.dependencies.loading")
                  : language.t("settings.dependencies.noData")}
              </div>
            }
          >
            <SettingsList>
              <For each={presets()!.presets}>
                {(preset) => (
                  <div class="flex flex-wrap items-start justify-between gap-4 min-h-16 py-3 border-b border-border-weak-base last:border-none">
                    <div class="flex items-start gap-3 min-w-0 flex-1">
                      <span class={`mt-0.5 shrink-0 ${statusClass(preset.status)}`}>
                        <Icon name={statusIcon(preset.status)} />
                      </span>
                      <div class="flex flex-col min-w-0 gap-0.5">
                        <span class="text-14-medium text-text-strong">{preset.label}</span>
                        <span class="text-12-regular text-text-weak">{preset.description}</span>
                        <Show when={preset.missing.length > 0}>
                          <span class="text-12-regular text-icon-warning-base">
                            {language.t("settings.dependencies.missing", {
                              tools: preset.missing.join(", "),
                            })}
                          </span>
                        </Show>
                      </div>
                    </div>
                  </div>
                )}
              </For>
            </SettingsList>
          </Show>
        </Section>

        <Show when={doctor()?.rawOutput}>
          {(raw) => (
            <div class="flex flex-col gap-2">
              <button
                type="button"
                class="flex items-center gap-2 text-14-medium text-text-interactive-base text-left cursor-pointer"
                onClick={() => setDetailsOpen(!detailsOpen())}
              >
                <Icon name={detailsOpen() ? "chevron-down" : "chevron-right"} size="small" />
                {language.t("settings.dependencies.details")}
              </button>
              <Show when={detailsOpen()}>
                <pre class="text-11-regular text-text-weak font-mono bg-surface-base border border-border-weak-base p-3 rounded whitespace-pre-wrap break-all max-h-96 overflow-auto">
                  {raw()}
                </pre>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </div>
  )
}

const Section: Component<{ title: string; children: any }> = (props) => (
  <div class="flex flex-col gap-1">
    <h3 class="text-14-medium text-text-strong pb-2">{props.title}</h3>
    {props.children}
  </div>
)
