import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Plus, Bot, AlertCircle, Plug, ExternalLink, Loader2, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useToast } from "@/hooks/use-toast"
import { assistantsApi } from "@/api/assistants"
import { documentsApi } from "@/api/documents"
import { billingApi } from "@/api/billing"
import { AssistantModal } from "@/components/assistants/assistant-modal"
import type { Assistant, Document } from "@/types"

const PLAN_LIMITS = {
  free: 1,
  pro: 3,
}

function AssistantSyncBadge({ collectionId }: { collectionId?: string }) {
  const { data: documents = [] } = useQuery({
    queryKey: ["documents", collectionId],
    queryFn: () => documentsApi.list(collectionId!),
    enabled: !!collectionId,
    refetchInterval: (query) => {
      const docs = query.state.data
      if (docs?.some((d: Document) => d.status === "processing" || d.status === "pending"))
        return 5000
      return false
    },
  })

  if (documents.length === 0) return null

  const hasProcessing = documents.some(
    (d: Document) => d.status === "processing" || d.status === "pending"
  )
  const hasFailed = documents.some((d: Document) => d.status === "failed")
  const allReady = documents.every((d: Document) => d.status === "ready")

  if (hasProcessing)
    return (
      <Badge variant="status" className="gap-1 text-[10px]">
        <Loader2 className="h-3 w-3 animate-spin" />
        Sync…
      </Badge>
    )
  if (allReady)
    return (
      <Badge variant="success" className="gap-1 text-[10px]">
        <CheckCircle2 className="h-3 w-3" />
        Synchronisé
      </Badge>
    )
  if (hasFailed)
    return (
      <Badge variant="destructive" className="gap-1 text-[10px]">
        <AlertCircle className="h-3 w-3" />
        Erreur
      </Badge>
    )

  return null
}

export function AssistantsPage() {
  const navigate = useNavigate()
  const { toast } = useToast()

  const [isModalOpen, setIsModalOpen] = useState(false)

  const { data: subscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: billingApi.getSubscription,
  })

  const maxAssistants = subscription?.is_pro ? PLAN_LIMITS.pro : PLAN_LIMITS.free

  const { data: assistants, isLoading, error } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
  })

  const handleCreateClick = () => {
    setIsModalOpen(true)
  }

  const handleConfigClick = (assistant: Assistant) => {
    navigate(`/app/assistant/${assistant.id}`)
  }

  const isAtLimit = assistants && assistants.length >= maxAssistants

  if (error) {
    return (
      <div className="container py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erreur</AlertTitle>
          <AlertDescription>
            Impossible de charger vos assistants. Veuillez réessayer.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="container py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Mes assistants</h1>
          <p className="mt-1 text-muted-foreground">
            Configurez les assistants qui alimentent vos documents, emails et recherches
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Badge variant="outline" className="text-sm">
            {assistants?.length || 0} / {maxAssistants} assistants
          </Badge>
          {!isAtLimit ? (
            <Button onClick={handleCreateClick}>
              <Plus className="mr-2 h-4 w-4" />
              Créer un assistant
            </Button>
          ) : (
            <Button variant="outline" onClick={() => navigate("/app/billing")}>
              Passer au plan supérieur
            </Button>
          )}
        </div>
      </div>

      {/* Limit warning */}
      {isAtLimit && (
        <Alert className="mb-8">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Limite atteinte</AlertTitle>
          <AlertDescription>
            Vous avez atteint le nombre maximum d'assistants pour votre plan.{" "}
            <Button
              variant="link"
              className="h-auto p-0"
              onClick={() => navigate("/app/billing")}
            >
              Passez au plan supérieur
            </Button>{" "}
            pour créer plus d'assistants.
          </AlertDescription>
        </Alert>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
              <CardFooter>
                <Skeleton className="h-10 w-full" />
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && assistants?.length === 0 && (
        <Card className="flex flex-col items-center justify-center py-16">
          <Bot className="h-16 w-16 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Aucun assistant</h3>
          <p className="mt-2 text-center text-muted-foreground">
            Créez votre premier assistant IA pour commencer.
          </p>
          <Button className="mt-6" onClick={handleCreateClick}>
            <Plus className="mr-2 h-4 w-4" />
            Créer un assistant
          </Button>
        </Card>
      )}

      {/* Assistants grid */}
      {!isLoading && assistants && assistants.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {assistants.map((assistant) => (
            <Card key={assistant.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                      <Bot className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{assistant.name}</CardTitle>
                    </div>
                  </div>
                  <AssistantSyncBadge collectionId={assistant.collection_ids?.[0]} />
                </div>
              </CardHeader>
              <CardContent className="flex-1">
                <p className="line-clamp-3 text-sm text-muted-foreground">
                  {assistant.system_prompt || "Aucun prompt système défini."}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {assistant.collection_ids.length > 0 && (
                    <Badge variant="secondary">
                      {assistant.collection_ids.length} collection(s)
                    </Badge>
                  )}
                  {assistant.integration_ids.length > 0 && (
                    <Badge variant="outline" className="gap-1">
                      <Plug className="h-3 w-3" />
                      {assistant.integration_ids.length} outil(s)
                    </Badge>
                  )}
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  variant="default"
                  className="w-full"
                  onClick={() => handleConfigClick(assistant)}
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Configurer
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal (édition via page de configuration) */}
      <AssistantModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        assistant={null}
        onCreated={(id) => navigate(`/app/assistant/${id}`)}
      />

    </div>
  )
}
