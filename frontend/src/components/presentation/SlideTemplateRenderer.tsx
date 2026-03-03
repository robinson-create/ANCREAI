/**
 * SlideTemplateRenderer — renders a slide using the JSON template system.
 *
 * Replaces the old recursive SlideNodeRenderer. Each slide has a layout_type
 * that maps to a fixed React template, and content_json that fills the template.
 */
import { useMemo } from 'react'
import { TEMPLATE_REGISTRY } from './templates'
import { cleanData } from '@ancre/presentation-layout'

interface SlideTemplateRendererProps {
  layoutType: string
  data: Record<string, any>
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
