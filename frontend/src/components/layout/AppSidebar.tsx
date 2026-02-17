import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  FileText,
  Mail,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Bot,
  LogOut,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { AnchorLogo } from "@/components/ui/anchor-logo";
import { useClerk } from "@clerk/clerk-react";

const mainNav = [
  { label: "Recherche", icon: Search, path: "/app/search" },
  { label: "Emails", icon: Mail, path: "/app/email" },
  { label: "Documents", icon: FileText, path: "/app/documents" },
  { label: "Calendrier", icon: Calendar, path: "/app/calendar" },
  { label: "Assistant", icon: Bot, path: "/app/assistants", matchPaths: ["/app/assistant"] },
];

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useClerk();

  return (
    <aside
      className={cn(
        "flex flex-col h-screen max-h-screen bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-all duration-200 shrink-0 overflow-y-auto",
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
      <nav className="py-4 px-3 space-y-1">
        <div className={cn("mb-4", collapsed && "hidden")}>
          <span className="px-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">
            Navigation
          </span>
        </div>
        {mainNav.map((item) => {
          const itemPaths = "matchPaths" in item ? [item.path, ...(item.matchPaths ?? [])] : [item.path];
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

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom section: Facturation + Réglages */}
      <div className="border-t border-sidebar-border p-3 space-y-1">
          <Link
            to="/app/billing"
            className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
          >
            <CreditCard className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Facturation</span>}
          </Link>
          <Link
            to="/app/profile"
            className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Réglages</span>}
          </Link>
          <button
            onClick={() => signOut({ redirectUrl: "/" })}
            className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-destructive transition-colors w-full"
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
    </aside>
  );
}
