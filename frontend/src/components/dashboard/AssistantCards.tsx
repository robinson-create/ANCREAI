import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { FolderOpen, MessageSquare } from "lucide-react";

const assistants = [
  {
    name: "Trouver l'info",
    slug: "trouver-info",
    emoji: "\u{1F50D}",
    role: "Recherche rapide dans vos sources",
    docs: 15,
    color: "bg-blue-50 dark:bg-blue-950/30",
  },
  {
    name: "Commercial & Dossiers",
    slug: "commercial-dossiers",
    emoji: "\u{1F4BC}",
    role: "Devis, propositions, infos clients",
    docs: 12,
    color: "bg-amber-50 dark:bg-amber-950/30",
  },
  {
    name: "Emails & Réponses",
    slug: "emails-reponses",
    emoji: "\u{2709}\u{FE0F}",
    role: "Emails types, relances, réponses",
    docs: 8,
    color: "bg-emerald-50 dark:bg-emerald-950/30",
  },
];

export function AssistantCards() {
  const navigate = useNavigate();

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Vos assistants
        </h2>
        <Badge variant="status">3 / 3 actifs</Badge>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {assistants.map((a) => (
          <button
            key={a.name}
            onClick={() => navigate(`/app/assistant/${a.slug}`)}
            className="group flex flex-col items-start gap-3 p-4 rounded-lg bg-card border border-border shadow-soft hover:shadow-elevated hover:border-primary/30 transition-all text-left"
          >
            <div className="flex items-center gap-3 w-full">
              <span className="text-2xl">{a.emoji}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-foreground">{a.name}</div>
                <div className="text-xs text-muted-foreground">{a.role}</div>
              </div>
              <MessageSquare className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <FolderOpen className="h-3 w-3" />
              {a.docs} documents connectés
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
