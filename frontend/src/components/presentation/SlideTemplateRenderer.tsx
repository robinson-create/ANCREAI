/**
 * SlideTemplateRenderer — renders a slide using the JSON template system.
 *
 * Replaces the old recursive SlideNodeRenderer. Each slide has a layout_type
 * that maps to a fixed React template, and content_json that fills the template.
 */
import { useMemo } from 'react'
import { TEMPLATE_REGISTRY } from './templates'

interface SlideTemplateRendererProps {
  layoutType: string
  data: Record<string, any>
}

/** Strip markdown formatting from a string (bold, italic, code, links, headers). */
function stripMarkdown(text: string): string {
  if (!text) return text
  let s = text
  // Bold: **text** or __text__
  s = s.replace(/\*\*(.+?)\*\*/g, '$1')
  s = s.replace(/__(.+?)__/g, '$1')
  // Italic: *text* or _text_ (word boundary)
  s = s.replace(/\*(.+?)\*/g, '$1')
  s = s.replace(/(?<!\w)_(.+?)_(?!\w)/g, '$1')
  // Inline code: `text`
  s = s.replace(/`(.+?)`/g, '$1')
  // Links: [text](url)
  s = s.replace(/\[(.+?)\]\(.+?\)/g, '$1')
  // Headers: # text
  s = s.replace(/^#{1,6}\s+/gm, '')
  // «guillemets» are fine, keep them
  return s
}

/** Recursively strip markdown from all string values in a data object. */
function cleanData(obj: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === 'string') {
      result[key] = stripMarkdown(value)
    } else if (Array.isArray(value)) {
      result[key] = value.map(item =>
        typeof item === 'object' && item !== null && !Array.isArray(item)
          ? cleanData(item)
          : typeof item === 'string'
            ? stripMarkdown(item)
            : item
      )
    } else if (typeof value === 'object' && value !== null) {
      result[key] = cleanData(value)
    } else {
      result[key] = value
    }
  }
  return result
}

function FallbackSlide({ data }: { data: Record<string, any> }) {
  return (
    <div
      className="w-full h-full overflow-hidden flex items-center justify-center"
      style={{
        fontFamily: 'var(--heading-font-family, Plus Jakarta Sans)',
        background: 'var(--background-color, #FFFFFF)',
        color: 'var(--background-text, #323F50)',
      }}
    >
      <div className="text-center p-8">
        <h2 className="text-2xl font-bold mb-4">
          {data?.title || data?.heading || 'Slide'}
        </h2>
        {data?.description && (
          <p className="text-base opacity-70">{data.description}</p>
        )}
      </div>
    </div>
  )
}

export default function SlideTemplateRenderer({ layoutType, data }: SlideTemplateRendererProps) {
  const entry = TEMPLATE_REGISTRY[layoutType]
  const cleaned = useMemo(() => cleanData(data || {}), [data])

  if (!entry) {
    console.warn('[SlideTemplate] Unknown layout:', layoutType, '— using fallback. Data keys:', Object.keys(data || {}))
    return <FallbackSlide data={cleaned} />
  }

  const Template = entry.component
  return <Template data={cleaned} />
}
