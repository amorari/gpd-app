import { createSignal } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { TextField } from "@opencode-ai/ui/text-field"
import { useLanguage } from "@/context/language"

export function WelcomeScreen(props: { onComplete: (apiKey: string) => void | Promise<void> }) {
  const language = useLanguage()
  const [apiKey, setApiKey] = createSignal("")
  const [error, setError] = createSignal<string | undefined>()
  const [submitting, setSubmitting] = createSignal(false)

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault()
    const key = apiKey().trim()
    if (!key) {
      setError(language.t("welcome.apiKey.required"))
      return
    }
    setError(undefined)
    setSubmitting(true)
    try {
      await props.onComplete(key)
    } catch (e) {
      setError(String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div class="h-dvh w-screen flex items-center justify-center bg-background-base p-6">
      <div class="flex flex-col items-center w-full max-w-sm">
        <svg class="w-16 h-16 text-icon-strong-base" viewBox="55 60 106 104" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M156.244 65.456V98.672C156.244 104.133 155.412 109.083 153.748 113.52C152.084 117.915 149.609 121.712 146.324 124.912C143.038 128.112 138.942 130.651 134.036 132.528C129.129 134.405 123.454 135.493 117.012 135.792V158H99.7315V135.792C93.2888 135.451 87.6355 134.341 82.7715 132.464C77.9075 130.587 73.8328 128.048 70.5475 124.848C67.3048 121.648 64.8515 117.851 63.1875 113.456C61.5235 109.019 60.6915 104.091 60.6915 98.672V65.456H72.2115C74.0462 65.456 75.4542 66.0107 76.4355 67.12C77.4595 68.2293 77.9715 69.5947 77.9715 71.216V98.672C77.9715 102.256 78.3342 105.456 79.0595 108.272C79.8275 111.045 81.0648 113.413 82.7715 115.376C84.4782 117.296 86.7182 118.832 89.4915 119.984C92.2648 121.093 95.6782 121.776 99.7315 122.032V65.456H117.012V122.032C121.108 121.776 124.542 121.093 127.316 119.984C130.132 118.875 132.393 117.36 134.1 115.44C135.849 113.477 137.086 111.109 137.812 108.336C138.58 105.52 138.964 102.299 138.964 98.672V71.216C138.964 69.5947 139.454 68.2293 140.436 67.12C141.46 66.0107 142.889 65.456 144.724 65.456H156.244Z" fill="currentColor" />
        </svg>
        <h1 class="mt-6 text-text-strong" style={{ "font-size": "var(--font-size-x-large)", "font-weight": "var(--font-weight-medium)" }}>
          {language.t("welcome.title")}
        </h1>
        <p class="mt-1.5 text-14-regular text-text-weak">{language.t("welcome.subtitle")}</p>
        <form onSubmit={handleSubmit} class="mt-10 w-full flex flex-col gap-4">
          <TextField autofocus type="password" hideLabel label={language.t("welcome.apiKey.label")} placeholder={language.t("welcome.apiKey.placeholder")} name="apiKey" value={apiKey()} onChange={(v) => { setApiKey(v); if (error()) setError(undefined) }} validationState={error() ? "invalid" : undefined} error={error()} />
          <Button type="submit" size="large" variant="primary" class="w-full" disabled={submitting()}>{language.t("welcome.getStarted")}</Button>
        </form>
      </div>
    </div>
  )
}
