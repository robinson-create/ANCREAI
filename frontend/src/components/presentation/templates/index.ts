/**
 * Template registry — maps layout_id to React component.
 */
import { ComponentType } from 'react'

import IntroSlideLayout from './IntroSlideLayout'
import BasicInfoSlideLayout from './BasicInfoSlideLayout'
import BulletIconsOnlySlideLayout from './BulletIconsOnlySlideLayout'
import BulletWithIconsSlideLayout from './BulletWithIconsSlideLayout'
import ChartWithBulletsSlideLayout from './ChartWithBulletsSlideLayout'
import MetricsSlideLayout from './MetricsSlideLayout'
import MetricsWithImageSlideLayout from './MetricsWithImageSlideLayout'
import NumberedBulletsSlideLayout from './NumberedBulletsSlideLayout'
import QuoteSlideLayout from './QuoteSlideLayout'
import TableInfoSlideLayout from './TableInfoSlideLayout'
import TableOfContentsSlideLayout from './TableOfContentsSlideLayout'
import TeamSlideLayout from './TeamSlideLayout'

export interface TemplateEntry {
  component: ComponentType<{ data: Record<string, any> }>
  name: string
}

export const TEMPLATE_REGISTRY: Record<string, TemplateEntry> = {
  'general-intro-slide': { component: IntroSlideLayout, name: 'Intro Slide' },
  'basic-info-slide': { component: BasicInfoSlideLayout, name: 'Basic Info' },
  'bullet-icons-only-slide': { component: BulletIconsOnlySlideLayout, name: 'Bullet Icons Only' },
  'bullet-with-icons-slide': { component: BulletWithIconsSlideLayout, name: 'Bullet with Icons' },
  'chart-with-bullets-slide': { component: ChartWithBulletsSlideLayout, name: 'Chart with Bullets' },
  'metrics-slide': { component: MetricsSlideLayout, name: 'Metrics' },
  'metrics-with-image-slide': { component: MetricsWithImageSlideLayout, name: 'Metrics with Image' },
  'numbered-bullets-slide': { component: NumberedBulletsSlideLayout, name: 'Numbered Bullets' },
  'quote-slide': { component: QuoteSlideLayout, name: 'Quote' },
  'table-info-slide': { component: TableInfoSlideLayout, name: 'Table with Info' },
  'table-of-contents-slide': { component: TableOfContentsSlideLayout, name: 'Table of Contents' },
  'team-slide': { component: TeamSlideLayout, name: 'Team Slide' },
}

export function getTemplate(layoutType: string): TemplateEntry | undefined {
  return TEMPLATE_REGISTRY[layoutType]
}

export function getAllLayoutIds(): string[] {
  return Object.keys(TEMPLATE_REGISTRY)
}
