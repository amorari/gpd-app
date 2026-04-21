import { IconButton } from "@opencode-ai/ui/icon-button"
import { useLanguage } from "@/context/language"

export interface EditHotspotProps {
  top: number
  height: number
  lineNumber: number
  onClick: () => void
}

/**
 * Floating pencil affordance that appears when the user hovers a line.
 * Positioned absolutely inside the overlay layer rendered above the Pierre
 * File viewer.
 */
export function EditHotspot(props: EditHotspotProps) {
  const language = useLanguage()
  return (
    <div
      data-component="edit-hotspot"
      class="pointer-events-auto absolute right-2 flex items-center"
      style={{
        top: `${props.top}px`,
        height: `${props.height}px`,
      }}
    >
      <IconButton
        icon="pencil-line"
        variant="ghost"
        size="small"
        aria-label={language.t("file.edit.hotspot.label", { line: String(props.lineNumber) })}
        onMouseDown={(event) => {
          // Prevent Pierre's line-selection drag from starting under our click.
          event.stopPropagation()
        }}
        onClick={(event) => {
          event.stopPropagation()
          event.preventDefault()
          props.onClick()
        }}
        class="size-6 rounded-md opacity-80 hover:opacity-100"
      />
    </div>
  )
}
