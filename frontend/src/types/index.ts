// Subscription types
export type SubscriptionPlan = "free" | "pro"

export interface SubscriptionPlanDetails {
  id: string
  name: string
  price: number
  max_assistants: number
  max_storage_gb: number
  max_chat_tokens: number
  features: string[]
  popular?: boolean
}
export type SubscriptionStatus = "active" | "trialing" | "past_due" | "canceled"

// Assistant types
export interface Assistant {
  id: string
  tenant_id: string
  name: string
  system_prompt: string | null
  model: string
  settings: Record<string, unknown>
  created_at: string
  updated_at: string
  collection_ids: string[]
  integration_ids: string[]
}

export interface AssistantCreate {
  name: string
  system_prompt?: string
  model?: string
  settings?: Record<string, unknown>
  collection_ids?: string[]
  integration_ids?: string[]
}

export interface AssistantUpdate {
  name?: string
  system_prompt?: string
  model?: string
  settings?: Record<string, unknown>
  collection_ids?: string[]
  integration_ids?: string[]
}

// Collection types
export interface Collection {
  id: string
  tenant_id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
  documents_count: number
  total_chunks: number
}

export interface CollectionCreate {
  name: string
  description?: string
}

// Document types
export interface Document {
  id: string
  collection_id: string
  filename: string
  content_type: string
  file_size: number
  status: DocumentStatus
  error_message: string | null
  page_count: number | null
  chunk_count: number | null
  tokens_used: number | null
  created_at: string
  updated_at: string
  processed_at: string | null
}

export type DocumentStatus = "pending" | "processing" | "ready" | "failed"

export interface DocumentUploadResponse {
  id: string
  filename: string
  status: DocumentStatus
  message: string
}

// Chat types
export interface ChatRequest {
  message: string
  conversation_id?: string
  include_history?: boolean
  max_history_messages?: number
  context_hint?: string
}

export interface ChatResponse {
  message: string
  conversation_id: string
  citations: Citation[]
  tokens_input: number
  tokens_output: number
}

export interface Citation {
  chunk_id: string
  document_id: string
  document_filename: string
  page_number: number | null
  excerpt: string
  score: number
}

// Generative UI blocks
export type BlockType = "kpi_cards" | "steps" | "table" | "callout" | "tool_call" | "error"

export interface Block {
  id: string
  type: BlockType
  payload: unknown
}

export interface Message {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  citations?: Citation[]
  blocks?: Block[]
  created_at: string
}

export interface Conversation {
  id: string
  assistant_id: string
  messages: Message[]
  created_at: string
}

// API Error
export interface ApiError {
  detail: string
  status_code?: number
}

// ── Workspace Documents ──

export type DocBlockKind =
  | "rich_text"
  | "line_items"
  | "clause"
  | "terms"
  | "signature"
  | "attachments"
  | "variables"

export type WorkspaceDocStatus = "draft" | "validated" | "sent" | "archived"

export interface LineItemData {
  id: string
  description: string
  quantity: number
  unit: string
  unit_price: number
  tax_rate: number
  total: number
  meta?: Record<string, unknown>
}

export interface DocBlock {
  type: DocBlockKind
  id: string
  label?: string | null
  locked?: boolean
  // rich_text / clause / terms
  content?: Record<string, unknown>
  clause_ref?: string
  // line_items
  items?: LineItemData[]
  columns?: string[]
  currency?: string
  // signature
  parties?: Record<string, unknown>[]
  // attachments
  files?: Record<string, unknown>[]
  // variables
  variables?: Record<string, unknown>
}

export interface DocSource {
  chunk_id: string
  document_id: string
  document_filename: string
  page_number: number | null
  excerpt: string
  score: number
}

export interface DocMeta {
  author?: string | null
  client?: string | null
  project?: string | null
  reference?: string | null
  date?: string | null
  tags: string[]
  custom: Record<string, unknown>
}

export interface DocModel {
  version: number
  meta: DocMeta
  blocks: DocBlock[]
  variables: Record<string, unknown>
  sources: DocSource[]
}

export interface WorkspaceDocument {
  id: string
  tenant_id: string
  assistant_id: string | null
  title: string
  doc_type: string
  status: WorkspaceDocStatus
  content_json: DocModel
  version: number
  last_exported_url: string | null
  created_at: string
  updated_at: string
}

