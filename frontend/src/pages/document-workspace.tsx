import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Download, Eye, Clock, Search, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const documents = [
  { title: "NDA — Partenariat TechCo", type: "Contrat", date: "10 fév. 2026", status: "Finalisé" },
  { title: "Devis Transformation Digitale", type: "Devis", date: "8 fév. 2026", status: "Brouillon" },
  { title: "CR Réunion équipe produit", type: "Compte-rendu", date: "5 fév. 2026", status: "Finalisé" },
  { title: "Proposition commerciale Acme", type: "Devis", date: "3 fév. 2026", status: "Envoyé" },
  { title: "Note interne — Process onboarding", type: "Note", date: "1 fév. 2026", status: "Brouillon" },
];

export const DocumentWorkspace = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = searchQuery
    ? documents.filter(
        (d) =>
          d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.type.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : documents;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        <FileText className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
        <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">Documents</h1>
        <span className="text-xs text-muted-foreground">{filtered.length} docs</span>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Rechercher…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 w-36 sm:w-56 text-sm"
            />
          </div>
          <Button
            variant="premium"
            size="sm"
            className="gap-1.5 shrink-0"
            onClick={() => navigate("/app/documents")}
          >
            <Plus className="h-3.5 w-3.5" />
            Nouveau
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-surface p-3 sm:p-5">
        <div className="max-w-4xl mx-auto space-y-2">
          {filtered.map((doc) => (
            <div
              key={doc.title}
              className="group flex items-center gap-3 sm:gap-4 px-3 sm:px-4 py-3 sm:py-4 rounded-lg bg-card border border-border hover:shadow-soft hover:border-primary/20 transition-all cursor-pointer"
            >
              <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-accent flex items-center justify-center shrink-0">
                <FileText className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-foreground truncate">{doc.title}</div>
                <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1 sm:gap-2 flex-wrap">
                  <span>{doc.type}</span>
                  <span>·</span>
                  <span>{doc.date}</span>
                </div>
              </div>
              <Badge className="shrink-0" variant={doc.status === "Finalisé" ? "default" : doc.status === "Envoyé" ? "secondary" : "outline"}>
                {doc.status}
              </Badge>
              <div className="hidden sm:flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Eye className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Download className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-12 text-sm text-muted-foreground">Aucun document trouvé</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentWorkspace;
