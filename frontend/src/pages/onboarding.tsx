import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "@clerk/clerk-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  CreditCard,
  FileText,
  Globe,
  Loader2,
  Mail,
  MessageSquare,
  Plug,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  User,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import {
  integrationsApi,
  type NangoConnection,
} from "@/api/integrations";
import { onboardingApi } from "@/api/onboarding";
import { documentsApi } from "@/api/documents";
import { cn } from "@/lib/utils";

// ── Constants ───────────────────────────────────────────────────────

const TOTAL_STEPS = 7;

const EMAIL_PROVIDERS = [
  { key: "gmail", name: "Gmail", color: "bg-red-500" },
  { key: "outlook", name: "Outlook", color: "bg-blue-600" },
];

const CONNECTOR_PROVIDERS = [
  { key: "google-drive", name: "Google Drive", color: "bg-yellow-600" },
  { key: "notion", name: "Notion", color: "bg-gray-800" },
  { key: "hubspot", name: "HubSpot", color: "bg-orange-500" },
  { key: "pipedrive", name: "Pipedrive", color: "bg-green-600" },
  { key: "slack", name: "Slack", color: "bg-purple-600" },
  { key: "shopify", name: "Shopify", color: "bg-green-500" },
  { key: "stripe", name: "Stripe", color: "bg-purple-500" },
  { key: "salesforce", name: "Salesforce", color: "bg-blue-500" },
];

const ACCEPTED_FILE_TYPES =
  ".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.csv,.md";

// ── Stepper ─────────────────────────────────────────────────────────

const STEP_LABELS = [
  "Profil",
  "Email",
  "Connecteurs",
  "Documents",
  "Memoires",
  "Sites web",
  "Activation",
];

