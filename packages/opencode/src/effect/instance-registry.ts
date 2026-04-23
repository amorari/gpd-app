const disposers = new Set<(directory: string) => Promise<void>>()

export function registerDisposer(disposer: (directory: string) => Promise<void>) {
  disposers.add(disposer)
  return () => {
    disposers.delete(disposer)
  }
}

// Same 10s ceiling as Instance.disposeAll. A single disposer that never
// resolves (stuck network flush, wedged GCS upload, hung subprocess) would
// otherwise keep Promise.allSettled pending forever, which propagates back
// to disposeAll and then to the Hono error middleware that never gets to
// run. Bound each disposer independently so one slow disposer doesn't
// starve the others.
const DISPOSER_TIMEOUT_MS = 10_000

export async function disposeInstance(directory: string) {
  await Promise.allSettled(
    [...disposers].map((disposer) =>
      Promise.race([
        disposer(directory),
        new Promise<void>((resolve) =>
          setTimeout(() => {
            resolve()
          }, DISPOSER_TIMEOUT_MS),
        ),
      ]),
    ),
  )
}
