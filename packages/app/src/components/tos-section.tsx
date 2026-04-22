import { Show, createSignal } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { Checkbox } from "@opencode-ai/ui/checkbox"
import { useLanguage } from "@/context/language"
import { TOS_TEXT } from "./tos-content"

/**
 * Reusable TOS acceptance UI — scrollable text, agree checkbox, Accept button.
 * Consumed both by the welcome-screen first-run flow (with an optional Back
 * button) and by the version-bump gate (Back hidden, Cancel quits).
 *
 * Enforces scroll-to-bottom before the agreement checkbox is enabled. This
 * produces the `viewedInFull` flag passed back to the caller via onAccept
 * — stored server-side so a Specht-v.-Netscape-style "I never saw clause 7"
 * defence has a direct counter-record. Small epsilon (~16px) lets layout
 * wiggle pass for content that fits without scrolling.
 *
 * The component is view-only for POSTs; it does NOT call the server. Callers
 * supply `onAccept(viewedInFull)` which must POST to /gpd/tos-accept AND
 * persist the accepted version locally. On error, callers set `error` and
 * keep the component mounted.
 */
const SCROLL_BOTTOM_EPSILON_PX = 16

export function TosSection(props: {
  onAccept: (viewedInFull: boolean) => void | Promise<void>
  onBack?: () => void
  /** Quit-the-app button (version-bump mode). Hidden when undefined. */
  onCancel?: () => void | Promise<void>
  submitting?: boolean
  error?: string
}) {
  const language = useLanguage()
  const [agreed, setAgreed] = createSignal(false)
  // Track whether the user scrolled (or whether the content fits without
  // scrolling at all — also counts as "seen in full"). Initially false; set
  // true on scrollend OR on mount if scrollHeight ≤ clientHeight.
  const [scrolledToBottom, setScrolledToBottom] = createSignal(false)

  let scrollHost: HTMLDivElement | undefined

  function handleScroll(e: Event) {
    const el = e.currentTarget as HTMLDivElement
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - SCROLL_BOTTOM_EPSILON_PX) {
      setScrolledToBottom(true)
    }
  }

  function mountScrollHost(el: HTMLDivElement) {
    scrollHost = el
    // If content already fits, treat as seen-in-full. Defer to next tick so
    // the browser has laid out the children first.
    queueMicrotask(() => {
      if (!scrollHost) return
      if (scrollHost.scrollHeight - scrollHost.clientHeight <= SCROLL_BOTTOM_EPSILON_PX) {
        setScrolledToBottom(true)
      }
    })
  }

  async function handleAccept() {
    if (!agreed() || !scrolledToBottom() || props.submitting) return
    await props.onAccept(scrolledToBottom())
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
      <div
        ref={mountScrollHost}
        onScroll={handleScroll}
        class="mt-6 w-full overflow-y-auto border border-border-base rounded-md"
        style={{ "max-height": "320px" }}
      >
        <div class="p-4 text-13-regular text-text-base whitespace-pre-wrap">
          {TOS_TEXT}
        </div>
      </div>

      <Show when={!scrolledToBottom()}>
        <p class="mt-3 w-full text-13-regular text-text-weak">
          {language.t("welcome.tos.scrollHint")}
        </p>
      </Show>

      <div class="mt-5 w-full flex items-start gap-3">
        <Checkbox
          checked={agreed()}
          onChange={(checked) => setAgreed(checked)}
          disabled={props.submitting || !scrolledToBottom()}
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
          disabled={!agreed() || !scrolledToBottom() || props.submitting}
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
