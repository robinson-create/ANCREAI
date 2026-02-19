import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Plus, Folder as FolderIcon, MessageSquare, FileText, Mail } from "lucide-react"
import { Button } from "@/components/ui/button"
import { foldersApi } from "@/api/folders"
import { FolderCreateDialog } from "./FolderCreateDialog"
import { FolderDetailPanel } from "./FolderDetailPanel"
import type { Folder as FolderType } from "@/types"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"

export function FolderSection() {
  const [searchParams, setSearchParams] = useSearchParams()
  const folderId = searchParams.get("folder")
  const [createOpen, setCreateOpen] = useState(false)

  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["folders"],
    queryFn: () => foldersApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      toast({ title: "Dossier créé" })
      setCreateOpen(false)
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer le dossier.",
      })
    },
  })

  const openFolder = (id: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("folder", id)
      return next
    })
  }

  const closeFolder = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("folder")
      return next
    })
  }

  return (
    <>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-px flex-1 bg-border" />
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            <FolderIcon className="h-3.5 w-3.5" />
            Mes dossiers
          </div>
          <div className="h-px flex-1 bg-border" />
        </div>

        <div className="flex justify-end mb-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            Nouveau dossier
          </Button>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-24 rounded-lg bg-muted/50 animate-pulse"
              />
            ))}
          </div>
        ) : folders.length === 0 ? (
          <div className="text-center py-8 rounded-lg border border-dashed border-border">
            <FolderIcon className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              Aucun dossier. Créez-en un pour organiser vos conversations,
              documents et emails.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {folders.map((f) => (
              <FolderCard
                key={f.id}
                folder={f}
                onClick={() => openFolder(f.id)}
              />
            ))}
          </div>
        )}
      </div>

      <FolderCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(name) => createMutation.mutateAsync(name).then(() => undefined)}
        mode="create"
      />

      {folderId && (
        <FolderDetailPanel
          folderId={folderId}
          onClose={closeFolder}
        />
      )}
    </>
  )
}

function FolderCard({ folder, onClick }: { folder: FolderType; onClick: () => void }) {
  const total =
    folder.item_counts.conversation +
    folder.item_counts.document +
    folder.item_counts.email_thread

  return (
    <button
      onClick={onClick}
      className="group flex flex-col text-left p-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all"
    >
      <div
        className="w-full h-1 -mx-4 -mt-4 rounded-t-lg mb-3"
        style={{
          backgroundColor: folder.color || "var(--muted)",
        }}
      />
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
          <FolderIcon className="h-4 w-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {folder.name}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {folder.item_counts.conversation > 0 && (
              <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground">
                <MessageSquare className="h-2.5 w-2.5" />
                {folder.item_counts.conversation}
              </span>
            )}
            {folder.item_counts.document > 0 && (
              <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground">
                <FileText className="h-2.5 w-2.5" />
                {folder.item_counts.document}
              </span>
            )}
            {folder.item_counts.email_thread > 0 && (
              <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground">
                <Mail className="h-2.5 w-2.5" />
                {folder.item_counts.email_thread}
              </span>
            )}
            {total === 0 && (
              <span className="text-[10px] text-muted-foreground">Vide</span>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}
