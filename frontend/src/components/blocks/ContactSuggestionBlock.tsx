/**
 * CopilotKit block for contact suggestions from agent.
 */

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Users, Check, X, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { contactsApi } from "@/api/contacts"
import { useToast } from "@/hooks/use-toast"

interface ContactSuggestionBlockProps {
  block: {
    action: "create" | "update"
    contact_id?: string
    email: string
    first_name?: string
    last_name?: string
    phone?: string
    company_name?: string
    title?: string
    confidence: number
    reason: string
  }
}

export function ContactSuggestionBlock({
  block,
}: ContactSuggestionBlockProps) {
  const [dismissed, setDismissed] = useState(false)
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (block.action === "create") {
        return contactsApi.create({
          primary_email: block.email,
          first_name: block.first_name,
          last_name: block.last_name,
          phone: block.phone,
          title: block.title,
          source: "agent",
        })
      } else {
        // Update existing contact
        if (!block.contact_id) {
          throw new Error("Contact ID required for update")
        }
        return contactsApi.update(block.contact_id, {
          first_name: block.first_name,
          last_name: block.last_name,
          phone: block.phone,
          title: block.title,
        })
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      toast({
        title:
          block.action === "create"
            ? "Contact créé"
            : "Contact mis à jour",
      })
      setDismissed(true)
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: `Impossible d'appliquer la suggestion: ${error}`,
      })
    },
  })

  if (dismissed) {
    return null
  }

  const getConfidenceBadgeVariant = () => {
    if (block.confidence >= 0.8) return "default"
    if (block.confidence >= 0.5) return "secondary"
    return "outline"
  }

  const getConfidenceColor = () => {
    if (block.confidence >= 0.8) return "text-green-600"
    if (block.confidence >= 0.5) return "text-yellow-600"
    return "text-orange-600"
  }

  return (
    <Card className="my-4 border-primary/20">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="w-5 h-5 text-primary" />
          Suggestion de contact
          {block.confidence < 0.6 && (
            <AlertCircle className="w-4 h-4 text-orange-500" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Reason */}
        <div>
          <p className="text-sm mb-2">{block.reason}</p>
          <Badge variant={getConfidenceBadgeVariant()}>
            <span className={getConfidenceColor()}>
              Confiance: {(block.confidence * 100).toFixed(0)}%
            </span>
          </Badge>
        </div>

        {/* Details */}
        <div className="space-y-2 text-sm bg-muted/50 p-3 rounded-md">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="font-medium text-muted-foreground">
                Action:
              </span>
            </div>
            <div>
              {block.action === "create"
                ? "Créer nouveau contact"
                : "Mettre à jour contact"}
            </div>

            <div>
              <span className="font-medium text-muted-foreground">
                Email:
              </span>
            </div>
            <div className="truncate">{block.email}</div>

            {block.first_name && (
              <>
                <div>
                  <span className="font-medium text-muted-foreground">
                    Prénom:
                  </span>
                </div>
                <div>{block.first_name}</div>
              </>
            )}

            {block.last_name && (
              <>
                <div>
                  <span className="font-medium text-muted-foreground">
                    Nom:
                  </span>
                </div>
                <div>{block.last_name}</div>
              </>
            )}

            {block.phone && (
              <>
                <div>
                  <span className="font-medium text-muted-foreground">
                    Téléphone:
                  </span>
                </div>
                <div>{block.phone}</div>
              </>
            )}

            {block.company_name && (
              <>
                <div>
                  <span className="font-medium text-muted-foreground">
                    Société:
                  </span>
                </div>
                <div>{block.company_name}</div>
              </>
            )}

            {block.title && (
              <>
                <div>
                  <span className="font-medium text-muted-foreground">
                    Fonction:
                  </span>
                </div>
                <div>{block.title}</div>
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => applyMutation.mutate()}
            disabled={applyMutation.isPending}
          >
            <Check className="w-4 h-4 mr-2" />
            {block.action === "create" ? "Créer" : "Mettre à jour"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDismissed(true)}
            disabled={applyMutation.isPending}
          >
            <X className="w-4 h-4 mr-2" />
            Ignorer
          </Button>
        </div>

        {block.confidence < 0.6 && (
          <p className="text-xs text-muted-foreground flex items-start gap-2">
            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
            Confiance faible - vérifiez les informations avant d'appliquer.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
