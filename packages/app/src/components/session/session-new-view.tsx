import { For, Show, createMemo } from "solid-js"
import { DateTime } from "luxon"
import { useSync } from "@/context/sync"
import { useSDK } from "@/context/sdk"
import { useLanguage } from "@/context/language"
import { usePrompt } from "@/context/prompt"
import { Icon, type IconProps } from "@opencode-ai/ui/icon"
import { Mark } from "@opencode-ai/ui/logo"
import { getDirectory, getFilename } from "@opencode-ai/util/path"

const MAIN_WORKTREE = "main"
const CREATE_WORKTREE = "create"
const ROOT_CLASS = "size-full flex flex-col"

interface ActionCard {
  icon: IconProps["name"]
  titleKey: string
  descKey: string
  insert: string
}

const ACTION_CARDS: ActionCard[] = [
  {
    icon: "new-session",
    titleKey: "session.newView.card.newProject",
    descKey: "session.newView.card.newProject.description",
    insert: "/gpd-new-project",
  },
  {
    icon: "glasses",
    titleKey: "session.newView.card.tour",
    descKey: "session.newView.card.tour.description",
    insert: "/gpd-tour",
  },
  {
    icon: "magnifying-glass",
    titleKey: "session.newView.card.arxiv",
    descKey: "session.newView.card.arxiv.description",
    insert: "Search arXiv for recent papers on ",
  },
  {
    icon: "help",
    titleKey: "session.newView.card.allCommands",
    descKey: "session.newView.card.allCommands.description",
    insert: "/gpd-help",
  },
]

const PROMPT_CHIP_KEYS = [
  "session.newView.chip.eulerLagrange",
  "session.newView.chip.symmetryBreaking",
  "session.newView.chip.researchMilestone",
  "session.newView.chip.quantumEntanglement",
] as const

interface NewSessionViewProps {
  worktree: string
}

export function NewSessionView(props: NewSessionViewProps) {
  const sync = useSync()
  const sdk = useSDK()
  const language = useLanguage()
  const prompt = usePrompt()

  const insertPrompt = (text: string) => {
    prompt.set([{ type: "text", content: text, start: 0, end: text.length }], text.length)
  }

  const sandboxes = createMemo(() => sync.project?.sandboxes ?? [])
  const options = createMemo(() => [MAIN_WORKTREE, ...sandboxes(), CREATE_WORKTREE])
  const current = createMemo(() => {
    const selection = props.worktree
    if (options().includes(selection)) return selection
    return MAIN_WORKTREE
  })
  const projectRoot = createMemo(() => sync.project?.worktree ?? sdk.directory)
  const isWorktree = createMemo(() => {
    const project = sync.project
    if (!project) return false
    return sdk.directory !== project.worktree
  })

  const label = (value: string) => {
    if (value === MAIN_WORKTREE) {
      if (isWorktree()) return language.t("session.new.worktree.main")
      const branch = sync.data.vcs?.branch
      if (branch) return language.t("session.new.worktree.mainWithBranch", { branch })
      return language.t("session.new.worktree.main")
    }

    if (value === CREATE_WORKTREE) return language.t("session.new.worktree.create")

    return getFilename(value)
  }

  return (
    <div class={ROOT_CLASS}>
      <div class="h-12 shrink-0" aria-hidden />
      <div class="flex-1 px-6 pb-30 flex items-center justify-center text-center">
        <div class="w-full max-w-200 flex flex-col items-center text-center gap-8">
          <div class="flex flex-col items-center gap-4">
            <div class="flex flex-col items-center gap-6">
              <Mark class="w-10" />
              <div class="text-20-medium text-text-strong">{language.t("session.new.title")}</div>
            </div>
            <div class="w-full flex flex-col gap-4 items-center">
              <div class="flex items-start justify-center gap-3 min-h-5">
                <div class="text-12-medium text-text-weak select-text leading-5 min-w-0 max-w-160 break-words text-center">
                  {getDirectory(projectRoot())}
                  <span class="text-text-strong">{getFilename(projectRoot())}</span>
                </div>
              </div>
              <div class="flex items-start justify-center gap-1.5 min-h-5">
                <Icon name="branch" size="small" class="mt-0.5 shrink-0" />
                <div class="text-12-medium text-text-weak select-text leading-5 min-w-0 max-w-160 break-words text-center">
                  {label(current())}
                </div>
              </div>
              <Show when={sync.project}>
                {(project) => (
                  <div class="flex items-start justify-center gap-3 min-h-5">
                    <div class="text-12-medium text-text-weak leading-5 min-w-0 max-w-160 break-words text-center">
                      {language.t("session.new.lastModified")}&nbsp;
                      <span class="text-text-strong">
                        {DateTime.fromMillis(project().time.updated ?? project().time.created)
                          .setLocale(language.intl())
                          .toRelative()}
                      </span>
                    </div>
                  </div>
                )}
              </Show>
            </div>
          </div>

          <div class="w-full flex flex-col gap-4">
            <div class="text-12-medium text-text-weak uppercase tracking-wide">
              {language.t("session.newView.getStarted.title")}
            </div>
            <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <For each={ACTION_CARDS}>
                {(card) => (
                  <button
                    type="button"
                    onClick={() => insertPrompt(card.insert)}
                    class="flex flex-col items-start gap-2 rounded-lg border border-border-weak-base bg-background-base px-3 py-3 text-left transition-colors hover:bg-background-strong hover:border-border-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                  >
                    <Icon name={card.icon} size="small" class="text-text-weak shrink-0" />
                    <div class="flex flex-col gap-0.5 min-w-0">
                      <div class="text-12-medium text-text-base truncate">
                        {language.t(card.titleKey as Parameters<typeof language.t>[0])}
                      </div>
                      <div class="text-11-regular text-text-weak leading-tight line-clamp-2">
                        {language.t(card.descKey as Parameters<typeof language.t>[0])}
                      </div>
                    </div>
                  </button>
                )}
              </For>
            </div>
          </div>

          <div class="w-full flex flex-col gap-2">
            <div class="text-12-medium text-text-weak uppercase tracking-wide">
              {language.t("session.newView.chips.title")}
            </div>
            <div class="flex flex-wrap justify-center gap-2">
              <For each={PROMPT_CHIP_KEYS}>
                {(key) => (
                  <button
                    type="button"
                    onClick={() => insertPrompt(language.t(key))}
                    class="rounded-full border border-border-weak-base bg-background-base px-3 py-1.5 text-12-regular text-text-weak transition-colors hover:bg-background-strong hover:text-text-base hover:border-border-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
                  >
                    {language.t(key)}
                  </button>
                )}
              </For>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
