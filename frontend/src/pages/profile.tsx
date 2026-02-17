import { useState, useEffect, useRef, useCallback } from "react";
import { useUser, useClerk } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  User,
  Settings,
  AlertTriangle,
  ExternalLink,
  Plug,
  Mail,
  Save,
  Loader2,
  CheckCircle2,
  Plus,
  X,
  Building2,
  Briefcase,
  PenLine,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import {
  integrationsApi,
  type NangoConnection,
} from "@/api/integrations";
import { settingsApi } from "@/api/settings";

// ── Known providers ──
const KNOWN_PROVIDERS = [
  { key: "google-drive", name: "Google Drive", color: "bg-yellow-600" },
  { key: "notion", name: "Notion", color: "bg-gray-800" },
  { key: "salesforce", name: "Salesforce", color: "bg-blue-500" },
  { key: "hubspot", name: "HubSpot", color: "bg-orange-500" },
  { key: "pipedrive", name: "Pipedrive", color: "bg-green-600" },
  { key: "slack", name: "Slack", color: "bg-purple-600" },
  { key: "shopify", name: "Shopify", color: "bg-green-500" },
  { key: "stripe", name: "Stripe", color: "bg-purple-500" },
];

const EMAIL_PROVIDERS = [
  { key: "gmail", name: "Gmail", color: "bg-red-500" },
  { key: "outlook", name: "Outlook", color: "bg-blue-600" },
];

