/**
 * Contact detail page - View and edit contact with history timeline.
 */

import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  Edit,
  Trash,
  Mail,
  FileText,
  Building,
  MapPin,
  Phone,
  Globe,
  Tag,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { contactsApi } from "@/api/contacts"
import { useToast } from "@/hooks/use-toast"
import { formatDistanceToNow } from "date-fns"
import { fr } from "date-fns/locale"
import { useState } from "react"
import { ContactEditDialog } from "@/components/contacts/ContactEditDialog"

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)

  // Fetch contact
  const { data: contact, isLoading } = useQuery({
    queryKey: ["contacts", contactId],
    queryFn: () => contactsApi.get(contactId!),
    enabled: !!contactId,
  })

  // Fetch update history
  const { data: updates = [] } = useQuery({
    queryKey: ["contacts", contactId, "updates"],
    queryFn: () => contactsApi.getUpdates(contactId!),
    enabled: !!contactId,
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: any) => contactsApi.update(contactId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts", contactId] })
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      toast({ title: "Contact mis à jour" })
      setShowEditDialog(false)
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de mettre à jour le contact.",
      })
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => contactsApi.delete(contactId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      toast({ title: "Contact supprimé" })
      navigate("/app/contacts")
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de supprimer le contact.",
      })
    },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <p className="text-muted-foreground">Chargement...</p>
      </div>
    )
  }

  if (!contact) {
    return (
      <div className="flex justify-center items-center h-full">
        <p className="text-muted-foreground">Contact introuvable</p>
      </div>
    )
  }

  const fullName =
    `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
    "Sans nom"

  const getContactTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      client: "bg-green-100 text-green-800 border-green-200",
      prospect: "bg-blue-100 text-blue-800 border-blue-200",
      partenaire: "bg-purple-100 text-purple-800 border-purple-200",
      fournisseur: "bg-orange-100 text-orange-800 border-orange-200",
      candidat: "bg-pink-100 text-pink-800 border-pink-200",
      interne: "bg-gray-100 text-gray-800 border-gray-200",
      autre: "bg-gray-50 text-gray-600 border-gray-200",
    }
    return colors[type] || "bg-gray-50 text-gray-600 border-gray-200"
  }

  const formatSourceLabel = (source: string | null | undefined): string => {
    if (!source) return "Inconnue"
    const labels: Record<string, string> = {
      agent: "Assistant IA",
      manual: "Manuel",
      email: "Email",
      email_import: "Import email",
      import_email: "Import email",
      crm: "CRM",
    }
    return labels[source] || source.replace(/_/g, " ")
  }

  const formatUpdateTypeLabel = (updateType: string): string => {
    const labels: Record<string, string> = {
      create: "Création du contact",
      created: "Création du contact",
      update: "Mise à jour",
      updated: "Mise à jour",
      enrich: "Enrichissement",
      enriched: "Enrichissement",
      contact_create: "Création du contact",
      contact_update: "Mise à jour du contact",
      contact_added_dev: "Ajout du contact",
      add_contact_dev: "Ajout du contact",
      contact_add_dev: "Ajout du contact",
    }
    return labels[updateType] || updateType.replace(/_/g, " ")
  }

  const formatFieldLabel = (fieldName: string): string => {
    const labels: Record<string, string> = {
      first_name: "Prénom",
      last_name: "Nom",
      primary_email: "Email",
      phone: "Téléphone",
      title: "Fonction",
      contact_type: "Type",
      company_name: "Société",
      language: "Langue",
      country: "Pays",
      city: "Ville",
      address: "Adresse",
      notes: "Notes",
      tags: "Tags",
    }
    return labels[fieldName] || fieldName.replace(/_/g, " ")
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-background">
      {/* Header */}
      <div className="p-6 border-b bg-background sticky top-0 z-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/app/contacts")}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Retour
        </Button>

        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center font-medium text-lg text-primary">
              {contact.first_name?.[0] || contact.primary_email[0]}
              {contact.last_name?.[0] || ""}
            </div>

            <div>
              <h1 className="text-2xl font-bold">{fullName}</h1>
              <p className="text-sm text-muted-foreground">
                {contact.primary_email}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <Badge
                  variant="outline"
                  className={getContactTypeColor(contact.contact_type)}
                >
                  {contact.contact_type}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {formatSourceLabel(contact.source)}
                </Badge>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/app/email?contact=${contact.id}`)}
            >
              <Mail className="w-4 h-4 mr-2" />
              Écrire un email
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/app/documents?contact=${contact.id}`)}
            >
              <FileText className="w-4 h-4 mr-2" />
              Créer un document
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEditDialog(true)}
            >
              <Edit className="w-4 h-4 mr-2" />
              Modifier
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteDialog(true)}
            >
              <Trash className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-6 space-y-6">
        {/* Details card */}
        <Card>
          <CardHeader>
            <CardTitle>Informations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {contact.phone && (
              <div className="flex items-center gap-3">
                <Phone className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">{contact.phone}</span>
              </div>
            )}

            {contact.title && (
              <div className="flex items-start gap-3">
                <Building className="w-4 h-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Fonction</p>
                  <p className="text-sm text-muted-foreground">
                    {contact.title}
                  </p>
                </div>
              </div>
            )}

            {contact.company && (
              <div className="flex items-start gap-3">
                <Building className="w-4 h-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Société</p>
                  <p className="text-sm text-muted-foreground">
                    {contact.company.company_name}
                  </p>
                  {contact.company.company_domain && (
                    <p className="text-xs text-muted-foreground">
                      {contact.company.company_domain}
                    </p>
                  )}
                </div>
              </div>
            )}

            {(contact.city || contact.country) && (
              <div className="flex items-start gap-3">
                <MapPin className="w-4 h-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Localisation</p>
                  <p className="text-sm text-muted-foreground">
                    {[contact.city, contact.country]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                </div>
              </div>
            )}

            {contact.language && (
              <div className="flex items-center gap-3">
                <Globe className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">Langue: {contact.language}</span>
              </div>
            )}

            {contact.tags && contact.tags.length > 0 && (
              <div className="flex items-start gap-3">
                <Tag className="w-4 h-4 text-muted-foreground mt-0.5" />
                <div className="flex flex-wrap gap-2">
                  {contact.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {contact.notes && (
              <div>
                <p className="text-sm font-medium mb-1">Notes</p>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {contact.notes}
                </p>
              </div>
            )}

            <Separator />

            <div className="text-xs text-muted-foreground space-y-1">
              <p>
                Créé:{" "}
                {formatDistanceToNow(new Date(contact.created_at), {
                  addSuffix: true,
                  locale: fr,
                })}
              </p>
              <p>
                Modifié:{" "}
                {formatDistanceToNow(new Date(contact.updated_at), {
                  addSuffix: true,
                  locale: fr,
                })}
              </p>
              <p>Confiance: {(contact.confidence_score * 100).toFixed(0)}%</p>
            </div>
          </CardContent>
        </Card>

        {/* Update history */}
        {updates.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Historique</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {updates.map((update, index) => (
                  <div key={update.created_at} className="relative">
                    {index < updates.length - 1 && (
                      <div className="absolute left-2 top-6 bottom-0 w-px bg-border" />
                    )}
                    <div className="flex items-start gap-3">
                      <div className="w-4 h-4 rounded-full bg-primary mt-1 relative z-10" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">
                            {formatUpdateTypeLabel(update.update_type)}
                          </span>
                          {update.field_name && (
                            <Badge variant="outline" className="text-xs">
                              {formatFieldLabel(update.field_name)}
                            </Badge>
                          )}
                        </div>
                        {update.source && (
                          <p className="text-xs text-muted-foreground">
                            Source: {formatSourceLabel(update.source)}
                          </p>
                        )}
                        {update.confidence && (
                          <p className="text-xs text-muted-foreground">
                            Confiance: {(update.confidence * 100).toFixed(0)}%
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">
                          {formatDistanceToNow(new Date(update.created_at), {
                            addSuffix: true,
                            locale: fr,
                          })}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer le contact?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. Le contact "{fullName}" sera
              définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit dialog */}
      <ContactEditDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        onSubmit={(data) => updateMutation.mutateAsync(data)}
        contact={contact}
      />
    </div>
  )
}
