import { useState, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Folder,
  Plus,
  Search,
  MessageSquare,
  FileText,
  Mail,
  ChevronRight,
  Trash2,
  Pencil,
  ExternalLink,
  Loader2,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { foldersApi } from "@/api/folders";
import { FolderCreateDialog } from "@/components/folders/FolderCreateDialog";
import { useToast } from "@/hooks/use-toast";
import type { FolderItem } from "@/types";

const ITEM_TABS = [
  { value: "all", label: "Tout" },
  { value: "conversation", label: "Conversations" },
  { value: "document", label: "Documents" },
  { value: "email_thread", label: "Emails" },
] as const;

type ItemTab = (typeof ITEM_TABS)[number]["value"];

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

function itemIcon(type: FolderItem["item_type"]) {
  switch (type) {
    case "conversation":
      return <MessageSquare className="h-4 w-4 text-violet-500" />;
    case "document":
      return <FileText className="h-4 w-4 text-blue-500" />;
    case "email_thread":
      return <Mail className="h-4 w-4 text-emerald-500" />;
    default:
      return <FileText className="h-4 w-4 text-muted-foreground" />;
  }
}

function itemBg(type: FolderItem["item_type"]) {
  switch (type) {
    case "conversation":
      return "bg-violet-500/10";
    case "document":
      return "bg-blue-500/10";
    case "email_thread":
      return "bg-emerald-500/10";
    default:
      return "bg-muted";
  }
}

export function FoldersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const selectedFolderId = searchParams.get("id");
  const [createOpen, setCreateOpen] = useState(false);
  const [folderSearch, setFolderSearch] = useState("");
  const [itemSearch, setItemSearch] = useState("");
  const [activeTab, setActiveTab] = useState<ItemTab>("all");
  const [editingName, setEditingName] = useState(false);

  // Fetch all folders
  const { data: folders = [], isLoading: foldersLoading } = useQuery({
    queryKey: ["folders"],
    queryFn: () => foldersApi.list(),
  });

  // Fetch selected folder detail
  const { data: selectedFolder } = useQuery({
    queryKey: ["folder", selectedFolderId],
    queryFn: () => foldersApi.get(selectedFolderId!),
    enabled: !!selectedFolderId,
  });

  // Fetch items of selected folder
  const { data: folderItems = [], isLoading: itemsLoading } = useQuery({
    queryKey: ["folder-items", selectedFolderId, activeTab],
    queryFn: () =>
      foldersApi.listItems(
        selectedFolderId!,
        activeTab === "all" ? undefined : { item_type: activeTab },
      ),
    enabled: !!selectedFolderId,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      toast({ title: "Dossier créé" });
      setCreateOpen(false);
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Impossible de créer le dossier." });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      foldersApi.update(id, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      queryClient.invalidateQueries({ queryKey: ["folder", selectedFolderId] });
      toast({ title: "Dossier mis à jour" });
      setEditingName(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => foldersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      toast({ title: "Dossier supprimé" });
      setSearchParams({}, { replace: true });
    },
  });

  const removeItemMutation = useMutation({
    mutationFn: (itemId: string) =>
      foldersApi.removeItem(selectedFolderId!, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folder-items", selectedFolderId] });
      queryClient.invalidateQueries({ queryKey: ["folder", selectedFolderId] });
    },
  });

  const selectFolder = useCallback(
    (id: string) => {
      setSearchParams({ id }, { replace: true });
      setActiveTab("all");
      setItemSearch("");
      setEditingName(false);
    },
    [setSearchParams],
  );

  const handleOpenItem = useCallback(
    (item: FolderItem) => {
      if (item.item_type === "conversation") {
        navigate(`/app/search?conversation=${item.item_id}`);
      } else if (item.item_type === "document") {
        navigate(`/app/documents/${item.item_id}`);
      } else if (item.item_type === "email_thread") {
        navigate(`/app/email?thread=${item.item_id}`);
      }
    },
    [navigate],
  );

  const filteredFolders = useMemo(() => {
    if (!folderSearch.trim()) return folders;
    const q = folderSearch.toLowerCase();
    return folders.filter((f) => f.name.toLowerCase().includes(q));
  }, [folders, folderSearch]);

  const filteredItems = useMemo(() => {
    if (!itemSearch.trim()) return folderItems;
    const q = itemSearch.toLowerCase();
    return folderItems.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        (item.subtitle && item.subtitle.toLowerCase().includes(q)),
    );
  }, [folderItems, itemSearch]);

  const totalItems = selectedFolder
    ? (selectedFolder.item_counts?.conversation || 0) +
      (selectedFolder.item_counts?.document || 0) +
      (selectedFolder.item_counts?.email_thread || 0)
    : 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header area */}
      <div className="px-6 pt-8 pb-6 md:pt-10 md:pb-6">
        <div className="max-w-4xl mx-auto space-y-5">
          {selectedFolderId && selectedFolder ? (
            <>
              {/* Back + folder header */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSearchParams({}, { replace: true })}
                  className="h-9 w-9 rounded-full flex items-center justify-center bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {selectedFolder.color && (
                    <div
                      className="w-3 h-10 rounded-full shrink-0"
                      style={{ backgroundColor: selectedFolder.color }}
                    />
                  )}
                  {editingName ? (
                    <Input
                      defaultValue={selectedFolder.name}
                      className="h-9 text-lg font-bold max-w-xs"
                      autoFocus
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v && v !== selectedFolder.name) {
                          updateMutation.mutate({ id: selectedFolderId, name: v });
                        } else {
                          setEditingName(false);
                        }
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.currentTarget.blur();
                        if (e.key === "Escape") setEditingName(false);
                      }}
                    />
                  ) : (
                    <h1 className="font-heading text-xl md:text-2xl font-bold text-foreground tracking-tight truncate">
                      {selectedFolder.name}
                    </h1>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() => setEditingName(true)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0 text-destructive"
                    onClick={() => deleteMutation.mutate(selectedFolderId)}
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              <p className="text-sm text-muted-foreground font-body">
                {totalItems} élément{totalItems > 1 ? "s" : ""} dans ce dossier
              </p>
            </>
          ) : (
            <>
              <div className="space-y-1">
                <h1 className="font-heading text-2xl md:text-3xl font-bold text-foreground tracking-tight flex items-center gap-3">
                  <Folder className="h-7 w-7 text-primary" />
                  Dossiers
                </h1>
                <p className="text-sm text-muted-foreground font-body">
                  Organisez vos documents, conversations et emails dans des dossiers.
                </p>
              </div>

              {/* Search + create */}
              <div className="flex items-center gap-3">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    value={folderSearch}
                    onChange={(e) => setFolderSearch(e.target.value)}
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
            </>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 bg-background rounded-t-3xl border-t border-border px-6 py-6 md:py-8 overflow-auto">
        <div className="max-w-4xl mx-auto">
          {!selectedFolderId ? (
            /* ── Folders grid ── */
            foldersLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredFolders.length === 0 ? (
              <div className="text-center py-16 space-y-4">
                <Folder className="h-12 w-12 text-muted-foreground/30 mx-auto" />
                <div>
                  <p className="text-sm text-muted-foreground font-body">
                    {folderSearch ? "Aucun dossier trouvé." : "Aucun dossier pour le moment."}
                  </p>
                  {!folderSearch && (
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
                {filteredFolders.map((folder) => {
                  const count =
                    (folder.item_counts?.conversation || 0) +
                    (folder.item_counts?.document || 0) +
                    (folder.item_counts?.email_thread || 0);
                  return (
                    <button
                      key={folder.id}
                      onClick={() => selectFolder(folder.id)}
                      className="group text-left p-5 rounded-xl border border-border bg-card hover:shadow-lg hover:border-primary/20 transition-all"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-2.5">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center"
                            style={{ backgroundColor: folder.color ? `${folder.color}20` : "var(--muted)" }}
                          >
                            <Folder
                              className="h-5 w-5"
                              style={{ color: folder.color || "var(--muted-foreground)" }}
                            />
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <div className="text-sm font-semibold text-foreground font-body truncate">
                        {folder.name}
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <span className="text-xs text-muted-foreground font-body">
                          {count} élément{count > 1 ? "s" : ""}
                        </span>
                        {folder.item_counts && (
                          <div className="flex items-center gap-2">
                            {(folder.item_counts.document || 0) > 0 && (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                {folder.item_counts.document} doc
                              </Badge>
                            )}
                            {(folder.item_counts.conversation || 0) > 0 && (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                {folder.item_counts.conversation} conv
                              </Badge>
                            )}
                            {(folder.item_counts.email_thread || 0) > 0 && (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                                {folder.item_counts.email_thread} email
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}

                {/* Create new folder card */}
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
            )
          ) : (
            /* ── Folder detail — items list ── */
            <div className="space-y-4">
              {/* Tabs + search */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 bg-muted/50 rounded-lg p-1">
                  {ITEM_TABS.map((tab) => (
                    <button
                      key={tab.value}
                      onClick={() => setActiveTab(tab.value)}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-xs font-medium font-body transition-all whitespace-nowrap",
                        activeTab === tab.value
                          ? "bg-card text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    value={itemSearch}
                    onChange={(e) => setItemSearch(e.target.value)}
                    placeholder="Rechercher..."
                    className="w-full h-8 pl-9 pr-3 text-xs font-body bg-muted/50 border border-border rounded-lg outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 text-foreground placeholder:text-muted-foreground/60 transition-all"
                  />
                </div>
              </div>

              {/* Items */}
              {itemsLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="text-center py-16 text-sm text-muted-foreground font-body">
                  {itemSearch
                    ? "Aucun élément trouvé."
                    : "Ce dossier est vide. Ajoutez des éléments depuis la page d'accueil."}
                </div>
              ) : (
                <div className="space-y-1">
                  {filteredItems.map((item) => (
                    <div
                      key={item.id}
                      className="group flex items-center gap-3 w-full px-3 py-2.5 rounded-lg hover:bg-muted/50 transition-all"
                    >
                      <button
                        onClick={() => handleOpenItem(item)}
                        className="flex items-center gap-3 flex-1 min-w-0 text-left"
                      >
                        <div className={`w-8 h-8 rounded-lg ${itemBg(item.item_type)} flex items-center justify-center shrink-0`}>
                          {itemIcon(item.item_type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-foreground truncate font-body">
                            {item.title}
                          </div>
                          {item.subtitle && (
                            <div className="text-xs text-muted-foreground truncate font-body">
                              {item.subtitle}
                            </div>
                          )}
                        </div>
                        <span className="text-[11px] text-muted-foreground shrink-0 hidden sm:block font-body">
                          {formatRelativeDate(item.date)}
                        </span>
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                      </button>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleOpenItem(item)}
                        >
                          <ExternalLink className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={() => removeItemMutation.mutate(item.id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <FolderCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(name) => createMutation.mutateAsync(name).then(() => undefined)}
        mode="create"
      />
    </div>
  );
}
