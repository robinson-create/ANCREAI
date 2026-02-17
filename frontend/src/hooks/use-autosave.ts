import { useRef, useCallback, useEffect } from "react"
import { useMutation } from "@tanstack/react-query"
import { workspaceDocumentsApi } from "@/api/workspace-documents"
import type { DocModel } from "@/types"

export function useAutosave(docId: string, debounceMs: number = 1000) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestContent = useRef<DocModel | null>(null)

  const mutation = useMutation({
    mutationFn: (content: DocModel) =>
      workspaceDocumentsApi.patchContent(docId, content),
  })

  const save = useCallback(
    (content: DocModel) => {
      latestContent.current = content
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        if (latestContent.current) {
          mutation.mutate(latestContent.current)
        }
      }, debounceMs)
    },
    [docId, debounceMs] // eslint-disable-line react-hooks/exhaustive-deps
  )

  // Reset on docId change + flush on unmount/docId change
  useEffect(() => {
    // Clear stale content from a previous document
    latestContent.current = null

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (latestContent.current) {
        workspaceDocumentsApi
          .patchContent(docId, latestContent.current)
          .catch((err) => console.error("[autosave] flush failed:", err))
      }
    }
  }, [docId])

  return {
    save,
    isSaving: mutation.isPending,
    lastSaved: mutation.data?.updated_at ?? null,
  }
}