function Stepper({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-1 sm:gap-2 w-full max-w-xl mx-auto">
      {STEP_LABELS.map((label, i) => {
        const step = i + 1;
        const done = step < current;
        const active = step === current;
        return (
          <div key={step} className="flex-1 flex flex-col items-center gap-1">
            <div
              className={cn(
                "w-6 h-6 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-bold transition-colors",
                done
                  ? "bg-primary text-primary-foreground"
                  : active
                    ? "bg-primary text-primary-foreground ring-2 sm:ring-4 ring-primary/20"
                    : "bg-muted text-muted-foreground"
              )}
            >
              {done ? (
                <CheckCircle2 className="h-3 w-3 sm:h-4 sm:w-4" />
              ) : (
                step
              )}
            </div>
            <span
              className={cn(
                "text-[9px] sm:text-[10px] font-medium hidden sm:block",
                active ? "text-foreground" : "text-muted-foreground"
              )}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Provider card (reused for email + connectors) ───────────────────

function ProviderCard({
  provider,
  isConnected,
  isConnecting,
  onConnect,
  onDisconnect,
}: {
  provider: { key: string; name: string; color: string };
  isConnected: boolean;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg border border-border bg-card">
      <div
        className={`w-8 h-8 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center text-white text-[10px] sm:text-xs font-bold shrink-0 ${provider.color}`}
      >
        {provider.name.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs sm:text-sm font-medium text-foreground">
          {provider.name}
        </div>
      </div>
      {isConnected ? (
        <>
          <Badge variant="success" className="gap-1 text-[10px] sm:text-xs">
            <CheckCircle2 className="h-3 w-3" />
            <span className="hidden sm:inline">Connecte</span>
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive h-7 w-7 p-0"
            onClick={onDisconnect}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </>
      ) : (
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={onConnect}
          disabled={isConnecting}
        >
          {isConnecting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">Connecter</span>
        </Button>
      )}
    </div>
  );
}

// ── Uploaded file item ──────────────────────────────────────────────

interface PendingFile {
  file: File;
}

function UploadedFileItem({
  item,
  onRemove,
}: {
  item: PendingFile;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card text-sm">
      <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="flex-1 truncate text-foreground text-xs sm:text-sm">
        {item.file.name}
      </span>
      <span className="text-[10px] text-muted-foreground shrink-0">
        {(item.file.size / 1024).toFixed(0)} Ko
      </span>
      <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
        onClick={onRemove}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useUser();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Wizard state ──
  const [step, setStep] = useState(1);

  // Step 1: Personal info
  const [firstName, setFirstName] = useState(user?.firstName || "");
  const [lastName, setLastName] = useState(user?.lastName || "");
  const [companyName, setCompanyName] = useState("");

  // Step 4: Documents
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);

  // Step 5: Memories
  const [memories, setMemories] = useState("");

  // Step 6: Websites
  const [websiteUrls, setWebsiteUrls] = useState<string[]>([]);
  const [newUrl, setNewUrl] = useState("");

  // ── Drag & drop state ──
  const [isDragOver, setIsDragOver] = useState(false);

  // ── Nango connections ──
  const { data: connections = [], refetch: refetchConnections } = useQuery({
    queryKey: ["nango-connections"],
    queryFn: integrationsApi.listConnections,
  });

  const connectedProviders = new Set(
    connections.map((c: NangoConnection) => c.provider)
  );

  const connectMutation = useMutation({
    mutationFn: async (provider: string) => {
      const resp = await integrationsApi.connect(provider);
      const popup = window.open(
        resp.connect_url,
        "nango-oauth",
        "width=600,height=700"
      );
      return new Promise<void>((resolve) => {
        const interval = setInterval(() => {
          if (!popup || popup.closed) {
            clearInterval(interval);
            resolve();
          }
        }, 500);
      });
    },
    onSuccess: () => {
      refetchConnections();
      toast({ title: "Connecteur ajoute" });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "La connexion a echoue.",
      });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: integrationsApi.deleteConnection,
    onSuccess: () => {
      refetchConnections();
      toast({ title: "Connecteur deconnecte" });
    },
  });

  // ── File handling ──
  const handleFiles = useCallback((files: FileList | File[]) => {
    const newFiles: PendingFile[] = Array.from(files).map((file) => ({
      file,
    }));
    setPendingFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    handleFiles(files);
    e.target.value = "";
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (e.dataTransfer.files?.length) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles]
  );

  const removeFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // ── Onboarding complete mutation ──
  const completeMutation = useMutation({
    mutationFn: async () => {
      // Save personal info to Clerk
      if (user) {
        await user.update({
          unsafeMetadata: {
            ...user.unsafeMetadata,
            firstName,
            lastName,
            companyName,
          },
        });
      }

      // Complete onboarding via API
      const result = await onboardingApi.complete({
        first_name: firstName,
        last_name: lastName,
        company_name: companyName,
        memories,
        website_urls: websiteUrls.filter((u) => u.trim()),
      });

      // Upload documents to the created collection
      if (pendingFiles.length > 0 && result.collection_id) {
        await Promise.allSettled(
          pendingFiles.map((item) =>
            documentsApi.upload(result.collection_id!, item.file)
          )
        );
      }

      return result;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["onboarding-status"] });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        navigate("/app/search");
      }
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de finaliser l'onboarding.",
      });
    },
  });

  // ── Navigation ──
  const canGoNext = () => {
    if (step === 1) return firstName.trim() !== "" && lastName.trim() !== "";
    return true; // Other steps are optional
  };

  const goNext = () => {
    if (step < TOTAL_STEPS) setStep(step + 1);
  };

  const goBack = () => {
    if (step > 1) setStep(step - 1);
  };

  // ── Website management ──
  const addWebsite = () => {
    const url = newUrl.trim();
    if (!url) return;
    try {
      new URL(url.startsWith("http") ? url : `https://${url}`);
    } catch {
      toast({ variant: "destructive", title: "URL invalide" });
      return;
    }
    const finalUrl = url.startsWith("http") ? url : `https://${url}`;
    if (websiteUrls.includes(finalUrl)) {
      toast({ variant: "destructive", title: "URL deja ajoutee" });
      return;
    }
    setWebsiteUrls([...websiteUrls, finalUrl]);
    setNewUrl("");
  };

  const removeWebsite = (url: string) => {
    setWebsiteUrls(websiteUrls.filter((u) => u !== url));
  };

  // ── Render step content ──
  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <User className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Bienvenue sur Ancre
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Commencez par renseigner vos informations. Elles seront
                utilisees pour personnaliser vos emails et documents.
              </p>
            </div>
            <div className="max-w-sm mx-auto space-y-3 sm:space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Prenom *
                </label>
                <Input
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Jean"
                  autoFocus
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Nom *
                </label>
                <Input
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Dupont"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <Building2 className="h-3 w-3" /> Societe
                </label>
                <Input
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Mon Entreprise SAS"
                />
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Mail className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Connectez votre email
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Connectez votre boite mail pour envoyer et recevoir des emails
                depuis Ancre.
              </p>
            </div>
            <div className="max-w-sm mx-auto space-y-2 sm:space-y-3">
              {EMAIL_PROVIDERS.map((provider) => (
                <ProviderCard
                  key={provider.key}
                  provider={provider}
                  isConnected={connectedProviders.has(provider.key)}
                  isConnecting={connectMutation.isPending}
                  onConnect={() => connectMutation.mutate(provider.key)}
                  onDisconnect={() =>
                    disconnectMutation.mutate(provider.key)
                  }
                />
              ))}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Plug className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Connectez vos outils
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Ajoutez des connecteurs pour enrichir votre assistant avec vos
                donnees CRM, documents, messages, etc.
              </p>
            </div>
            <div className="max-w-sm mx-auto space-y-2 sm:space-y-3 max-h-[50vh] overflow-y-auto">
              {CONNECTOR_PROVIDERS.map((provider) => (
                <ProviderCard
                  key={provider.key}
                  provider={provider}
                  isConnected={connectedProviders.has(provider.key)}
                  isConnecting={connectMutation.isPending}
                  onConnect={() => connectMutation.mutate(provider.key)}
                  onDisconnect={() =>
                    disconnectMutation.mutate(provider.key)
                  }
                />
              ))}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <FileText className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Importez vos documents
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Ajoutez vos fichiers pour que votre assistant puisse les
                consulter. PDF, Word, Excel, PowerPoint, TXT, CSV, Markdown.
              </p>
            </div>
            <div className="max-w-md mx-auto space-y-4">
              {/* Drop zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-colors",
                  isDragOver
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50 hover:bg-muted/30"
                )}
              >
                <Upload className="h-8 w-8 sm:h-10 sm:w-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground">
                  Glissez vos fichiers ici
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  ou cliquez pour parcourir
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                multiple
                accept={ACCEPTED_FILE_TYPES}
                onChange={handleFileSelect}
              />

              {/* File list */}
              {pendingFiles.length > 0 && (
                <div className="space-y-2 max-h-[35vh] overflow-y-auto">
                  {pendingFiles.map((item, idx) => (
                    <UploadedFileItem
                      key={`${item.file.name}-${idx}`}
                      item={item}
                      onRemove={() => removeFile(idx)}
                    />
                  ))}
                  <p className="text-xs text-muted-foreground text-center pt-1">
                    {pendingFiles.length} fichier
                    {pendingFiles.length > 1 ? "s" : ""} selectionne
                    {pendingFiles.length > 1 ? "s" : ""}
                  </p>
                </div>
              )}
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <MessageSquare className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Memoires ChatGPT
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Si vous utilisez ChatGPT, collez ici vos memoires
                personnalisees. Elles seront utilisees comme contexte par votre
                assistant Ancre.
              </p>
            </div>
            <div className="max-w-md mx-auto space-y-3">
              <Textarea
                value={memories}
                onChange={(e) => setMemories(e.target.value)}
                placeholder="Collez vos memoires ChatGPT ici (optionnel)..."
                rows={8}
                className="resize-none"
              />
              <p className="text-xs text-muted-foreground">
                Pour exporter vos memoires ChatGPT : Parametres &gt;
                Personnalisation &gt; Memoire &gt; Gerer la memoire &gt; tout
                selectionner et copier.
              </p>
            </div>
          </div>
        );

      case 6:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Globe className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Sites internet
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Ajoutez les sites web que vous consultez regulierement. Leur
                contenu sera indexe dans votre base de connaissances.
              </p>
            </div>
            <div className="max-w-md mx-auto space-y-4">
              <div className="flex gap-2">
                <Input
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="https://example.com"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addWebsite();
                    }
                  }}
                />
                <Button
                  variant="outline"
                  onClick={addWebsite}
                  className="shrink-0 gap-1.5"
                >
                  <Plus className="h-4 w-4" />
                  <span className="hidden sm:inline">Ajouter</span>
                </Button>
              </div>
              {websiteUrls.length > 0 && (
                <div className="space-y-2 max-h-[40vh] overflow-y-auto">
                  {websiteUrls.map((url) => (
                    <div
                      key={url}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card text-sm"
                    >
                      <Globe className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="flex-1 truncate text-foreground text-xs sm:text-sm">
                        {url}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        onClick={() => removeWebsite(url)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );

      case 7:
        return (
          <div className="space-y-4 sm:space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                <Sparkles className="h-6 w-6 sm:h-7 sm:w-7 text-primary" />
              </div>
              <h2 className="text-lg sm:text-xl font-display font-bold text-foreground">
                Tout est pret !
              </h2>
              <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto">
                Voici un recapitulatif de votre configuration. Activez votre
                essai gratuit pour commencer.
              </p>
            </div>

            <div className="max-w-sm mx-auto space-y-3">
              {/* Recap */}
              <div className="rounded-lg border border-border bg-card p-3 sm:p-4 space-y-2.5 sm:space-y-3">
                <div className="flex items-center gap-2 text-sm">
                  <User className="h-4 w-4 text-primary shrink-0" />
                  <span className="font-medium truncate">
                    {firstName} {lastName}
                  </span>
                  {companyName && (
                    <span className="text-muted-foreground truncate">
                      — {companyName}
                    </span>
                  )}
                </div>

                {connectedProviders.size > 0 && (
                  <div className="flex items-start gap-2 text-sm">
                    <Plug className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <span>
                        {connectedProviders.size} connecteur
                        {connectedProviders.size > 1 ? "s" : ""}
                      </span>
                      <div className="flex gap-1 flex-wrap mt-1">
                        {Array.from(connectedProviders).map((p) => (
                          <Badge
                            key={p}
                            variant="secondary"
                            className="text-[10px] sm:text-xs"
                          >
                            {p}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {pendingFiles.length > 0 && (
                  <div className="flex items-center gap-2 text-sm">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <span>
                      {pendingFiles.length} document
                      {pendingFiles.length > 1 ? "s" : ""} a importer
                    </span>
                  </div>
                )}

                {memories && (
                  <div className="flex items-center gap-2 text-sm">
                    <MessageSquare className="h-4 w-4 text-primary shrink-0" />
                    <span>Memoires ChatGPT importees</span>
                  </div>
                )}

                {websiteUrls.length > 0 && (
                  <div className="flex items-center gap-2 text-sm">
                    <Globe className="h-4 w-4 text-primary shrink-0" />
                    <span>
                      {websiteUrls.length} site
                      {websiteUrls.length > 1 ? "s" : ""} a indexer
                    </span>
                  </div>
                )}
              </div>

              {/* Trial info */}
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 sm:p-4 space-y-2 text-center">
                <div className="flex items-center justify-center gap-2">
                  <CreditCard className="h-4 w-4 text-primary" />
                  <span className="text-xs sm:text-sm font-semibold text-foreground">
                    Essai gratuit de 7 jours
                  </span>
                </div>
                <p className="text-[10px] sm:text-xs text-muted-foreground">
                  Votre carte sera debitee de 15&#8364;/mois a la fin de la
                  periode d'essai. Annulable a tout moment.
                </p>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card px-3 sm:px-6 py-3 sm:py-4 shrink-0">
        <div className="max-w-2xl mx-auto">
          <Stepper current={step} />
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto flex items-start sm:items-center justify-center px-3 sm:px-6 py-6 sm:py-8">
        <div className="w-full max-w-2xl">{renderStep()}</div>
      </main>

      {/* Footer navigation */}
      <footer className="border-t border-border bg-card px-3 sm:px-6 py-3 sm:py-4 shrink-0">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-2">
          <div>
            {step > 1 && (
              <Button
                variant="ghost"
                onClick={goBack}
                className="gap-1.5 text-xs sm:text-sm"
              >
                <ArrowLeft className="h-4 w-4" />
                <span className="hidden sm:inline">Retour</span>
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Skip button for optional steps (2-6) */}
            {step >= 2 && step <= 6 && (
              <Button
                variant="ghost"
                onClick={goNext}
                className="text-xs sm:text-sm"
              >
                Passer
              </Button>
            )}

            {step < TOTAL_STEPS ? (
              <Button
                variant="premium"
                onClick={goNext}
                disabled={!canGoNext()}
                className="gap-1.5 text-xs sm:text-sm"
              >
                Continuer
                <ArrowRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                variant="premium"
                onClick={() => completeMutation.mutate()}
                disabled={completeMutation.isPending}
                className="gap-1.5 text-xs sm:text-sm"
              >
                {completeMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CreditCard className="h-4 w-4" />
                )}
                <span className="hidden sm:inline">
                  Demarrer mon essai gratuit
                </span>
                <span className="sm:hidden">Demarrer l'essai</span>
              </Button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
