import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  FileText,
  Mail,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  Bot,
  LogOut,
  Calendar,
  Folder,
  Plus,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AnchorLogo } from "@/components/ui/anchor-logo";
import { useClerk } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { foldersApi } from "@/api/folders";
import { FolderCreateDialog } from "@/components/folders/FolderCreateDialog";
import { useToast } from "@/hooks/use-toast";

const mainNav = [
  { label: "Recherche", icon: Search, path: "/app/search" },
  { label: "Emails", icon: Mail, path: "/app/email" },
  { label: "Documents", icon: FileText, path: "/app/documents" },
  { label: "Calendrier", icon: Calendar, path: "/app/calendar" },
];

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const FOLDERS_VISIBLE = 5;

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [foldersExpanded, setFoldersExpanded] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: folders = [] } = useQuery({
    queryKey: ["folders"],
    queryFn: () => foldersApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
      toast({ title: "Dossier créé" });
      setCreateOpen(false);
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer le dossier.",
      });
    },
  });

  const displayedFolders = foldersExpanded ? folders : folders.slice(0, FOLDERS_VISIBLE);
  const hasMoreFolders = folders.length > FOLDERS_VISIBLE;

  return (
    <aside
      className={cn(
        "flex flex-col h-screen max-h-screen bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-all duration-200 shrink-0 overflow-y-auto",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo — non cliquable */}
      <div className="flex items-center h-14 px-4 border-b border-sidebar-border">
        <AnchorLogo size="sm" />
        {!collapsed && (
          <span className="ml-2.5 text-sm font-semibold text-sidebar-foreground">
            Ancre
          </span>
        )}
      </div>

      {/* Main nav */}
      <nav className="py-4 px-3 space-y-1">
        <div className={cn("mb-4", collapsed && "hidden")}>
          <span className="px-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">
            Navigation
          </span>
        </div>
        {mainNav.map((item) => {
          const itemPaths: string[] = [item.path];
          const active = itemPaths.some(
            (p) => location.pathname === p || (p !== "/app" && location.pathname.startsWith(p + "/"))
          );
          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={(e) => {
                if (active) {
                  e.preventDefault();
                  navigate(item.path, { state: { reset: Date.now() } });
                }
              }}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Dossiers section */}
      <div className="border-t border-sidebar-border py-3 px-3">
        <div className={cn("flex items-center gap-2 mb-2", collapsed && "justify-center")}>
          {!collapsed && (
            <span className="px-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted flex-1">
              Dossiers
            </span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className={cn("h-7 w-7 shrink-0", collapsed && "mx-auto")}
            onClick={() => setCreateOpen(true)}
            title="Nouveau dossier"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        {collapsed ? (
          <Link
            to="/app/search"
            className="flex justify-center py-2 rounded-md text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
            title="Dossiers"
          >
            <Folder className="h-4 w-4" />
          </Link>
        ) : (
          <div className="space-y-0.5">
            {displayedFolders.map((f) => {
              const isActive =
                location.pathname === "/app/search" &&
                new URLSearchParams(location.search || "").get("folder") === f.id;
              return (
                <Link
                  key={f.id}
                  to={`/app/search?folder=${f.id}`}
                  className={cn(
                    "flex items-center gap-2 px-2 py-2 rounded-md text-sm transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                      : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                  )}
                >
                  <span
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: f.color || "var(--muted)" }}
                  />
                  <span className="truncate flex-1">{f.name}</span>
                </Link>
              );
            })}
            {hasMoreFolders && (
              <button
                onClick={() => setFoldersExpanded((v) => !v)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground w-full"
              >
                {foldersExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3" />
                    Voir moins
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" />
                    Voir plus ({folders.length - FOLDERS_VISIBLE})
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom section: Assistant, Réglages, Connecteurs (subtle), Déconnexion */}
      <div className="border-t border-sidebar-border p-3 space-y-1">
          <Link
            to="/app/assistants"
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors",
              (location.pathname === "/app/assistants" || location.pathname.startsWith("/app/assistant"))
                ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            )}
          >
            <Bot className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Assistant</span>}
          </Link>
          <Link
            to="/app/profile"
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors",
              location.pathname === "/app/profile"
                ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            )}
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Réglages</span>}
          </Link>
          <button
            onClick={() => signOut({ redirectUrl: "/" })}
            className="flex items-center justify-center px-2 py-1.5 rounded-md text-sidebar-muted/50 hover:text-destructive hover:bg-sidebar-accent/30 transition-colors w-full"
            title="Déconnexion"
          >
            <LogOut className="h-3.5 w-3.5 shrink-0" />
          </button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="w-full flex justify-center text-sidebar-muted hover:text-sidebar-accent-foreground hover:bg-sidebar-accent/50"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
      </div>

      <FolderCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(name) => createMutation.mutateAsync(name).then(() => undefined)}
        mode="create"
      />
    </aside>
  );
}
