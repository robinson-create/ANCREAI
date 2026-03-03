export interface Dossier {
  id: string
  tenant_id: string
  user_id: string
  name: string
  description: string | null
  color: string | null
  created_at: string
  updated_at: string
}

export interface DossierWithStats extends Dossier {
  documents_count: number
  conversations_count: number
}

export interface DossierDocument {
  id: string
  dossier_id: string
  filename: string
  content_type: string
  file_size: number
  status: "pending" | "processing" | "ready" | "failed"
  error_message: string | null
  page_count: number | null
  chunk_count: number | null
  tokens_used: number | null
  created_at: string
  updated_at: string
  processed_at: string | null
}

export interface DossierDocumentUploadResponse {
  id: string
  filename: string
  status: string
  message: string
}

export interface DossierConversation {
  id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
}

export type DossierItemType =
  | "document"
  | "presentation"
  | "upload"
  | "email_thread"
  | "conversation"

export interface DossierItem {
  id: string
  dossier_id: string
  item_type: DossierItemType
  item_id: string
  title: string
  subtitle: string | null
  added_at: string
}

export interface DossierItemAdd {
  item_type: DossierItemType
  item_id: string
  title: string
  subtitle?: string
}
