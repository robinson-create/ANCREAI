import { useNavigate } from "react-router-dom";
import { FileText, Mail, Search } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const createActions = [
  {
    label: "Rédiger un document",
    description: "Contrat, devis, NDA, compte-rendu",
    icon: FileText,
    path: "/app/documents",
  },
  {
    label: "Composer un email",
    description: "Avec ton, contexte et sources",
    icon: Mail,
    path: "/app/email",
  },
  {
    label: "Rechercher une info",
    description: "Interroger vos documents",
    icon: Search,
    path: "/app/search",
  },
];

interface CreateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateModal({ open, onOpenChange }: CreateModalProps) {
  const navigate = useNavigate();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Créer</DialogTitle>
        </DialogHeader>
        <div className="grid gap-2 py-2">
          {createActions.map((action) => (
            <button
              key={action.label}
              className="flex items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-accent transition-colors"
              onClick={() => {
                navigate(action.path);
                onOpenChange(false);
              }}
            >
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-accent shrink-0">
                <action.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="text-sm font-medium text-foreground">{action.label}</div>
                <div className="text-xs text-muted-foreground">{action.description}</div>
              </div>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
