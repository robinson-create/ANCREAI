import { useState } from "react"
import { Loader2, FolderPlus, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { dossiersApi } from "@/api/dossiers"
import { FolderCreateDialog } from "./FolderCreateDialog"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"
import { useNavigate } from "react-router-dom"

const COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f43f5e",
  "#f97316", "#eab308", "#22c55e", "#06b6d4",
  "#3b82f6", "#64748b",
]

function pickColor() {
  return COLORS[Math.floor(Math.random() * COLORS.length)]
}

interface AddToFolderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  itemType: string
  itemId: string
  itemTitle?: string
  onSuccess?: () => void
}

export function AddToFolderDialog({
  open,
  onOpenChange,
  itemType,
  itemId,
  itemTitle,
  onSuccess,
}: AddToFolderDialogProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  const { data: dossiers = [], isLoading } = useQuery({
    queryKey: ["dossiers"],
    queryFn: () => dossiersApi.list(),
    enabled: open,
  })

  // For uploads: import document (file copy + RAG processing)
  // For other types: link item by reference
  const isUploadType = itemType === "upload" || itemType === "document"

  const addToDossierMutation = useMutation({
    mutationFn: async ({ dossierId }: { dossierId: string }) => {
      if (isUploadType) {
        return dossiersApi.importDocument(dossierId, itemId)
      } else {
        await dossiersApi.addItem(dossierId, {
          item_type: itemType as "presentation" | "email_thread" | "conversation",
          item_id: itemId,
          title: itemTitle || "Sans titre",
        })
        return { filename: itemTitle || "Élément", message: "linked" }
      }
    },
    onSuccess: (data, { dossierId }) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers"] })
      queryClient.invalidateQueries({ queryKey: ["dossier-documents", dossierId] })
      queryClient.invalidateQueries({ queryKey: ["dossier-items", dossierId] })
      queryClient.invalidateQueries({ queryKey: ["dossier", dossierId] })
      const isDuplicate = data.message?.includes("duplicate") || data.message?.includes("already exists")
      toast({
        title: isDuplicate ? "Déjà dans ce dossier" : "Ajouté au dossier",
        description: isDuplicate
          ? `"${data.filename}" existe déjà dans ce dossier.`
          : `"${data.filename}" ajouté au dossier.`,
      })
      onSuccess?.()
      onOpenChange(false)
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      const detail = err.response?.data?.detail
      toast({
        variant: "destructive",
        title: "Erreur",
        description: detail || err.message || "Impossible d'ajouter au dossier.",
      })
    },
  })

  // Create a new dossier then add the item
  const createAndAddMutation = useMutation({
    mutationFn: async (name: string) => {
      const dossier = await dossiersApi.create({ name, color: pickColor() })
      if (isUploadType) {
        await dossiersApi.importDocument(dossier.id, itemId)
      } else {
        await dossiersApi.addItem(dossier.id, {
          item_type: itemType as "presentation" | "email_thread" | "conversation",
          item_id: itemId,
          title: itemTitle || "Sans titre",
        })
      }
      return dossier
    },
    onSuccess: (dossier) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers"] })
      toast({ title: "Dossier créé et élément ajouté" })
      setCreateOpen(false)
      onSuccess?.()
      onOpenChange(false)
      navigate(`/app/dossier/${dossier.id}`)
    },
    onError: (err: Error) => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: err.message || "Impossible de créer le dossier.",
      })
    },
  })

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Ajouter à un dossier</DialogTitle>
            <DialogDescription>
              {itemTitle ? (
                <>Ajouter &quot;{itemTitle}&quot; à un dossier.</>
              ) : (
                <>Sélectionnez un dossier ou créez-en un nouveau.</>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : dossiers.length === 0 ? (
              <div className="text-center py-6 text-sm text-muted-foreground">
                Aucun dossier. Créez-en un pour commencer.
              </div>
            ) : (
              <div className="space-y-1 max-h-[240px] overflow-auto">
                {dossiers.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => addToDossierMutation.mutate({ dossierId: d.id })}
                    disabled={addToDossierMutation.isPending}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors hover:bg-accent"
                  >
                    {d.color && (
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: d.color }}
                      />
                    )}
                    <span className="flex-1 truncate text-sm font-medium">
                      {d.name}
                    </span>
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0">
                      <FileText className="h-3 w-3" />
                      {d.documents_count} doc{d.documents_count > 1 ? "s" : ""}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(true)}
              className="gap-2"
            >
              <FolderPlus className="h-4 w-4" />
              Nouveau dossier
            </Button>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Fermer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <FolderCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(name) =>
          createAndAddMutation.mutateAsync(name).then(() => undefined)
        }
        mode="create"
      />
    </>
  )
}
