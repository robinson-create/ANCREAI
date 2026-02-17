import { Badge } from "@/components/ui/badge";
import { FileText, Clock } from "lucide-react";

const documents = [
  { title: "NDA — Partenariat TechCo", type: "NDA", status: "draft", date: "Il y a 2h", assistant: "Juridique" },
  { title: "Devis maintenance annuelle", type: "Devis", status: "final", date: "Il y a 4h", assistant: "Commercial" },
  { title: "CR Réunion Q1 2025", type: "Compte-rendu", status: "review", date: "Hier", assistant: "Commercial" },
  { title: "Relance client Dupont", type: "Email", status: "draft", date: "Hier", assistant: "Commercial" },
  { title: "Note interne — Politique télétravail", type: "Note", status: "final", date: "Lun.", assistant: "RH" },
];

const statusLabels: Record<string, { label: string; variant: "status" | "success" | "gold" }> = {
  draft: { label: "Brouillon", variant: "status" },
  final: { label: "Final", variant: "success" },
  review: { label: "À relire", variant: "gold" },
};

export function RecentDocuments() {
  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Documents récents
        </h2>
        <button className="text-xs text-muted-foreground hover:text-foreground transition-colors">
          Tout voir →
        </button>
      </div>
      <div className="bg-card rounded-lg border border-border shadow-soft overflow-hidden">
        <div className="divide-y divide-border">
          {documents.map((doc, i) => {
            const st = statusLabels[doc.status];
            return (
              <button
                key={i}
                className="flex items-center gap-4 w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center justify-center w-8 h-8 rounded-md bg-muted shrink-0">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{doc.title}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground">{doc.type}</span>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-xs text-muted-foreground">{doc.assistant}</span>
                  </div>
                </div>
                <Badge variant={st.variant} className="shrink-0">{st.label}</Badge>
                <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
                  <Clock className="h-3 w-3" />
                  {doc.date}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
