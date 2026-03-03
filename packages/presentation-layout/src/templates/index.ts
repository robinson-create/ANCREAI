/**
 * Template registry — maps layout_id to React component.
 */
import { ComponentType } from "react";

import IntroSlideLayout from "./IntroSlideLayout.js";
import BasicInfoSlideLayout from "./BasicInfoSlideLayout.js";
import BulletIconsOnlySlideLayout from "./BulletIconsOnlySlideLayout.js";
import BulletWithIconsSlideLayout from "./BulletWithIconsSlideLayout.js";
import ChartWithBulletsSlideLayout from "./ChartWithBulletsSlideLayout.js";
import MetricsSlideLayout from "./MetricsSlideLayout.js";
import MetricsWithImageSlideLayout from "./MetricsWithImageSlideLayout.js";
import NumberedBulletsSlideLayout from "./NumberedBulletsSlideLayout.js";
import QuoteSlideLayout from "./QuoteSlideLayout.js";
import TableInfoSlideLayout from "./TableInfoSlideLayout.js";
import TableOfContentsSlideLayout from "./TableOfContentsSlideLayout.js";
import TeamSlideLayout from "./TeamSlideLayout.js";

export interface TemplateEntry {
  component: ComponentType<{ data: Record<string, any> }>;
  name: string;
}

export const TEMPLATE_REGISTRY: Record<string, TemplateEntry> = {
  "general-intro-slide": { component: IntroSlideLayout, name: "Intro Slide" },
  "basic-info-slide": { component: BasicInfoSlideLayout, name: "Basic Info" },
  "bullet-icons-only-slide": {
    component: BulletIconsOnlySlideLayout,
    name: "Bullet Icons Only",
  },
  "bullet-with-icons-slide": {
    component: BulletWithIconsSlideLayout,
    name: "Bullet with Icons",
  },
  "chart-with-bullets-slide": {
    component: ChartWithBulletsSlideLayout,
    name: "Chart with Bullets",
  },
  "metrics-slide": { component: MetricsSlideLayout, name: "Metrics" },
  "metrics-with-image-slide": {
    component: MetricsWithImageSlideLayout,
    name: "Metrics with Image",
  },
  "numbered-bullets-slide": {
    component: NumberedBulletsSlideLayout,
    name: "Numbered Bullets",
  },
  "quote-slide": { component: QuoteSlideLayout, name: "Quote" },
  "table-info-slide": {
    component: TableInfoSlideLayout,
    name: "Table with Info",
  },
  "table-of-contents-slide": {
    component: TableOfContentsSlideLayout,
    name: "Table of Contents",
  },
  "team-slide": { component: TeamSlideLayout, name: "Team Slide" },
};

export function getTemplate(layoutType: string): TemplateEntry | undefined {
  return TEMPLATE_REGISTRY[layoutType];
}

export function getAllLayoutIds(): string[] {
  return Object.keys(TEMPLATE_REGISTRY);
}
