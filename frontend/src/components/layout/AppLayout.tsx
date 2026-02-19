import { useState, useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AppSidebar } from "./AppSidebar";
import { useSearchView } from "@/contexts/search-view-context";
import { CommandBar } from "@/components/CommandBar";
import { CreateModal } from "@/components/CreateModal";
import { Plus, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import merFond from "@/assets/mer-fond.png";

export function NewAppLayout() {
  const isMobile = useIsMobile();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const location = useLocation();

  const hideHeader = location.pathname === "/app" || location.pathname === "/app/documents" || location.pathname.startsWith("/app/documents/") || location.pathname === "/app/workspace" || location.pathname === "/app/email" || location.pathname === "/app/search" || location.pathname === "/app/profile" || location.pathname === "/app/billing" || location.pathname.startsWith("/app/assistant");

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const isDashboard = location.pathname === "/app";
  const searchViewCtx = useSearchView();
  const isSearchHome =
    location.pathname === "/app/search" && (searchViewCtx?.isSearchHome ?? true);

  return (
    <div className={`flex h-screen w-full overflow-hidden ${isDashboard ? "" : "bg-background"}`}>
      <div className="relative z-10 flex flex-1 min-w-0 overflow-hidden">
        {isMobile && mobileSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-40 animate-fade-in"
            onClick={() => setMobileSidebarOpen(false)}
          />
        )}

        {isMobile ? (
          <div
            className={`fixed inset-y-0 left-0 z-50 transition-transform duration-200 ${
              mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            <AppSidebar collapsed={false} onToggle={() => setMobileSidebarOpen(false)} />
          </div>
        ) : (
          <AppSidebar
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed((v) => !v)}
          />
        )}

        <div className="relative flex-1 flex flex-col min-w-0 overflow-hidden">
          {(isDashboard || isSearchHome) && (
            <div
              className="absolute inset-0 z-0 pointer-events-none bg-white"
              aria-hidden
            >
              <div
                className="absolute inset-0 bg-cover bg-top bg-no-repeat dashboard-wallpaper"
                style={{ backgroundImage: `url(${merFond})` }}
              />
            </div>
          )}
          {isMobile && (
            <header className="relative z-10 flex items-center h-12 px-3 border-b border-border bg-surface-elevated shrink-0 gap-2">
            <Button variant="ghost" size="icon" onClick={() => setMobileSidebarOpen(true)} className="shrink-0">
              <Menu className="h-5 w-5" />
            </Button>
            <span className="font-display font-bold text-foreground text-sm">Ancre</span>
            {!hideHeader && (
              <Button
                variant="premium"
                size="sm"
                onClick={() => setCreateOpen(true)}
                className="gap-1.5 ml-auto"
              >
                <Plus className="h-4 w-4" />
                Créer
              </Button>
            )}
            </header>
          )}

          {!isMobile && !hideHeader && (
          <header className="relative z-10 flex items-center justify-between h-14 px-6 border-b border-border bg-surface-elevated shrink-0">
            <div />
            <Button
              variant="premium"
              size="sm"
              onClick={() => setCreateOpen(true)}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              Créer
            </Button>
            </header>
          )}
          <main className="relative z-10 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
      <CommandBar open={commandOpen} onOpenChange={setCommandOpen} />
      <CreateModal open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
