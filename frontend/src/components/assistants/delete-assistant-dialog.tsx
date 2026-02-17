import { Loader2, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { Assistant } from "@/types"

interface DeleteAssistantDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  assistant: Assistant | null
  onConfirm: () => void
  isLoading: boolean
}

export function DeleteAssistantDialog({
  open,
  onOpenChange,
  assistant,
  onConfirm,
  isLoading,
}: DeleteAssistantDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <DialogTitle>Supprimer l'assistant</DialogTitle>
          </div>
          <DialogDescription>
            Êtes-vous sûr de vouloir supprimer l'assistant{" "}
            <strong>{assistant?.name}</strong> ? Cette action est irréversible
            et toutes les conversations seront perdues.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Supprimer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
