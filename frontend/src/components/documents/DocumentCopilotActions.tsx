/**
 * Page-level CopilotKit readables + actions for workspace document editing.
 * Rendered inside DocumentEditorPage only — does NOT modify global CopilotActions.
 */

import { useCopilotReadable, useCopilotAction } from "@copilotkit/react-core"
import { useDocumentStore } from "@/hooks/use-document-store"
import { workspaceDocumentsApi } from "@/api/workspace-documents"
import type { DocBlock, DocPatch } from "@/types"

interface Props {
  docId: string
  title: string
  docType: string
  collectionIds: string[]
}

function applyPatches(
  patches: DocPatch[],
  updateBlock: (id: string, patch: Partial<DocBlock>) => void,
  addBlock: (block: DocBlock, afterId?: string) => void
) {
  for (const patch of patches) {
    if (patch.op === "add_block" && patch.value) {
      addBlock(patch.value as unknown as DocBlock)
    } else if (patch.op === "replace_block" && patch.block_id && patch.value) {
      updateBlock(patch.block_id, patch.value as Partial<DocBlock>)
    } else if (patch.op === "add_line_item" && patch.block_id && patch.value) {
      // Handled by the caller — needs to merge with existing items
      // For now, we emit an update with the new item appended
      updateBlock(patch.block_id, {
        items: undefined, // trigger store to re-render
      })
    }
  }
}

export function DocumentCopilotActions({
  docId,
  title,
  docType,
  collectionIds,
}: Props) {
  const { docModel, updateBlock, addBlock } = useDocumentStore()

  // Expose document context to CopilotKit LLM
  useCopilotReadable({
    description: "Current workspace document being edited",
    value: {
      id: docId,
      title,
      doc_type: docType,
      blocks_count: docModel?.blocks.length ?? 0,
      block_types:
        docModel?.blocks.map((b) => ({
          id: b.id,
          type: b.type,
          label: b.label,
        })) ?? [],
      variables: docModel?.variables ?? {},
      sources_count: docModel?.sources.length ?? 0,
    },
  })

  // Action: generateDocument
  useCopilotAction({
    name: "generateDocument",
    description:
      "Generate or fill document content using AI and the knowledge base. " +
      "Use when the user asks to generate, create, or fill a document.",
    parameters: [
      {
        name: "prompt",
        type: "string",
        description: "What to generate",
        required: true,
      },
      {
        name: "target_block_ids",
        type: "string[]",
        description: "Specific block IDs to fill, or omit for full doc",
        required: false,
      },
    ],
    handler: async (args) => {
      const response = await workspaceDocumentsApi.generate(docId, {
        prompt: args.prompt as string,
        collection_ids: collectionIds,
        doc_type: docType,
      })
      applyPatches(response.patches, updateBlock, addBlock)
      return response.message || "Document genere."
    },
  })

  // Action: rewriteBlock
  useCopilotAction({
    name: "rewriteBlock",
    description:
      "Rewrite a specific block of the document with AI. " +
      "Use when the user asks to improve, rephrase, or modify a section.",
    parameters: [
      {
        name: "block_id",
        type: "string",
        description: "ID of the block to rewrite",
        required: true,
      },
      {
        name: "instruction",
        type: "string",
        description:
          "How to rewrite (e.g. 'make more concise', 'add legal terms')",
        required: true,
      },
    ],
    handler: async (args) => {
      const response = await workspaceDocumentsApi.rewriteBlock(docId, {
        block_id: args.block_id as string,
        instruction: args.instruction as string,
        collection_ids: collectionIds,
      })
      applyPatches(response.patches, updateBlock, addBlock)
      return response.message || "Bloc reecrit."
    },
  })

  // Action: checkDocument
  useCopilotAction({
    name: "checkDocument",
    description:
      "Check the document for consistency, compliance, or errors. " +
      "Use when the user asks to review or validate the document.",
    parameters: [
      {
        name: "check_type",
        type: "string",
        description: "Type of check: general, legal, or financial",
        required: false,
      },
    ],
    handler: async (args) => {
      const response = await workspaceDocumentsApi.checkDocument(docId, {
        collection_ids: collectionIds,
        check_type: (args.check_type as string) || "general",
      })
      applyPatches(response.patches, updateBlock, addBlock)
      return response.message || "Verification terminee."
    },
  })

  // Action: addLineItem
  useCopilotAction({
    name: "addLineItem",
    description:
      "Add a line item to a line_items block using AI. " +
      "Use when the user asks to add a product, service, or item.",
    parameters: [
      {
        name: "block_id",
        type: "string",
        description: "ID of the line_items block",
        required: true,
      },
      {
        name: "description",
        type: "string",
        description: "Description of the item to add",
        required: true,
      },
    ],
    handler: async (args) => {
      const response = await workspaceDocumentsApi.addLineItem(docId, {
        block_id: args.block_id as string,
        description: args.description as string,
        collection_ids: collectionIds,
      })
      applyPatches(response.patches, updateBlock, addBlock)
      return response.message || "Ligne ajoutee."
    },
  })

  return null
}
