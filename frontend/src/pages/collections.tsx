import { useNavigate } from "react-router-dom"
import {
  FolderOpen,
  FileText,
  Link as LinkIcon,
  Settings2,
  Upload,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

// Reuse same assistant data shape as assistant-page
const assistantsCollections = [
  {
    slug: "trouver-info",
    name: "Trouver l'info",
    emoji: "\u{1F50D}",
    role: "Recherche rapide dans vos sources",
    documents: [
      { name: "Guide onboarding.pdf", type: "PDF", status: "ready" },
      { name: "Process qualité v3.docx", type: "Word", status: "ready" },
    ],
    links: [
      { url: "https://docs.company.fr", label: "Documentation interne" },
      { url: "https://wiki.company.fr", label: "Wiki équipe" },
    ],
  },
  {
    slug: "commercial-dossiers",
    name: "Commercial & Dossiers",
    emoji: "\u{1F4BC}",
    role: "Devis, propositions, clients",
    documents: [
      { name: "Grille tarifaire 2026.xlsx", type: "Excel", status: "ready" },
      { name: "Template proposition.docx", type: "Word", status: "ready" },
      { name: "CGV 2026.pdf", type: "PDF", status: "ready" },
    ],
    links: [
      { url: "https://crm.company.fr", label: "CRM" },
    ],
  },
  {
    slug: "emails-reponses",
    name: "Emails & Réponses",
    emoji: "\u{2709}\u{FE0F}",
    role: "Emails types, relances, réponses",
    documents: [
      { name: "Réponses types clients.docx", type: "Word", status: "ready" },
      { name: "Charte de communication.pdf", type: "PDF", status: "ready" },
    ],
    links: [],
  },
]

export function CollectionsPage() {
  const navigate = useNavigate()

  const totalDocs = assistantsCollections.reduce((sum, a) => sum + a.documents.length, 0)
  const totalLinks = assistantsCollections.reduce((sum, a) => sum + a.links.length, 0)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        <FolderOpen className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
        <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">Collections</h1>
        <span className="text-xs text-muted-foreground hidden sm:inline">
          {totalDocs} documents · {totalLinks} liens · {assistantsCollections.length} assistants
        </span>
      </div>

      <div className="flex-1 overflow-auto bg-surface p-3 sm:p-5">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Info banner */}
          <div className="flex items-center gap-3 p-4 bg-accent border border-primary/20 rounded-lg">
            <FolderOpen className="h-5 w-5 text-primary shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">
                Chaque assistant possède sa propre collection
              </p>
              <p className="text-xs text-white/70 mt-0.5">
                Ajoutez documents et liens depuis l'onglet "Configurer" de chaque assistant.
              </p>
            </div>
          </div>

          {/* Assistant collections */}
          {assistantsCollections.map((assistant) => (
            <div
              key={assistant.slug}
              className="bg-card border border-border rounded-lg shadow-soft overflow-hidden"
            >
              {/* Assistant header */}
              <div className="flex items-center gap-3 px-4 sm:px-5 py-4 border-b border-border">
                <span className="text-xl">{assistant.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground">{assistant.name}</div>
                  <div className="text-xs text-muted-foreground">{assistant.role}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="status">
                    {assistant.documents.length} doc{assistant.documents.length > 1 ? "s" : ""}
                  </Badge>
                  {assistant.links.length > 0 && (
                    <Badge variant="status">
                      {assistant.links.length} lien{assistant.links.length > 1 ? "s" : ""}
                    </Badge>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    onClick={() => navigate(`/app/assistant/${assistant.slug}`)}
                  >
                    <Settings2 className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Configurer</span>
                  </Button>
                </div>
              </div>

              {/* Documents */}
              <div className="divide-y divide-border">
                {assistant.documents.map((doc, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 px-4 sm:px-5 py-3 hover:bg-muted/30 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                      <FileText className="h-3.5 w-3.5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground truncate">{doc.name}</div>
                      <div className="text-xs text-muted-foreground">{doc.type}</div>
                    </div>
                    <Badge variant={doc.status === "ready" ? "success" : "status"}>
                      {doc.status === "ready" ? "Indexé" : "En cours"}
                    </Badge>
                  </div>
                ))}

                {/* Links */}
                {assistant.links.map((link, i) => (
                  <div
                    key={`link-${i}`}
                    className="flex items-center gap-3 px-4 sm:px-5 py-3 hover:bg-muted/30 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center shrink-0">
                      <LinkIcon className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground truncate">{link.label}</div>
                      <div className="text-xs text-muted-foreground truncate">{link.url}</div>
                    </div>
                  </div>
                ))}

                {assistant.documents.length === 0 && assistant.links.length === 0 && (
                  <div className="px-5 py-8 text-center">
                    <Upload className="h-8 w-8 text-muted-foreground mx-auto" />
                    <p className="text-sm text-muted-foreground mt-2">Aucune source configurée</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3 gap-1.5"
                      onClick={() => navigate(`/app/assistant/${assistant.slug}`)}
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                      Ajouter des sources
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
