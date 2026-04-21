import { Show, createEffect, createResource, createSignal, on, onCleanup } from "solid-js"
import { useLanguage } from "@/context/language"
import { usePlatform } from "@/context/platform"

/**
 * Embedded PDF viewer for the TeX Build pane.
 *
 * We use the browser's native PDF renderer via `<iframe>` with a
 * `data:application/pdf;base64,…` URL. Tauri's WebView (WebKit on macOS,
 * WebView2 on Windows) renders PDFs natively, so this works without
 * bundling PDF.js. PDF.js can be swapped in later to gain per-click
 * coordinate capture — for now we surface the SyncTeX forward handler via
 * a small overlay button the user can drop on the page they care about.
 *
 * The iframe is keyed on the PDF path, so switching builds re-creates the
 * element and forces the viewer to forget its scroll position. This is
 * the right default: a new compile usually invalidates the previous view.
 */
export function TexPdfViewer(props: {
  pdfPath: string
  /**
   * Optional SyncTeX callback invoked when the user confirms "jump to
   * current page / coordinates". The builder pane wires this to
   * `synctex_forward`.
   */
  onJumpToSource?: (input: { page: number; x: number; y: number }) => void
  class?: string
}) {
  const platform = usePlatform()
  const language = useLanguage()
  const [dataUrl, { refetch }] = createResource(
    () => props.pdfPath,
    async (path) => {
      const api = platform.tex
      if (!api) return null
      const b64 = await api.readArtifactBase64(path)
      return `data:application/pdf;base64,${b64}`
    },
  )

  // Re-fetch whenever the path changes (e.g. recompile produced a new build).
  createEffect(
    on(
      () => props.pdfPath,
      () => {
        refetch()
      },
      { defer: true },
    ),
  )

  const [page, setPage] = createSignal<number>(1)

  // Query the iframe's current page if possible. WebKit exposes
  // `document.location.hash = "#page=N"` as the standard way to navigate,
  // but there's no read-back API. We approximate by letting the user tell
  // us which page they are on via the header control.
  let iframeRef: HTMLIFrameElement | undefined

  const navigateTo = (nextPage: number) => {
    setPage(nextPage)
    const el = iframeRef
    const url = dataUrl()
    if (!el || !url) return
    // Re-point the iframe at `#page=N` to scroll the WebView renderer.
    // We append the fragment to the data URL.
    el.src = `${url}#page=${nextPage}`
  }

  onCleanup(() => {
    // Nothing to dispose; the iframe garbage-collects when the node unmounts.
  })

  return (
    <div
      class={
        "relative h-full w-full flex flex-col bg-background-stronger " + (props.class ?? "")
      }
      data-component="tex-pdf-viewer"
    >
      <div class="flex items-center justify-between shrink-0 px-3 py-2 text-12-regular text-text-weak border-b border-border-weaker-base">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-2 py-0.5 rounded hover:bg-background-weaker-base"
            onClick={() => navigateTo(Math.max(1, page() - 1))}
            aria-label={language.t("tex.pdf.prev")}
          >
            ‹
          </button>
          <span>
            {language.t("tex.pdf.page")} {page()}
          </span>
          <button
            type="button"
            class="px-2 py-0.5 rounded hover:bg-background-weaker-base"
            onClick={() => navigateTo(page() + 1)}
            aria-label={language.t("tex.pdf.next")}
          >
            ›
          </button>
        </div>
        <Show when={props.onJumpToSource}>
          {(handler) => (
            <button
              type="button"
              class="px-2 py-0.5 rounded hover:bg-background-weaker-base"
              title={language.t("tex.pdf.jumpToSource.hint")}
              onClick={() => handler()({ page: page(), x: 50, y: 50 })}
            >
              {language.t("tex.pdf.jumpToSource")}
            </button>
          )}
        </Show>
      </div>

      <div class="flex-1 min-h-0">
        <Show
          when={dataUrl()}
          fallback={
            <div class="h-full flex items-center justify-center text-12-regular text-text-weak">
              {language.t("tex.build.status.compiling")}
            </div>
          }
        >
          {(url) => (
            <iframe
              ref={(el) => {
                iframeRef = el
              }}
              src={url()}
              class="w-full h-full border-0 bg-white"
              title={language.t("tex.pdf.title")}
            />
          )}
        </Show>
      </div>
    </div>
  )
}
