import { create } from "zustand"
import type { DocBlock, DocModel } from "@/types"

interface DocumentStore {
  docModel: DocModel | null
  setDocModel: (model: DocModel) => void
  updateBlock: (blockId: string, patch: Partial<DocBlock>) => void
  addBlock: (block: DocBlock, afterBlockId?: string) => void
  removeBlock: (blockId: string) => void
  getDocModel: () => DocModel | null
  reset: () => void
}

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  docModel: null,

  setDocModel: (model) => set({ docModel: model }),

  getDocModel: () => get().docModel,

  reset: () => set({ docModel: null }),

  updateBlock: (blockId, patch) => {
    const { docModel } = get()
    if (!docModel) return
    set({
      docModel: {
        ...docModel,
        blocks: docModel.blocks.map((b) =>
          b.id === blockId ? { ...b, ...patch } : b
        ),
      },
    })
  },

  addBlock: (block, afterBlockId) => {
    const { docModel } = get()
    if (!docModel) return

    const blocks = [...docModel.blocks]
    if (afterBlockId) {
      const idx = blocks.findIndex((b) => b.id === afterBlockId)
      if (idx >= 0) {
        blocks.splice(idx + 1, 0, block)
      } else {
        blocks.push(block)
      }
    } else {
      blocks.push(block)
    }

    set({ docModel: { ...docModel, blocks } })
  },

  removeBlock: (blockId) => {
    const { docModel } = get()
    if (!docModel) return
    set({
      docModel: {
        ...docModel,
        blocks: docModel.blocks.filter((b) => b.id !== blockId),
      },
    })
  },
}))
