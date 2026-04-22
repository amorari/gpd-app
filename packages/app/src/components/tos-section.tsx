import { Show, createSignal } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { Checkbox } from "@opencode-ai/ui/checkbox"
import { ScrollView } from "@opencode-ai/ui/scroll-view"
import { useLanguage } from "@/context/language"
import { TOS_TEXT } from "./tos-content"

/**
 * Reusable TOS acceptance UI — scrollable text, agree checkbox, Accept button.
 * Consumed both by the welcome-screen first-run flow (with an optional Back
 * button) and by the version-bump gate (Back hidden, Cancel quits).
 *
 * The component is view-only; it does NOT call the server. Callers supply
 * `onAccept` which must POST to /gpd/tos-accept AND persist the accepted
 * version locally. On error, callers set `error` and keep the component
 * mounted.
 */
export function TosSection(props: {
  onAccept: () => void | Promise<void>
  onBack?: () => void
  /** Quit-the-app button (version-bump mode). Hidden when undefined. */
  onCancel?: () => void | Promise<void>
  submitting?: boolean
  error?: string
}) {
  const language = useLanguage()
  const [agreed, setAgreed] = createSignal(false)

  async function handleAccept() {
    if (!agreed() || props.submitting) return
    await props.onAccept()
  }

  return (
    <div class="flex flex-col items-center w-full max-w-2xl">
      <h2
        class="text-text-strong"
        style={{
          "font-size": "var(--font-size-x-large)",
          "font-weight": "var(--font-weight-medium)",
        }}
      >
        {language.t("welcome.tos.title")}
      </h2>
      <p class="mt-1.5 text-14-regular text-text-weak">
        {language.t("welcome.tos.intro")}
      </p>
      <ScrollView
        class="mt-6 w-full border border-border-base rounded-md"
        style={{ "max-height": "320px" }}
      >
        <div class="p-4 text-13-regular text-text-base whitespace-pre-wrap">
          {TOS_TEXT}
        </div>
      </ScrollView>

      <div class="mt-5 w-full flex items-start gap-3">
        <Checkbox
          checked={agreed()}
          onChange={(checked) => setAgreed(checked)}
          disabled={props.submitting}
        >
          {language.t("welcome.tos.checkbox")}
        </Checkbox>
      </div>

      <Show when={props.error}>
        <p class="mt-4 w-full text-13-regular text-text-danger">{props.error}</p>
      </Show>

      <div class="mt-6 w-full flex flex-col gap-3">
        <Button
          type="button"
          size="large"
          variant="primary"
          class="w-full"
          disabled={!agreed() || props.submitting}
          onClick={handleAccept}
        >
          {language.t("welcome.tos.accept")}
        </Button>
        <Show when={props.onBack}>
          <Button
            type="button"
            size="large"
            variant="secondary"
            class="w-full"
            disabled={props.submitting}
            onClick={props.onBack}
          >
            {language.t("welcome.tos.back")}
          </Button>
        </Show>
        <Show when={props.onCancel}>
          <Button
            type="button"
            size="large"
            variant="ghost"
            class="w-full"
            disabled={props.submitting}
            onClick={props.onCancel}
          >
            {language.t("welcome.tos.cancel")}
          </Button>
        </Show>
      </div>
    </div>
  )
}
