/**
 * Shared types for the PPTX exporter service.
 * Contract between Arq worker (Python) and this service.
 */

export interface ExportRequest {
  schema_version: 1;
  presentation_id: string;
  tenant_id: string;
  export_id: string;
  theme: ThemeProperties;
  page_size: PageSize;
  slides: ResolvedSlide[];
  assets: AssetManifest[];
}

export interface PageSize {
  width: number;   // inches
  height: number;  // inches
  margin: number;  // inches
}

export interface ThemeProperties {
  colors?: ThemeColors;
  fonts?: ThemeFonts;
  border_radius?: string;
}

export interface ThemeColors {
  primary?: string;
  secondary?: string;
  accent?: string;
  background?: string;
  text?: string;
  heading?: string;
  muted?: string;
}

export interface ThemeFonts {
  heading?: string;
  body?: string;
}

export interface ResolvedSlide {
  id: string;
  position: number;
  layout_type: string;
  bg_color: string | null;
  boxes: ResolvedBox[];
}

export interface ResolvedBox {
  x: number;           // inches
  y: number;           // inches
  w: number;           // inches
  h: number;           // inches
  node_type: "text" | "image" | "shape" | "chart" | "svg";
  content: Record<string, any>;
  font_size_pt?: number | null;
  truncated?: boolean;
}

export interface AssetManifest {
  asset_id: string;
  presigned_url: string;
  mime: string;
  width: number | null;
  height: number | null;
}

export interface ExportResponse {
  s3_key: string;
  file_size: number;
  duration_ms: number;
}