export interface WorkspaceDocumentListItem {
  id: string
  tenant_id: string
  title: string
  doc_type: string
  status: WorkspaceDocStatus
  assistant_id: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface WorkspaceDocumentCreate {
  title?: string
  doc_type?: string
  assistant_id?: string
  content_json?: DocModel
  template_id?: string
}

export interface WorkspaceDocumentUpdate {
  title?: string
  doc_type?: string
  assistant_id?: string
  status?: string
  content_json?: DocModel
}

export interface DocPatch {
  op: string
  block_id?: string | null
  value: Record<string, unknown>
}

export interface AiActionResponse {
  patches: DocPatch[]
  sources: DocSource[]
  message: string
}

// Folder types
export interface Folder {
  id: string
  name: string
  description: string | null
  color: string | null
  item_counts: { conversation: number; document: number; email_thread: number }
  created_at: string
  updated_at: string
}

export interface FolderItem {
  id: string
  item_type: "conversation" | "document" | "email_thread"
  item_id: string
  title: string
  subtitle: string | null
  date: string
  added_at: string
}

export interface FolderCreate {
  name: string
  description?: string | null
  color?: string | null
}

export interface FolderUpdate {
  name?: string
  description?: string | null
  color?: string | null
}

export interface FolderItemAdd {
  item_type: "conversation" | "document" | "email_thread"
  item_id: string
}

// ── Presentations ──

export type PresentationStatus =
  | "draft"
  | "generating_outline"
  | "outline_ready"
  | "generating_slides"
  | "ready"
  | "exporting"
  | "error"

export interface PresentationListItem {
  id: string
  tenant_id: string
  title: string
  status: PresentationStatus
  slide_order: string[]
  version: number
  theme_id: string | null
  created_at: string
  updated_at: string
}

export interface PresentationCreate {
  title?: string
  prompt?: string
  theme_id?: string
  settings?: {
    language?: string
    style?: string
    slide_count?: number
  }
}

// ── Presentation Full Types ──

export interface TextLeaf {
  text: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
  color?: string
  font_size?: string
  font_family?: string
}

export interface SlideNode {
  type: string // h1|h2|h3|h4|h5|h6|p|img|bullet_group|bullet_item|box_group|box_item|...
  children: (SlideNode | TextLeaf)[]
  url?: string
  asset_id?: string
  data?: Record<string, unknown>[]
  align?: string
  // Variant for styled elements (boxes, bullets, timeline, pyramid, quote, stats, gallery)
  variant?: string
  // Value for stats items
  value?: string
  // Image query for gallery items
  query?: string
}

export interface RootImage {
  asset_id?: string
  query?: string
  layout_type?: string
}

export interface Slide {
  id: string
  position: number
  layout_type: string
  content_json: Record<string, unknown>
  root_image?: RootImage | null
  bg_color?: string | null
  speaker_notes?: string | null
  created_at: string
  updated_at: string
}

export interface OutlineItem {
  title: string
  bullets: string[]
}

export interface PresentationSettings {
  language?: string
  style?: string
  slide_count?: number
}

export interface PresentationFull {
  id: string
  tenant_id: string
  title: string
  prompt?: string | null
  status: PresentationStatus
  outline: OutlineItem[]
  settings: PresentationSettings
  slide_order: string[]
  version: number
  theme_id?: string | null
  theme?: ThemeRead | null
  error_message?: string | null
  created_at: string
  updated_at: string
  slides: Slide[]
}

export interface PresentationUpdate {
  title?: string
  prompt?: string
  settings?: PresentationSettings
  theme_id?: string | null
}

export interface SlideUpdate {
  content_json?: Record<string, unknown>
  layout_type?: string
  root_image?: Record<string, unknown> | null
  bg_color?: string | null
  speaker_notes?: string | null
}

export interface GenerateOutlineRequest {
  prompt: string
  slide_count?: number
  language?: string
  style?: string
  collection_ids?: string[]
}

export interface GenerateSlidesRequest {
  collection_ids?: string[]
}

export interface RegenerateSlideRequest {
  instruction?: string
  collection_ids?: string[]
}

export interface ThemeColors {
  primary: string
  secondary: string
  accent: string
  background: string
  text: string
  heading: string
  muted: string
}

export interface ThemeFonts {
  heading: string
  body: string
}

export interface ThemeData {
  colors: ThemeColors
  fonts: ThemeFonts
  border_radius: string
}

export interface ThemeRead {
  id: string
  tenant_id: string | null
  name: string
  is_builtin: boolean
  theme_data: ThemeData
  created_at: string
}

export interface ThemeCreate {
  name: string
  theme_data: ThemeData
}

export interface ExportRequest {
  format: "pptx" | "pdf"
}

export interface ExportRead {
  id: string
  format: string
  status: string
  s3_key?: string | null
  file_size?: number | null
  presentation_version: number
  slide_count: number
  error_message?: string | null
  created_at: string
}

export type PresentationSSEEventType =
  | "outline_ready"
  | "slide_generated"
  | "slide_error"
  | "asset_ready"
  | "generation_complete"
  | "export_progress"
  | "export_ready"
  | "error"

export interface PresentationSSEEvent {
  type: PresentationSSEEventType
  payload: Record<string, unknown>
}
