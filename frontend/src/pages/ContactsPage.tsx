/**
 * Contacts page - List view with filters and search.
 */

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Search, Mail, Users, Building, ChevronRight } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { contactsApi, ContactBrief } from "@/api/contacts"
import { ContactCreateDialog } from "@/components/contacts/ContactCreateDialog"
import { ContactImportDialog } from "@/components/contacts/ContactImportDialog"
import { useToast } from "@/hooks/use-toast"

export function ContactsPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [contactType, setContactType] = useState<string | undefined>()
  const [source, setSource] = useState<string | undefined>()
  const [createOpen, setCreateOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)

  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Fetch contacts
  const { data: contacts = [], isLoading } = useQuery({
    queryKey: ["contacts", searchQuery, contactType, source],
    queryFn: () =>
      contactsApi.list({
        search: searchQuery || undefined,
        contact_type: contactType,
        source,
        limit: 100,
      }),
    staleTime: 30_000,
  })

  const handleContactClick = (contact: ContactBrief) => {
    navigate(`/app/contacts/${contact.id}`)
  }

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
    return colors[type] || colors.autre
  }

  const getInitials = (contact: ContactBrief): string => {
    const first = contact.first_name?.[0] || ""
    const last = contact.last_name?.[0] || ""
    if (first || last) {
      return (first + last).toUpperCase()
    }
    return contact.primary_email[0].toUpperCase()
  }

  const createMutation = useMutation({
    mutationFn: contactsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      toast({ title: "Contact créé avec succès" })
      setCreateOpen(false)
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer le contact.",
      })
    },
  })

  const importMutation = useMutation({
    mutationFn: contactsApi.importFromEmail,
    onSuccess: (report) => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] })
      toast({
        title: "Import terminé",
        description: `${report.contacts_created} contact(s) créé(s), ${report.contacts_updated} mis à jour.`,
      })
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible d'importer les contacts.",
      })
    },
  })

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b bg-background">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Contacts</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {contacts.length} contact{contacts.length !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="flex gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setImportOpen(true)}
          >
            <Mail className="w-4 h-4 mr-2" />
            Importer depuis emails
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Nouveau contact
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 p-4 bg-muted/30 border-b">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher un contact..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select
          value={contactType || "all"}
          onValueChange={(val) =>
            setContactType(val === "all" ? undefined : val)
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Tous les types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les types</SelectItem>
            <SelectItem value="client">Client</SelectItem>
            <SelectItem value="prospect">Prospect</SelectItem>
            <SelectItem value="partenaire">Partenaire</SelectItem>
            <SelectItem value="fournisseur">Fournisseur</SelectItem>
            <SelectItem value="candidat">Candidat</SelectItem>
            <SelectItem value="interne">Interne</SelectItem>
            <SelectItem value="autre">Autre</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={source || "all"}
          onValueChange={(val) => setSource(val === "all" ? undefined : val)}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Toutes les sources" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes les sources</SelectItem>
            <SelectItem value="manual">Manuel</SelectItem>
            <SelectItem value="import_email">Import email</SelectItem>
            <SelectItem value="agent">Agent</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Contacts list */}
      <div className="flex-1 p-6 overflow-y-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-full">
            <div className="text-muted-foreground">Chargement...</div>
          </div>
        ) : contacts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
            <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <Users className="w-8 h-8 text-muted-foreground" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Aucun contact</h2>
            <p className="text-muted-foreground mb-6">
              Créez votre premier contact ou importez depuis vos emails.
            </p>
            <div className="flex gap-3">
              <Button onClick={() => setImportOpen(true)}>
                <Mail className="w-4 h-4 mr-2" />
                Importer depuis emails
              </Button>
              <Button variant="outline" onClick={() => setCreateOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Nouveau contact
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {contacts.map((contact) => {
              const fullName =
                `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
                "Sans nom"

              return (
                <Card
                  key={contact.id}
                  className="p-4 cursor-pointer hover:shadow-md hover:border-primary/20 transition-all group"
                  onClick={() => handleContactClick(contact)}
                >
                  <div className="flex items-start gap-3">
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0 font-medium text-sm text-primary">
                      {getInitials(contact)}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h3 className="font-semibold text-foreground truncate">
                          {fullName}
                        </h3>
                        <Badge
                          variant="outline"
                          className={`shrink-0 ${getContactTypeColor(
                            contact.contact_type
                          )}`}
                        >
                          {contact.contact_type}
                        </Badge>
                      </div>

                      <p className="text-sm text-muted-foreground truncate mb-2">
                        {contact.primary_email}
                      </p>

                      {contact.company_name && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Building className="w-3 h-3 shrink-0" />
                          <span className="truncate">{contact.company_name}</span>
                        </div>
                      )}
                    </div>

                    {/* Arrow */}
                    <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </div>

      {/* Dialogs */}
      <ContactCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(data) => createMutation.mutateAsync(data)}
      />
      <ContactImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onSubmit={(data) => importMutation.mutateAsync(data)}
      />
    </div>
  )
}
