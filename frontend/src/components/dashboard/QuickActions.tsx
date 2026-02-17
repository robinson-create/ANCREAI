import { PenLine, Mail, FileSearch, CalendarCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

const actions = [
  {
    label: "Rédiger un document",
    description: "Contrat, devis, NDA, CR…",
    icon: PenLine,
    path: "/app/documents",
  },
  {
    label: "Composer un email",
    description: "Avec ton & contexte",
    icon: Mail,
    path: "/app/email",
  },
  {
    label: "Résumer un dossier",
    description: "Synthèse depuis vos sources",
    icon: FileSearch,
    path: "/app/documents",
  },
  {
    label: "Préparer un rendez-vous",
    description: "Briefing & points clés",
    icon: CalendarCheck,
    path: "/app/documents",
  },
];

export function QuickActions() {
  const navigate = useNavigate();

  return (
    <section>
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        Actions rapides
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={() => navigate(a.path)}
            className="group flex flex-col items-start gap-2 p-4 rounded-lg bg-card border border-border shadow-soft hover:shadow-elevated hover:border-primary/30 transition-all text-left"
          >
            <div className="flex items-center justify-center w-9 h-9 rounded-md bg-accent group-hover:bg-gradient-blue group-hover:text-white transition-colors">
              <a.icon className="h-4.5 w-4.5 text-primary group-hover:text-white" />
            </div>
            <div>
              <div className="text-sm font-medium text-foreground">{a.label}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{a.description}</div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
