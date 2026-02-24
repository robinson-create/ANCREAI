import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { assistantsApi } from "@/api/assistants"
import type { Assistant } from "@/types"

const assistantSchema = z.object({
  name: z.string().min(1, "Le nom est requis"),
  system_prompt: z.string().optional(),
})

type AssistantFormData = z.infer<typeof assistantSchema>

interface AssistantModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  assistant: Assistant | null
  onCreated?: (id: string) => void
}

export function AssistantModal({
  open,
  onOpenChange,
  assistant: _assistant,
  onCreated,
}: AssistantModalProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssistantFormData>({
    resolver: zodResolver(assistantSchema),
    defaultValues: {
      name: "",
      system_prompt: "",
    },
  })

  useEffect(() => {
    reset({
      name: "",
      system_prompt: "",
    })
  }, [open, reset])

  const createMutation = useMutation({
    mutationFn: (data: AssistantFormData) =>
      assistantsApi.create({
        name: data.name,
        system_prompt: data.system_prompt || "",
        model: "mistral-medium-latest",
        collection_ids: [],
        integration_ids: [],
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["assistants"] })
      toast({
        title: "Assistant créé",
        description: "Redirection vers la page de configuration…",
      })
      onOpenChange(false)
      onCreated?.(created.id)
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer l'assistant.",
      })
    },
  })

  const onSubmit = (data: AssistantFormData) => {
    createMutation.mutate(data)
  }

  const isLoading = createMutation.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Créer un assistant</DialogTitle>
          <DialogDescription>
            Donnez un nom et un prompt de base. La configuration complète se fait sur la page dédiée.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nom de l'assistant</Label>
              <Input
                id="name"
                placeholder="Mon assistant"
                {...register("name")}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="system_prompt">Prompt système</Label>
              <Textarea
                id="system_prompt"
                placeholder="Tu es un assistant utile et amical..."
                rows={4}
                {...register("system_prompt")}
              />
              <p className="text-xs text-muted-foreground">
                Le prompt définit le comportement de base. Vous pourrez affiner
                tout sur la page de configuration.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer et configurer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
