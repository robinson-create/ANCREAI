import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FolderOpen,
  Plus,
  Search,
  FileText,
  MessageSquare,
  ChevronRight,
  Trash2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { dossiersApi } from "@/api/dossiers";
import { FolderCreateDialog } from "@/components/folders/FolderCreateDialog";
import { useToast } from "@/hooks/use-toast";

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return "À l'instant";
  if (diffMins < 60) return `Il y a ${diffMins} min`;
  if (diffHours < 24) return `Il y a ${diffHours}h`;
  if (diffDays < 7) return `Il y a ${diffDays}j`;
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

const COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f43f5e",
  "#f97316", "#eab308", "#22c55e", "#06b6d4",
  "#3b82f6", "#64748b",
];

function pickColor() {
  return COLORS[Math.floor(Math.random() * COLORS.length)];
}

export function FoldersPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [createOpen, setCreateOpen] = useState(false);
  const [search, setSearch] = useState("");

  const { data: dossiers = [], isLoading } = useQuery({
    queryKey: ["dossiers"],
    queryFn: () => dossiersApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) =>
      dossiersApi.create({ name, color: pickColor() }),
    onSuccess: (dossier) => {
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
      toast({ title: "Dossier créé" });
      setCreateOpen(false);
      navigate(`/app/dossier/${dossier.id}`);
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer le dossier.",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dossiersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dossiers"] });
      toast({ title: "Dossier supprimé" });
    },
  });

  const filteredDossiers = useMemo(() => {
    if (!search.trim()) return dossiers;
    const q = search.toLowerCase();
    return dossiers.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        (d.description && d.description.toLowerCase().includes(q)),
    );
  }, [dossiers, search]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 pt-8 pb-6 md:pt-10 md:pb-6">
        <div className="max-w-4xl mx-auto space-y-5">
          <div className="space-y-1">
            <h1 className="font-heading text-2xl md:text-3xl font-bold text-foreground tracking-tight flex items-center gap-3">
              <FolderOpen className="h-7 w-7 text-primary" />
              Dossiers
            </h1>
            <p className="text-sm text-muted-foreground font-body">
              Vos espaces personnels : importez des documents et échangez avec leur contenu.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un dossier..."
                className="w-full h-10 pl-10 pr-4 text-sm font-body bg-card border border-border rounded-xl outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 text-foreground placeholder:text-muted-foreground/60 transition-all"
              />
            </div>
            <Button
              variant="premium"
              size="sm"
              className="gap-2 shrink-0"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="h-4 w-4" />
              Nouveau dossier
            </Button>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 bg-background rounded-t-3xl border-t border-border px-6 py-6 md:py-8 overflow-auto">
        <div className="max-w-4xl mx-auto">
          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filteredDossiers.length === 0 ? (
            <div className="text-center py-16 space-y-4">
              <FolderOpen className="h-12 w-12 text-muted-foreground/30 mx-auto" />
              <div>
                <p className="text-sm text-muted-foreground font-body">
                  {search
                    ? "Aucun dossier trouvé."
                    : "Aucun dossier pour le moment."}
                </p>
                {!search && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 gap-2"
                    onClick={() => setCreateOpen(true)}
                  >
                    <Plus className="h-4 w-4" />
                    Créer un dossier
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDossiers.map((dossier) => (
                <button
                  key={dossier.id}
                  onClick={() => navigate(`/app/dossier/${dossier.id}`)}
                  className="group text-left p-5 rounded-xl border border-border bg-card hover:shadow-lg hover:border-primary/20 transition-all relative"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center"
                        style={{
                          backgroundColor: dossier.color
                            ? `${dossier.color}20`
                            : "var(--muted)",
                        }}
                      >
                        <FolderOpen
                          className="h-5 w-5"
                          style={{
                            color: dossier.color || "var(--muted-foreground)",
                          }}
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (
                            window.confirm(
                              `Supprimer "${dossier.name}" et tout son contenu ?`,
                            )
                          ) {
                            deleteMutation.mutate(dossier.id);
                          }
                        }}
                        className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                      <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>

                  <div className="text-sm font-semibold text-foreground font-body truncate">
                    {dossier.name}
                  </div>
                  {dossier.description && (
                    <div className="text-xs text-muted-foreground font-body truncate mt-0.5">
                      {dossier.description}
                    </div>
                  )}

                  <div className="flex items-center gap-2 mt-3">
                    {dossier.documents_count > 0 && (
                      <Badge
                        variant="outline"
                        className="text-[10px] px-1.5 py-0 gap-1"
                      >
                        <FileText className="h-3 w-3" />
                        {dossier.documents_count} doc
                        {dossier.documents_count > 1 ? "s" : ""}
                      </Badge>
                    )}
                    {dossier.conversations_count > 0 && (
                      <Badge
                        variant="outline"
                        className="text-[10px] px-1.5 py-0 gap-1"
                      >
                        <MessageSquare className="h-3 w-3" />
                        {dossier.conversations_count} conv
                      </Badge>
                    )}
                    {dossier.documents_count === 0 &&
                      dossier.conversations_count === 0 && (
                        <span className="text-[11px] text-muted-foreground/60 font-body">
                          Vide
                        </span>
                      )}
                  </div>

                  <div className="text-[10px] text-muted-foreground/50 mt-2 font-body">
                    {formatRelativeDate(dossier.updated_at)}
                  </div>
                </button>
              ))}

              {/* Create card */}
              <button
                onClick={() => setCreateOpen(true)}
                className="flex flex-col items-center justify-center p-5 rounded-xl border border-dashed border-border hover:border-primary/30 hover:bg-muted/30 transition-all min-h-[140px]"
              >
                <Plus className="h-6 w-6 text-muted-foreground mb-2" />
                <span className="text-sm font-medium text-muted-foreground font-body">
                  Nouveau dossier
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      <FolderCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(name) =>
          createMutation.mutateAsync(name).then(() => undefined)
        }
        mode="create"
      />
    </div>
  );
}
