/**
 * Context for background document generation.
 * Allows generation to continue when the user navigates away from the document editor.
 */

import { createContext, useCallback, useContext, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import axios from "axios"
import { workspaceDocumentsApi } from "@/api/workspace-documents"
import { useToast } from "@/hooks/use-toast"
import type { DocBlock, DocModel, DocPatch } from "@/types"

/** Normalize DocModel before PATCH to satisfy strict backend validation (avoids 422). */
function normalizeDocModelForBackend(model: DocModel): DocModel {
  const meta = model.meta ?? { tags: [], custom: {} }
  const normalizedMeta = {
    ...meta,
    tags: Array.isArray(meta.tags) ? meta.tags : [],
    custom: meta.custom && typeof meta.custom === "object" ? meta.custom : {},
  }

  const normalizedSources = (model.sources ?? []).map((s) => ({
    chunk_id: String(s.chunk_id ?? ""),
    document_id: String(s.document_id ?? ""),
    document_filename: String(s.document_filename ?? ""),
    page_number:
      s.page_number == null ? null : typeof s.page_number === "number" ? Math.floor(s.page_number) : null,
    excerpt: String(s.excerpt ?? ""),
    score: typeof s.score === "number" && !Number.isNaN(s.score) ? s.score : 0,
  }))

  const seenIds = new Set<string>()
  const genId = () => {
    let id: string
    do {
      id = `b-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    } while (seenIds.has(id))
    seenIds.add(id)
    return id
  }

  const normalizedBlocks = (model.blocks ?? []).map((block): DocBlock => {
    const rawId = String(block.id ?? "")
    const id = rawId || genId()
    if (rawId) seenIds.add(rawId)
    const base = {
      type: block.type ?? "rich_text",
      id,
      label: block.label ?? null,
      locked: !!block.locked,
    }
    if (block.type === "line_items") {
      const items = (block.items ?? []).map((item, idx) => ({
        id: String((item as { id?: string }).id ?? "") || `li-${id}-${idx}`,
        description: String((item as { description?: string }).description ?? ""),
        quantity: Number((item as { quantity?: number }).quantity) || 0,
        unit: String((item as { unit?: string }).unit ?? ""),
        unit_price: Number((item as { unit_price?: number }).unit_price) || 0,
        tax_rate: Number((item as { tax_rate?: number }).tax_rate) || 0,
        total: Number((item as { total?: number }).total) || 0,
        meta: (item as { meta?: Record<string, unknown> }).meta,
      }))
      return { ...base, type: "line_items", items, columns: block.columns ?? [], currency: block.currency ?? "EUR" }
    }
    if (block.type === "signature") {
      return { ...base, type: "signature", parties: Array.isArray(block.parties) ? block.parties : [] }
    }
    if (block.type === "attachments") {
      return { ...base, type: "attachments", files: Array.isArray(block.files) ? block.files : [] }
    }
    if (block.type === "variables") {
      return {
        ...base,
        type: "variables",
        variables: block.variables && typeof block.variables === "object" ? block.variables : {},
      }
    }
    return {
      ...base,
      type: (block.type as DocBlock["type"]) ?? "rich_text",
      content: block.content && typeof block.content === "object" ? block.content : {},
      clause_ref: block.clause_ref ?? undefined,
    }
  })

  return {
    version: Number(model.version) || 1,
    meta: normalizedMeta,
    blocks: normalizedBlocks,
    variables: model.variables && typeof model.variables === "object" ? model.variables : {},
    sources: normalizedSources,
  }
}

// ── Pure helper: apply patches to a DocModel without store ──
function applyPatchesToModel(
  model: DocModel,
  patches: DocPatch[]
): DocModel {
  let blocks = [...(model.blocks || [])]
  for (const patch of patches) {
    if (patch.op === "add_block" && patch.value) {
      blocks = [...blocks, patch.value as unknown as DocBlock]
    } else if (patch.op === "replace_block" && patch.block_id && patch.value) {
      blocks = blocks.map((b) =>
        b.id === patch.block_id
          ? { ...b, ...(patch.value as Partial<DocBlock>) }
          : b
      )
    }
  }
  return { ...model, blocks }
}

const DEFAULT_MODEL: DocModel = {
  version: 1,
  meta: { tags: [], custom: {} },
  blocks: [],
  variables: {},
  sources: [],
}

interface DocumentGenerationContextValue {
  generatingDocIds: Set<string>
  startGeneration: (params: {
    docId: string
    prompt: string
    collectionIds?: string[]
    docType?: string
  }) => void
}

const DocumentGenerationContext =
  createContext<DocumentGenerationContextValue | null>(null)

export function DocumentGenerationProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [generatingDocIds, setGeneratingDocIds] = useState<Set<string>>(
    () => new Set()
  )

  const startGeneration = useCallback(
    async (params: {
      docId: string
      prompt: string
      collectionIds?: string[]
      docType?: string
    }) => {
      const { docId, prompt, collectionIds, docType } = params
      setGeneratingDocIds((prev) => new Set(prev).add(docId))

      try {
        const response = await workspaceDocumentsApi.generate(docId, {
          prompt,
          collection_ids: collectionIds,
          doc_type: docType,
        })

        if (
          (!response.patches || response.patches.length === 0) &&
          (response.message?.toLowerCase().includes("erreur") ?? false)
        ) {
          console.error("[doc-gen] Backend error:", response.message)
          return
        }

        if (!response.patches || response.patches.length === 0) {
          console.warn("[doc-gen] No patches returned")
          return
        }

        // Fetch current doc to apply patches on top
        const doc = await workspaceDocumentsApi.get(docId)
        const currentModel =
          (doc.content_json as DocModel) || DEFAULT_MODEL
        const normalized: DocModel = {
          version: currentModel.version ?? 1,
          meta: currentModel.meta ?? { tags: [], custom: {} },
          blocks: currentModel.blocks ?? [],
          variables: currentModel.variables ?? {},
          sources: [...(currentModel.sources ?? []), ...(response.sources ?? [])],
        }

        const newModel = applyPatchesToModel(normalized, response.patches)
        const modelToSend = normalizeDocModelForBackend(newModel)

        await workspaceDocumentsApi.patchContent(docId, modelToSend)

        // Générer un titre résumé à partir du contenu (au lieu du prompt)
        try {
          await workspaceDocumentsApi.suggestTitle(docId)
        } catch (titleErr) {
          console.warn("[doc-gen] Title suggestion failed:", titleErr)
        }

        queryClient.invalidateQueries({ queryKey: ["workspace-documents"] })
        queryClient.invalidateQueries({ queryKey: ["workspace-document", docId] })
      } catch (err) {
        console.error("[doc-gen] Generation failed:", err)
        let description = err instanceof Error ? err.message : "Impossible de générer le document."
        if (axios.isAxiosError(err) && err.response?.status === 422) {
          const detail = err.response.data?.detail
          if (Array.isArray(detail)) {
            const msgs = detail.map((d: { loc?: string[]; msg?: string }) => {
              const field = d.loc?.slice(1).join(".") || "?"
              return `${field}: ${d.msg ?? ""}`
            })
            description = msgs.join("; ") || "Données invalides (422)."
          } else if (typeof detail === "string") {
            description = detail
          }
        }
        toast({
          variant: "destructive",
          title: "Erreur de génération",
          description,
        })
      } finally {
        setGeneratingDocIds((prev) => {
          const next = new Set(prev)
          next.delete(docId)
          return next
        })
      }
    },
    [queryClient, toast]
  )

  return (
    <DocumentGenerationContext.Provider
      value={{ generatingDocIds, startGeneration }}
    >
      {children}
    </DocumentGenerationContext.Provider>
  )
}

export function useDocumentGeneration() {
  const ctx = useContext(DocumentGenerationContext)
  return ctx
}
