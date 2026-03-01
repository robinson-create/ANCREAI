import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  FileText,
  Mail,
  Settings,
  Bot,
  LogOut,
  Calendar,
  Folder,
  Plus,
  Users,
  House,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AnchorLogo } from "@/components/ui/anchor-logo";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { useClerk } from "@clerk/clerk-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { foldersApi } from "@/api/folders";
import { FolderCreateDialog } from "@/components/folders/FolderCreateDialog";
import { useToast } from "@/hooks/use-toast";

const mainNav = [
  { label: "Accueil", icon: House, path: "/app/search" },
  { label: "Emails", icon: Mail, path: "/app/email" },
  { label: "Contacts", icon: Users, path: "/app/contacts" },
  { label: "Documents", icon: FileText, path: "/app/documents" },
  { label: "Calendrier", icon: Calendar, path: "/app/calendar" },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [createOpen, setCreateOpen] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

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

  return (
    <TooltipProvider delayDuration={200}>
      <aside className="flex flex-col h-screen max-h-screen w-16 bg-sidebar text-sidebar-foreground border-r border-sidebar-border shrink-0 overflow-y-auto">
        {/* Logo — clickable, back to home */}
        <Link
          to="/app/search"
          className="flex items-center justify-center h-14 border-b border-sidebar-border hover:bg-sidebar-accent transition-colors"
        >
          <AnchorLogo size="sm" />
        </Link>

        {/* Main nav */}
        <nav className="py-4 px-2 space-y-1 flex flex-col items-center">
          {mainNav.map((item) => {
            const active =
              location.pathname === item.path ||
              (item.path !== "/app" && location.pathname.startsWith(item.path + "/"));
            return (
              <Tooltip key={item.path}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.path}
                    onClick={(e) => {
                      if (active) {
                        e.preventDefault();
                        navigate(item.path, { state: { reset: Date.now() } });
                      }
                    }}
                    className={cn(
                      "flex items-center justify-center h-10 w-10 rounded-md transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>

        {/* Dossiers section */}
        <div className="border-t border-sidebar-border py-3 px-2 flex flex-col items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10"
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Nouveau dossier</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app/folders"
                className={cn(
                  "flex items-center justify-center h-10 w-10 rounded-md transition-colors",
                  location.pathname === "/app/folders"
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <Folder className="h-4 w-4" />
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right">Dossiers</TooltipContent>
          </Tooltip>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Bottom section */}
        <div className="border-t border-sidebar-border p-2 flex flex-col items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app/assistants"
                className={cn(
                  "flex items-center justify-center h-10 w-10 rounded-md transition-colors",
                  (location.pathname === "/app/assistants" || location.pathname.startsWith("/app/assistant"))
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <Bot className="h-4 w-4" />
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right">Assistant</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/app/profile"
                className={cn(
                  "flex items-center justify-center h-10 w-10 rounded-md transition-colors",
                  location.pathname === "/app/profile"
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <Settings className="h-4 w-4" />
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right">Réglages</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={() => signOut({ redirectUrl: "/" })}
                className="flex items-center justify-center h-10 w-10 rounded-md text-sidebar-muted/50 hover:text-destructive hover:bg-sidebar-accent/30 transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Déconnexion</TooltipContent>
          </Tooltip>
        </div>

        <FolderCreateDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          onSubmit={(name) => createMutation.mutateAsync(name).then(() => undefined)}
          mode="create"
        />
      </aside>
    </TooltipProvider>
  );
}
