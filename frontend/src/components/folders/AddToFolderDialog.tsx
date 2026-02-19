import { useState } from "react"
import { Loader2, FolderPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { foldersApi } from "@/api/folders"
import { FolderCreateDialog } from "./FolderCreateDialog"
import type { Folder, FolderItemAdd } from "@/types"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"

interface AddToFolderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  itemType: FolderItemAdd["item_type"]
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
  const [createOpen, setCreateOpen] = useState(false)

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["folders"],
    queryFn: () => foldersApi.list(),
    enabled: open,
  })

  const addMutation = useMutation({
    mutationFn: ({ folderId }: { folderId: string }) =>
      foldersApi.addItem(folderId, { item_type: itemType, item_id: itemId }),
    onSuccess: (_, { folderId }) => {
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      queryClient.invalidateQueries({ queryKey: ["folder-items", folderId] })
      queryClient.invalidateQueries({ queryKey: ["folder", folderId] })
      toast({ title: "Ajouté au dossier" })
      onOpenChange(false)
      onSuccess?.()
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      const detail = err.response?.data?.detail
      const isAlreadyInFolder = typeof detail === "string" && detail.toLowerCase().includes("déjà")
      toast({
        variant: "destructive",
        title: isAlreadyInFolder ? "Déjà ajouté" : "Erreur",
        description: isAlreadyInFolder
          ? "Cet élément est déjà dans ce dossier."
          : (detail || err.message || "Impossible d'ajouter au dossier."),
      })
    },
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create({ name }),
    onSuccess: async (folder: Folder) => {
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      await foldersApi.addItem(folder.id, { item_type: itemType, item_id: itemId })
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      queryClient.invalidateQueries({ queryKey: ["folder-items", folder.id] })
      queryClient.invalidateQueries({ queryKey: ["folder", folder.id] })
      toast({ title: "Dossier créé et élément ajouté" })
      setCreateOpen(false)
      onOpenChange(false)
      onSuccess?.()
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
                <>
                  Ajouter &quot;{itemTitle}&quot; à un dossier.
                </>
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
            ) : (
              <div className="space-y-1 max-h-[240px] overflow-auto">
                {folders.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => addMutation.mutate({ folderId: f.id })}
                    disabled={addMutation.isPending}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent text-left transition-colors"
                  >
                    {f.color && (
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ backgroundColor: f.color }}
                      />
                    )}
                    <span className="flex-1 truncate text-sm font-medium">
                      {f.name}
                    </span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {f.item_counts.conversation + f.item_counts.document + f.item_counts.email_thread} élément(s)
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
        onSubmit={(name) => createMutation.mutateAsync(name).then(() => undefined)}
        mode="create"
      />
    </>
  )
}
