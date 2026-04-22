import { createSignal } from "solid-js"
import { useLanguage } from "@/context/language"
import { usePlatform } from "@/context/platform"
import { postTosAccept } from "@/lib/tos-accept"
import {
  CURRENT_TOS_VERSION,
  PRIVACY_TEXT_SHA256,
  TOS_ACCEPTED_VERSION_STORAGE_KEY,
  TOS_TEXT_SHA256,
} from "./tos-content"
import { TosSection } from "./tos-section"

/**
 * Full-viewport blocker shown when a user's already-saved key is valid but
 * their cached TOS acceptance is older than CURRENT_TOS_VERSION.
 *
 * "I agree" → POST with the user's existing key, bump the localStorage
 *             version, call `onAccepted()` so SetupGate unmounts this and
 *             falls through to the main IDE.
 *
 * "Quit" → `platform.quit()` (desktop) or `window.close()` fallback (web).
 *          No sign-out path; declining updated terms terminates the session.
 *          The saved key stays in auth.json so the user can re-launch and
 *          try again, but they can't use the app without agreeing.
 */
export function TosUpgradeGate(props: {
  /** LiteLLM virtual key read from auth.json via platform.readGpdKey().
   *  Fetched on-demand, not cached in WebKit/WebView2 localStorage. */
  apiKey: string
  /** Called on successful server-side record. */
  onAccepted: () => void
  /** True when user previously accepted a now-superseded TOS version; false
   *  when they have an auth.json but never accepted any TOS (CLI-install
   *  path, or the TOS system itself is new). Drives the title/intro copy —
   *  "Updated" is misleading for users who have never agreed. */
  isUpgrade?: boolean
}) {
  const language = useLanguage()
  const platform = usePlatform()
  const [error, setError] = createSignal<string | undefined>()
  const [submitting, setSubmitting] = createSignal(false)

  async function handleAccept(viewedInFull: boolean) {
    setError(undefined)
    setSubmitting(true)
    try {
      await postTosAccept({
        key: props.apiKey,
        tosVersion: CURRENT_TOS_VERSION,
        tosTextSha256: TOS_TEXT_SHA256,
        privacyTextSha256: PRIVACY_TEXT_SHA256,
        appVersion: platform.version,
        viewedInFull,
      })
      localStorage.setItem(TOS_ACCEPTED_VERSION_STORAGE_KEY, CURRENT_TOS_VERSION)
      props.onAccepted()
    } catch (e) {
      setError(
        e instanceof Error
          ? `${language.t("welcome.tos.errorAcceptFailed")} (${e.message})`
          : language.t("welcome.tos.errorAcceptFailed"),
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCancel() {
    // Quit the app. On desktop this is app.exit(0); on web it closes the
    // window (effective only if the window was opened by script, but this
    // code path only ships in the Tauri app — web build is for ops tools).
    try {
      if (platform.quit) {
        await platform.quit()
      } else {
        window.close()
      }
    } catch {
      // Last-ditch: force-reload a blank page so the user can't continue.
      window.location.replace("about:blank")
    }
  }

  return (
    <div class="h-dvh w-screen flex items-center justify-center bg-background-base p-6 overflow-auto">
      <div class="flex flex-col items-center w-full max-w-2xl">
        <h1
          class="text-text-strong"
          style={{
            "font-size": "var(--font-size-x-large)",
            "font-weight": "var(--font-weight-medium)",
          }}
        >
          {language.t(props.isUpgrade ? "welcome.tos.upgradeTitle" : "welcome.tos.firstTimeTitle")}
        </h1>
        <p class="mt-1.5 text-14-regular text-text-weak">
          {language.t(props.isUpgrade ? "welcome.tos.upgradeIntro" : "welcome.tos.firstTimeIntro")}
        </p>
        <div class="mt-6 w-full">
          <TosSection
            onAccept={handleAccept}
            onCancel={handleCancel}
            submitting={submitting()}
            error={error()}
            hideHeading
          />
        </div>
      </div>
    </div>
  )
}
