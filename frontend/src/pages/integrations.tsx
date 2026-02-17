import { useNavigate } from "react-router-dom"
import {
  Plug,
  Settings2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

// Connector data per assistant (mirrors assistant-page.tsx)
const assistantsConnectors = [
  {
    slug: "trouver-info",
    name: "Trouver l'info",
    emoji: "\u{1F50D}",
    role: "Recherche rapide dans vos sources",
    connectors: [
      { name: "Google Drive", status: "connected", provider: "google-drive", description: "Fichiers, dossiers, documents" },
      { name: "Notion", status: "disconnected", provider: "notion", description: "Pages, bases de données" },
    ],
  },
  {
    slug: "commercial-dossiers",
    name: "Commercial & Dossiers",
    emoji: "\u{1F4BC}",
    role: "Devis, propositions, clients",
    connectors: [
      { name: "Salesforce", status: "disconnected", provider: "salesforce", description: "CRM - Contacts, deals" },
    ],
  },
  {
    slug: "emails-reponses",
    name: "Emails & Réponses",
    emoji: "\u{2709}\u{FE0F}",
    role: "Emails types, relances, réponses",
    connectors: [
      { name: "Gmail", status: "connected", provider: "gmail", description: "Recherche et envoi d'emails" },
      { name: "Outlook", status: "disconnected", provider: "outlook", description: "Microsoft Outlook / Office 365" },
    ],
  },
]

// All available providers
const availableProviders = [
  { key: "hubspot", name: "HubSpot", description: "CRM - Contacts, deals, companies", color: "bg-orange-500" },
  { key: "salesforce", name: "Salesforce", description: "CRM - Full Salesforce data", color: "bg-blue-500" },
  { key: "pipedrive", name: "Pipedrive", description: "CRM - Deals, contacts, activités", color: "bg-green-600" },
  { key: "gmail", name: "Gmail", description: "Email - Recherche et envoi", color: "bg-red-500" },
  { key: "google-drive", name: "Google Drive", description: "Fichiers, dossiers, documents", color: "bg-yellow-600" },
  { key: "outlook", name: "Outlook", description: "Microsoft Outlook / Office 365", color: "bg-blue-600" },
  { key: "notion", name: "Notion", description: "Pages, bases de données", color: "bg-gray-800" },
  { key: "slack", name: "Slack", description: "Canaux, messages, fichiers", color: "bg-purple-600" },
  { key: "shopify", name: "Shopify", description: "Commandes, produits, clients", color: "bg-green-500" },
  { key: "stripe", name: "Stripe", description: "Clients, factures, abonnements", color: "bg-purple-500" },
]

export function IntegrationsPage() {
  const navigate = useNavigate()

  const totalConnected = assistantsConnectors.reduce(
    (sum, a) => sum + a.connectors.filter((c) => c.status === "connected").length,
    0
  )
  const totalConnectors = assistantsConnectors.reduce((sum, a) => sum + a.connectors.length, 0)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        <Plug className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
        <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">Connecteurs</h1>
        <span className="text-xs text-muted-foreground hidden sm:inline">
          {totalConnected} connecté{totalConnected > 1 ? "s" : ""} sur {totalConnectors} · {assistantsConnectors.length} assistants
        </span>
      </div>

      <div className="flex-1 overflow-auto bg-surface p-3 sm:p-5">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Info banner */}
          <div className="flex items-center gap-3 p-4 bg-accent border border-primary/20 rounded-lg">
            <Plug className="h-5 w-5 text-primary shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">
                Les connecteurs sont rattachés à chaque assistant
              </p>
              <p className="text-xs text-white/70 mt-0.5">
                Gérez les connexions OAuth depuis l'onglet "Configurer" de chaque assistant.
              </p>
            </div>
          </div>

          {/* Per-assistant connectors */}
          {assistantsConnectors.map((assistant) => (
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
                  <Badge variant={assistant.connectors.some((c) => c.status === "connected") ? "success" : "status"}>
                    {assistant.connectors.filter((c) => c.status === "connected").length} / {assistant.connectors.length} actif{assistant.connectors.filter((c) => c.status === "connected").length > 1 ? "s" : ""}
                  </Badge>
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

              {/* Connectors list */}
              <div className="divide-y divide-border">
                {assistant.connectors.map((conn, i) => {
                  const provider = availableProviders.find((p) => p.key === conn.provider)
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-3 px-4 sm:px-5 py-3 hover:bg-muted/30 transition-colors"
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0 ${provider?.color || "bg-muted"}`}>
                        {conn.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-foreground">{conn.name}</div>
                        <div className="text-xs text-muted-foreground">{conn.description}</div>
                      </div>
                      {conn.status === "connected" ? (
                        <Badge variant="success" className="gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          Connecté
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="gap-1">
                          <AlertCircle className="h-3 w-3" />
                          Non connecté
                        </Badge>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}

          {/* Available providers */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              Connecteurs disponibles
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {availableProviders.map((provider) => (
                <div
                  key={provider.key}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all"
                >
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center text-white text-[10px] font-bold shrink-0 ${provider.color}`}>
                    {provider.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium text-foreground truncate">{provider.name}</div>
                    <div className="text-[10px] text-muted-foreground truncate">{provider.description}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
