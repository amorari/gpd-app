import { For, Show } from "solid-js"
import { useLanguage } from "@/context/language"
import type { TexDiagnostic } from "@/context/platform"

/**
 * Renders parsed LaTeX errors + warnings for the Build pane. Line numbers
 * are clickable and call back into the parent, which can scroll the
 * editor tab to that line.
 */
export function TexErrorList(props: {
  errors: TexDiagnostic[]
  warnings: TexDiagnostic[]
  onNavigate?: (diag: TexDiagnostic) => void
}) {
  const language = useLanguage()

  const hasAny = () => props.errors.length > 0 || props.warnings.length > 0

  return (
    <div class="flex flex-col gap-2 text-12-regular" data-component="tex-error-list">
      <Show
        when={hasAny()}
        fallback={
          <div class="px-3 py-4 text-text-weak">
            {language.t("tex.error.none")}
          </div>
        }
      >
        <Show when={props.errors.length > 0}>
          <div class="flex flex-col gap-1">
            <div class="px-3 pt-2 text-text-weak uppercase tracking-wide">
              {language.t("tex.error.errors")} ({props.errors.length})
            </div>
            <For each={props.errors}>
              {(diag) => <DiagnosticRow diag={diag} onNavigate={props.onNavigate} />}
            </For>
          </div>
        </Show>
        <Show when={props.warnings.length > 0}>
          <div class="flex flex-col gap-1">
            <div class="px-3 pt-2 text-text-weak uppercase tracking-wide">
              {language.t("tex.error.warnings")} ({props.warnings.length})
            </div>
            <For each={props.warnings}>
              {(diag) => <DiagnosticRow diag={diag} onNavigate={props.onNavigate} />}
            </For>
          </div>
        </Show>
      </Show>
    </div>
  )
}

function DiagnosticRow(props: {
  diag: TexDiagnostic
  onNavigate?: (diag: TexDiagnostic) => void
}) {
  const severityClass = () =>
    props.diag.severity === "error" ? "text-text-error" : "text-text-weak"

  const clickable = () => props.onNavigate && props.diag.line !== null

  return (
    <div
      class="px-3 py-1.5 flex items-start gap-2 hover:bg-background-weaker-base"
      classList={{ "cursor-pointer": clickable() }}
      onClick={() => {
        if (clickable()) props.onNavigate?.(props.diag)
      }}
    >
      <div class={severityClass() + " shrink-0 mt-0.5"}>
        {props.diag.severity === "error" ? "●" : "○"}
      </div>
      <div class="min-w-0 flex-1">
        <div class="whitespace-pre-wrap break-words">{props.diag.message}</div>
        <Show when={props.diag.file || props.diag.line !== null}>
          <div class="text-text-weaker mt-0.5">
            <Show when={props.diag.file}>
              <span>{props.diag.file}</span>
            </Show>
            <Show when={props.diag.line !== null}>
              <span>:{props.diag.line}</span>
            </Show>
          </div>
        </Show>
      </div>
    </div>
  )
}