export function ProfilePage() {
  const { user } = useUser();
  const { openUserProfile } = useClerk();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // ── Personal info from Clerk unsafeMetadata ──
  const meta = (user?.unsafeMetadata || {}) as Record<string, string>;
  const [firstName, setFirstName] = useState(meta.firstName || "");
  const [lastName, setLastName] = useState(meta.lastName || "");
  const [companyName, setCompanyName] = useState(meta.companyName || "");
  const [jobTitle, setJobTitle] = useState(meta.jobTitle || "");
  const [infoDirty, setInfoDirty] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);

  // Sync from Clerk when user loads
  useEffect(() => {
    if (user) {
      const m = (user.unsafeMetadata || {}) as Record<string, string>;
      setFirstName(m.firstName || user.firstName || "");
      setLastName(m.lastName || user.lastName || "");
      setCompanyName(m.companyName || "");
      setJobTitle(m.jobTitle || "");
      setInfoDirty(false);
    }
  }, [user]);

  // ── Signature mail (paramètres tenant) ──
  const signatureRef = useRef<HTMLDivElement>(null);
  const [signatureDirty, setSignatureDirty] = useState(false);
  const { data: settingsData } = useQuery({
    queryKey: ["tenant-settings"],
    queryFn: settingsApi.get,
  });
  const updateSettingsMutation = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant-settings"] });
      setSignatureDirty(false);
      toast({ title: "Signature mail sauvegardée" });
    },
    onError: () => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de sauvegarder la signature.",
      });
    },
  });
  useEffect(() => {
    if (signatureRef.current && settingsData?.mail_signature !== undefined && !signatureDirty) {
      signatureRef.current.innerHTML = settingsData.mail_signature;
    }
  }, [settingsData?.mail_signature]);
  const saveSignature = useCallback(() => {
    const html = signatureRef.current?.innerHTML ?? "";
    updateSettingsMutation.mutate({ mail_signature: html });
  }, [updateSettingsMutation]);

  const savePersonalInfo = async () => {
    if (!user) return;
    setSavingInfo(true);
    try {
      await user.update({
        unsafeMetadata: {
          ...user.unsafeMetadata,
          firstName,
          lastName,
          companyName,
          jobTitle,
        },
      });
      setInfoDirty(false);
      toast({ title: "Informations sauvegardées" });
    } catch {
      toast({ variant: "destructive", title: "Erreur", description: "Impossible de sauvegarder." });
    } finally {
      setSavingInfo(false);
    }
  };

  // ── Nango connections ──
  const { data: connections = [] } = useQuery({
    queryKey: ["nango-connections"],
    queryFn: integrationsApi.listConnections,
  });

  const connectedProviders = new Set(
    connections.map((c: NangoConnection) => c.provider)
  );

  const connectMutation = useMutation({
    mutationFn: async (provider: string) => {
      const resp = await integrationsApi.connect(provider);
      const popup = window.open(resp.connect_url, "nango-oauth", "width=600,height=700");
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
      queryClient.invalidateQueries({ queryKey: ["nango-connections"] });
      toast({ title: "Connecteur ajouté" });
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "La connexion a échoué." });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: integrationsApi.deleteConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["nango-connections"] });
      toast({ title: "Connecteur déconnecté" });
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Impossible de déconnecter." });
    },
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 sm:gap-3 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0 flex-wrap">
        <Settings className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
        <h1 className="font-display font-semibold text-foreground text-sm sm:text-base">
          Réglages
        </h1>
      </div>

      <div className="flex-1 overflow-auto bg-surface p-3 sm:p-5">
        <div className="max-w-2xl mx-auto space-y-6 sm:space-y-8">
          {/* ── Informations personnelles ── */}
          <section className="bg-card border border-border rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <User className="h-4 w-4 text-primary" />
              <h3 className="font-display font-semibold text-foreground text-sm">
                Informations personnelles
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-4">
              <p className="text-xs text-muted-foreground">
                Ces informations sont utilisées pour personnaliser vos emails et documents.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Prénom</label>
                  <Input
                    value={firstName}
                    onChange={(e) => { setFirstName(e.target.value); setInfoDirty(true); }}
                    placeholder="Jean"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Nom</label>
                  <Input
                    value={lastName}
                    onChange={(e) => { setLastName(e.target.value); setInfoDirty(true); }}
                    placeholder="Dupont"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                    <Building2 className="h-3 w-3" /> Société
                  </label>
                  <Input
                    value={companyName}
                    onChange={(e) => { setCompanyName(e.target.value); setInfoDirty(true); }}
                    placeholder="Mon Entreprise SAS"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                    <Briefcase className="h-3 w-3" /> Poste
                  </label>
                  <Input
                    value={jobTitle}
                    onChange={(e) => { setJobTitle(e.target.value); setInfoDirty(true); }}
                    placeholder="Directeur commercial"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <span className="text-xs text-muted-foreground flex-1">
                  Email : {user?.primaryEmailAddress?.emailAddress}
                </span>
                <Button
                  variant="premium"
                  size="sm"
                  className="gap-1.5"
                  onClick={savePersonalInfo}
                  disabled={!infoDirty || savingInfo}
                >
                  {savingInfo ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  Sauvegarder
                </Button>
              </div>
            </div>
          </section>

          {/* ── Connexion email ── */}
          <section className="bg-card border border-border rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <Mail className="h-4 w-4 text-primary" />
              <h3 className="font-display font-semibold text-foreground text-sm">
                Connexion email
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-3">
              <p className="text-xs text-muted-foreground">
                Connectez votre boîte mail pour envoyer et recevoir des emails depuis Ancre.
              </p>
              {EMAIL_PROVIDERS.map((provider) => {
                const isConnected = connectedProviders.has(provider.key);
                return (
                  <div
                    key={provider.key}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-border"
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0 ${provider.color}`}
                    >
                      {provider.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground">{provider.name}</div>
                    </div>
                    {isConnected ? (
                      <>
                        <Badge variant="success" className="gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          Connecté
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => disconnectMutation.mutate(provider.key)}
                          disabled={disconnectMutation.isPending}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => connectMutation.mutate(provider.key)}
                        disabled={connectMutation.isPending}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Connecter
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* ── Signature mail ── */}
          <section className="bg-card border border-border rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <PenLine className="h-4 w-4 text-primary" />
              <h3 className="font-display font-semibold text-foreground text-sm">
                Signature mail
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-3">
              <p className="text-xs text-muted-foreground">
                Collez votre signature ici (texte, images, liens). Elle sera ajoutée automatiquement à la fin de chaque email. L&apos;IA ne rédige pas la signature.
              </p>
              <div
                ref={signatureRef}
                contentEditable
                onInput={() => setSignatureDirty(true)}
                className="min-h-[100px] px-3 py-2.5 rounded-lg border border-border bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                data-placeholder="Collez votre signature (Ctrl+V)..."
                suppressContentEditableWarning
              />
              <style>{`
                [data-placeholder]:empty:before {
                  content: attr(data-placeholder);
                  color: var(--muted-foreground);
                }
              `}</style>
              <div className="flex justify-end">
                <Button
                  variant="premium"
                  size="sm"
                  className="gap-1.5"
                  onClick={saveSignature}
                  disabled={!signatureDirty || updateSettingsMutation.isPending}
                >
                  {updateSettingsMutation.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  Sauvegarder
                </Button>
              </div>
            </div>
          </section>

          {/* ── Connecteurs ── */}
          <section className="bg-card border border-border rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <Plug className="h-4 w-4 text-primary" />
              <h3 className="font-display font-semibold text-foreground text-sm">
                Connecteurs
              </h3>
              {connectedProviders.size > 0 && (
                <Badge variant="success" className="ml-auto gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  {connectedProviders.size} actif{connectedProviders.size > 1 ? "s" : ""}
                </Badge>
              )}
            </div>
            <div className="p-4 sm:p-5 space-y-3">
              <p className="text-xs text-muted-foreground">
                Les connecteurs sont disponibles pour tous vos assistants et la recherche.
              </p>
              {KNOWN_PROVIDERS.map((provider) => {
                const isConnected = connectedProviders.has(provider.key);
                return (
                  <div
                    key={provider.key}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-border"
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0 ${provider.color}`}
                    >
                      {provider.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-foreground">{provider.name}</div>
                    </div>
                    {isConnected ? (
                      <>
                        <Badge variant="success" className="gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          Connecté
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => disconnectMutation.mutate(provider.key)}
                          disabled={disconnectMutation.isPending}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => connectMutation.mutate(provider.key)}
                        disabled={connectMutation.isPending}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Connecter
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* ── Compte & Sécurité ── */}
          <section className="bg-card border border-border rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <Settings className="h-4 w-4 text-primary" />
              <h3 className="font-display font-semibold text-foreground text-sm">
                Compte & Sécurité
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Mot de passe et sécurité</p>
                  <p className="text-xs text-muted-foreground">
                    Modifiez votre mot de passe, activez la 2FA
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => openUserProfile()}>
                  <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                  Gérer
                </Button>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Méthodes de connexion</p>
                  <p className="text-xs text-muted-foreground">
                    Email, Google, et autres providers
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => openUserProfile()}>
                  <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                  Gérer
                </Button>
              </div>
            </div>
          </section>

          {/* ── Zone de danger ── */}
          <section className="bg-card border border-destructive/30 rounded-lg shadow-soft overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-destructive/20">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              <h3 className="font-display font-semibold text-destructive text-sm">
                Zone de danger
              </h3>
            </div>
            <div className="p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Supprimer mon compte</p>
                  <p className="text-xs text-muted-foreground">
                    Cette action est irréversible. Toutes vos données seront supprimées.
                  </p>
                </div>
                <Button variant="destructive" size="sm" disabled>
                  Supprimer
                </Button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
