import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  Mail,
  Settings,
  CreditCard,
  Search,
} from "lucide-react";

const pages = [
  { label: "Accueil", path: "/app", icon: LayoutDashboard },
  { label: "Documents", path: "/app/documents", icon: FileText },
  { label: "Emails", path: "/app/email", icon: Mail },
  { label: "Recherche", path: "/app/search", icon: Search },
  { label: "Facturation", path: "/app/billing", icon: CreditCard },
  { label: "Réglages", path: "/app/profile", icon: Settings },
];

interface CommandBarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandBar({ open, onOpenChange }: CommandBarProps) {
  const navigate = useNavigate();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50" onClick={() => onOpenChange(false)}>
      <div
        className="fixed left-1/2 top-1/4 z-50 w-full max-w-lg -translate-x-1/2 rounded-lg border bg-popover p-0 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
          <input
            className="flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
            placeholder="Rechercher une page ou action..."
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Escape") onOpenChange(false);
            }}
          />
        </div>
        <div className="max-h-[300px] overflow-y-auto p-1">
          <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Navigation</div>
          {pages.map((page) => (
            <button
              key={page.path}
              className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm hover:bg-accent"
              onClick={() => {
                navigate(page.path);
                onOpenChange(false);
              }}
            >
              <page.icon className="h-4 w-4 text-muted-foreground" />
              {page.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
