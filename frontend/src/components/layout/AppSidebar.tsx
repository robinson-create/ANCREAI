import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Mail,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Bot,
  Loader2,
  LogOut,
  Plus,
  ChevronDown,
  ChevronUp,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AnchorLogo } from "@/components/ui/anchor-logo";
import { useClerk } from "@clerk/clerk-react";
import { assistantsApi } from "@/api/assistants";
import { billingApi } from "@/api/billing";
import { AssistantModal } from "@/components/assistants/assistant-modal";
import type { Assistant } from "@/types";

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

const PLAN_LIMITS = { free: 1, pro: 3 };

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useClerk();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [assistantsExpanded, setAssistantsExpanded] = useState(true);

  // Fetch assistants from API
  const { data: assistants = [], isLoading } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
  });

  const { data: subscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: billingApi.getSubscription,
  });

  const maxAssistants = subscription?.is_pro ? PLAN_LIMITS.pro : PLAN_LIMITS.free;
  const isAtLimit = assistants.length >= maxAssistants;

  return (
    <aside
      className={cn(
        "flex flex-col h-screen bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-all duration-200 shrink-0",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo — clickable, navigates to home */}
      <Link
        to="/app"
        className="flex items-center h-14 px-4 border-b border-sidebar-border group"
      >
        <div className="transition-transform duration-300 group-hover:rotate-[-12deg]">
          <AnchorLogo size="sm" />
        </div>
        {!collapsed && (
          <span className="ml-2.5 text-sm font-semibold text-sidebar-foreground">
            Ancre
          </span>
        )}
      </Link>

      {/* Main nav */}
      <nav className="py-3 px-2 space-y-0.5">
        <div className={cn("mb-3", collapsed && "hidden")}>
          <span className="px-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">
            Navigation
          </span>
        </div>
        {mainNav.map((item) => {
          const active = location.pathname === item.path || (item.path !== "/app" && location.pathname.startsWith(item.path));
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
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
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

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom section: Assistants + Facturation + Réglages */}
      <div className="border-t border-sidebar-border">
        {/* Assistants section — collapsible, between nav and settings */}
        <div className="px-2 pt-2 pb-1">
          {!collapsed ? (
            <>
              {/* Assistants header */}
              <button
                onClick={() => setAssistantsExpanded((v) => !v)}
                className="flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-[11px] font-medium uppercase tracking-wider text-sidebar-muted hover:text-sidebar-accent-foreground transition-colors"
              >
                <Bot className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1 text-left">Assistants</span>
                <span className="text-[10px] font-normal normal-case tracking-normal opacity-70">
                  {assistants.length}/{maxAssistants}
                </span>
                {assistantsExpanded ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </button>

              {/* Assistants list */}
              {assistantsExpanded && (
                <div className="space-y-0.5 mt-1">
                  {isLoading && (
                    <div className="flex justify-center py-3">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-sidebar-muted" />
                    </div>
                  )}

                  {assistants.map((a: Assistant) => {
                    const settings = (a.settings || {}) as Record<string, unknown>;
                    const emoji = (settings.emoji as string) || "";
                    const role = (settings.role as string) || a.model;
                    const assistantPath = `/app/assistant/${a.id}`;

                    return (
                      <Link
                        key={a.id}
                        to={assistantPath}
                        className={cn(
                          "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors w-full text-left group",
                          location.pathname === assistantPath
                            ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                            : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        )}
                      >
                        {emoji ? (
                          <span className="text-sm shrink-0">{emoji}</span>
                        ) : (
                          <Bot className="h-3.5 w-3.5 shrink-0 text-sidebar-muted" />
                        )}
                        <div className="min-w-0 flex-1">
                          <div className="text-[13px] font-medium text-sidebar-accent-foreground truncate">{a.name}</div>
                          <div className="text-[10px] text-sidebar-muted truncate">{role}</div>
                        </div>
                      </Link>
                    );
                  })}

                  {/* Add assistant button */}
                  {!isAtLimit && !isLoading && (
                    <button
                      onClick={() => setIsModalOpen(true)}
                      className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors w-full text-left text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                    >
                      <Plus className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-[13px]">Ajouter</span>
                    </button>
                  )}
                  {isAtLimit && !isLoading && (
                    <Link
                      to="/app/billing"
                      className="flex items-center gap-2.5 px-3 py-1.5 rounded-md text-[11px] transition-colors w-full text-left text-sidebar-muted hover:text-sidebar-accent-foreground"
                    >
                      Limite atteinte · Upgrader
                    </Link>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              {/* Collapsed: show assistant icons */}
              <Link
                to="/app/assistants"
                className="flex items-center justify-center py-2 rounded-md transition-colors w-full text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                title="Assistants"
              >
                <Bot className="h-4 w-4" />
              </Link>
              {assistants.map((a: Assistant) => {
                const settings = (a.settings || {}) as Record<string, unknown>;
                const emoji = (settings.emoji as string) || "";
                const assistantPath = `/app/assistant/${a.id}`;

                return (
                  <Link
                    key={a.id}
                    to={assistantPath}
                    className={cn(
                      "flex items-center justify-center py-1.5 rounded-md transition-colors w-full",
                      location.pathname === assistantPath
                        ? "bg-sidebar-accent"
                        : "text-muted-foreground hover:bg-sidebar-accent"
                    )}
                    title={a.name}
                  >
                    {emoji ? (
                      <span className="text-sm">{emoji}</span>
                    ) : (
                      <Bot className="h-3.5 w-3.5 text-sidebar-muted" />
                    )}
                  </Link>
                );
              })}
            </>
          )}
        </div>

        {/* Facturation + Réglages */}
        <div className="p-2 space-y-0.5 border-t border-sidebar-border/50">
          <Link
            to="/app/billing"
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
          >
            <CreditCard className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Facturation</span>}
          </Link>
          <Link
            to="/app/profile"
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Réglages</span>}
          </Link>
          <button
            onClick={() => signOut({ redirectUrl: "/" })}
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-destructive transition-colors w-full"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Déconnexion</span>}
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
      </div>
      {/* Create assistant modal */}
      <AssistantModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        assistant={null}
      />
    </aside>
  );
}
