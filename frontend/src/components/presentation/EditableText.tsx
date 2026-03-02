/**
 * EditableText — inline editable text for slide templates.
 *
 * Renders as a normal element (span/p/h2 etc.) that becomes contentEditable
 * when the slide is in edit mode. On blur, saves the new text via SlideEditContext.
 */
import { useRef, useCallback, KeyboardEvent } from "react"
import { useSlideEdit } from "./SlideEditContext"

interface EditableTextProps {
  /** The current text value */
  value: string | undefined
  /** Dot-path field in content_json, e.g. "title", "bulletPoints.0.description" */
  fieldPath: string
  /** HTML tag to render */
  as?: "h1" | "h2" | "h3" | "p" | "span" | "div"
  /** CSS class */
  className?: string
  /** Inline styles */
  style?: React.CSSProperties
  /** Placeholder when empty */
  placeholder?: string
}

export default function EditableText({
  value,
  fieldPath,
  as: Tag = "span",
  className,
  style,
  placeholder,
}: EditableTextProps) {
  const ctx = useSlideEdit()
  const ref = useRef<HTMLElement>(null)
  const lastValue = useRef(value ?? "")

  const handleBlur = useCallback(() => {
    if (!ctx?.isEditable || !ref.current) return
    const newText = ref.current.innerText.trim()
    if (newText !== lastValue.current) {
      lastValue.current = newText
      ctx.onFieldUpdate(fieldPath, newText)
    }
  }, [ctx, fieldPath])

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Enter = blur (save), Escape = cancel
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      ref.current?.blur()
    } else if (e.key === "Escape") {
      if (ref.current) {
        ref.current.innerText = lastValue.current
        ref.current.blur()
      }
    }
  }, [])

  const isEditable = ctx?.isEditable ?? false
  const displayText = value || ""

  return (
    <Tag
      ref={ref as any}
      className={className}
      style={{
        ...style,
        outline: "none",
        cursor: isEditable ? "text" : undefined,
        minWidth: isEditable && !displayText ? "60px" : undefined,
      }}
      contentEditable={isEditable}
      suppressContentEditableWarning
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      data-placeholder={placeholder}
    >
      {displayText}
    </Tag>
  )
}
