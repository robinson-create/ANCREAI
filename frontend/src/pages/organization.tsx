import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Building2,
  Users,
  Plug,
  Loader2,
  Plus,
  ShieldCheck,
  UserMinus,
  Crown,
  Mail,
  BarChart3,
  CreditCard,
  Zap,
  Check,
  ExternalLink,
  FileText,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import { useToast } from "@/hooks/use-toast"
import { organizationApi } from "@/api/organization"
import { billingApi, type Plan } from "@/api/billing"
import {
  integrationsApi,
  type NangoConnection,
} from "@/api/integrations"
import type { OrgMember } from "@/types"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

// ── Organization Page ──
export function OrganizationPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // ── Data ──
  const { data: tenant, isLoading: loadingTenant } = useQuery({
    queryKey: ["tenant"],
    queryFn: organizationApi.getTenant,
  })

  const { data: stats } = useQuery({
    queryKey: ["tenant-stats"],
    queryFn: organizationApi.getStats,
  })

  const { data: members = [], isLoading: loadingMembers } = useQuery({
    queryKey: ["members"],
    queryFn: organizationApi.listMembers,
  })

  const { data: connections = [] } = useQuery({
    queryKey: ["nango-connections"],
    queryFn: integrationsApi.listConnections,
  })

  // ── Billing ──
  const { data: subscription, isLoading: loadingSubscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: billingApi.getSubscription,
  })

  const { data: usage, isLoading: loadingUsage } = useQuery({
    queryKey: ["billing-usage"],
    queryFn: billingApi.getUsage,
  })

  const { data: plans } = useQuery({
    queryKey: ["plans"],
    queryFn: billingApi.getPlans,
  })

  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false)
  const [isPortalLoading, setIsPortalLoading] = useState(false)

  const handleUpgrade = async () => {
    setIsCheckoutLoading(true)
    try {
      const url = await billingApi.createCheckout(
        `${window.location.origin}/app/organization?success=true`,
        `${window.location.origin}/app/organization?canceled=true`
      )
      window.location.href = url
    } catch {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible de créer la session de paiement.",
      })
      setIsCheckoutLoading(false)
    }
  }

  const handleManageSubscription = async () => {
    setIsPortalLoading(true)
    try {
      const url = await billingApi.createPortal(
        `${window.location.origin}/app/organization`
      )
      window.location.href = url
    } catch {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: "Impossible d'accéder au portail client.",
      })
      setIsPortalLoading(false)
    }
  }

  const currentPlan = plans?.find((p) => p.id === subscription?.plan)

  // ── Tenant name ──
  const [orgName, setOrgName] = useState("")
  const [nameDirty, setNameDirty] = useState(false)

  // Initialize name when tenant loads
  if (tenant && !nameDirty && orgName !== tenant.name) {
    setOrgName(tenant.name)
  }

  const updateNameMutation = useMutation({
    mutationFn: (name: string) => organizationApi.updateTenant({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant"] })
      setNameDirty(false)
      toast({ title: "Nom de l'organisation mis à jour" })
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Impossible de mettre à jour." })
    },
  })

  // ── Feature toggles ──
  const toggleFeatureMutation = useMutation({
    mutationFn: ({ feature, enabled }: { feature: string; enabled: boolean }) =>
      organizationApi.updateTenant({
        settings: { features: { [feature]: enabled } },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant"] })
      queryClient.invalidateQueries({ queryKey: ["tenant-stats"] })
      toast({ title: "Configuration mise à jour" })
    },
  })

  // ── Invite member ──
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState("")

  const inviteMutation = useMutation({
    mutationFn: (email: string) => organizationApi.inviteMember(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members"] })
      queryClient.invalidateQueries({ queryKey: ["tenant-stats"] })
      setInviteOpen(false)
      setInviteEmail("")
      toast({ title: "Invitation envoyée" })
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        variant: "destructive",
        title: "Erreur",
        description: detail || "Impossible d'inviter ce membre.",
      })
    },
  })

  // ── Update member role ──
  const updateRoleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      organizationApi.updateMember(memberId, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members"] })
      toast({ title: "Rôle mis à jour" })
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({ variant: "destructive", title: "Erreur", description: detail || "Impossible de modifier le rôle." })
    },
  })

  // ── Remove member ──
  const [removingMember, setRemovingMember] = useState<OrgMember | null>(null)

  const removeMutation = useMutation({
    mutationFn: (memberId: string) => organizationApi.removeMember(memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members"] })
      queryClient.invalidateQueries({ queryKey: ["tenant-stats"] })
      setRemovingMember(null)
      toast({ title: "Membre retiré" })
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({ variant: "destructive", title: "Erreur", description: detail || "Impossible de retirer ce membre." })
    },
  })

  if (loadingTenant) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 h-auto min-h-[3.5rem] px-3 sm:px-5 py-2 border-b border-border bg-surface-elevated shrink-0">
        <Building2 className="h-4 w-4 text-primary shrink-0 hidden sm:block" />
        <h1 className="font-heading font-bold text-foreground text-lg sm:text-xl">
          Entreprise
        </h1>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-background p-3 sm:p-5">
        <div className="max-w-2xl mx-auto space-y-6 sm:space-y-8">

          {/* ── Stats overview ── */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Membres" value={stats.members_count} icon={Users} />
              <StatCard label="Assistants" value={`${stats.assistants_count}/${stats.max_assistants}`} icon={ShieldCheck} />
              <StatCard label="Documents" value={stats.documents_count} icon={BarChart3} />
              <StatCard
                label="Plan"
                value={stats.is_pro ? "Pro" : "Free"}
                icon={Crown}
                highlight={stats.is_pro}
              />
            </div>
          )}

          {/* ── Informations de l'organisation ── */}
          <section className="bg-card border border-border rounded-xl shadow-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <Building2 className="h-4 w-4 text-primary" />
              <h3 className="font-heading font-semibold text-foreground text-base">
                Informations
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Nom de l'organisation</label>
                <div className="flex gap-2">
                  <Input
                    value={orgName}
                    onChange={(e) => {
                      setOrgName(e.target.value)
                      setNameDirty(true)
                    }}
                    placeholder="Nom de l'entreprise"
                  />
                  <Button
                    size="sm"
                    disabled={!nameDirty || updateNameMutation.isPending}
                    onClick={() => updateNameMutation.mutate(orgName.trim())}
                  >
                    {updateNameMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Sauvegarder"
                    )}
                  </Button>
                </div>
              </div>

              {/* Feature toggles */}
              {tenant?.is_pro && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Fonctionnalités</label>
                    <div className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-sm font-medium">Dossiers personnels</p>
                        <p className="text-xs text-muted-foreground">
                          Permet aux membres de créer des espaces de travail privés
                        </p>
                      </div>
                      <Button
                        variant={tenant.features?.dossiers ? "default" : "outline"}
                        size="sm"
                        onClick={() =>
                          toggleFeatureMutation.mutate({
                            feature: "dossiers",
                            enabled: !tenant.features?.dossiers,
                          })
                        }
                        disabled={toggleFeatureMutation.isPending}
                      >
                        {tenant.features?.dossiers ? "Activé" : "Désactivé"}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </section>

          {/* ── Collaborateurs ── */}
          <section className="bg-card border border-border rounded-xl shadow-lg overflow-hidden">
            <div className="flex items-center justify-between px-4 sm:px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                <h3 className="font-heading font-semibold text-foreground text-base">
                  Collaborateurs
                </h3>
                {stats && (
                  <Badge variant="secondary" className="text-xs">
                    {stats.active_members_count}/{stats.max_seats} sièges
                  </Badge>
                )}
              </div>
              <Button size="sm" className="gap-1.5" onClick={() => setInviteOpen(true)}>
                <Plus className="h-3.5 w-3.5" />
                Inviter
              </Button>
            </div>

            <div className="divide-y divide-border">
              {loadingMembers ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : members.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  Aucun membre
                </div>
              ) : (
                members.map((member) => (
                  <MemberRow
                    key={member.id}
                    member={member}
                    onRoleChange={(role) =>
                      updateRoleMutation.mutate({ memberId: member.id, role })
                    }
                    onRemove={() => setRemovingMember(member)}
                    isUpdating={updateRoleMutation.isPending}
                  />
                ))
              )}
            </div>
          </section>

          {/* ── Connecteurs ── */}
          <section className="bg-card border border-border rounded-xl shadow-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <Plug className="h-4 w-4 text-primary" />
              <h3 className="font-heading font-semibold text-foreground text-base">
                Connecteurs
              </h3>
            </div>
            <div className="p-4 sm:p-5">
              {connections.length > 0 ? (
                <div className="space-y-2">
                  {connections.map((conn: NangoConnection) => (
                    <div
                      key={conn.id}
                      className="flex items-center justify-between py-2 px-3 rounded-lg border border-border"
                    >
                      <div className="flex items-center gap-2">
                        <Plug className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium capitalize">
                          {conn.provider?.replace(/-/g, " ") || "Connecteur"}
                        </span>
                      </div>
                      <Badge
                        variant={conn.status === "connected" ? "success" : "secondary"}
                        className="text-xs"
                      >
                        {conn.status === "connected" ? "Connecté" : conn.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 rounded-lg border border-dashed border-border">
                  <Plug className="h-8 w-8 mx-auto mb-2 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground">
                    Aucun connecteur configuré.
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Configurez vos connecteurs dans les réglages.
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* ── Facturation ── */}
          <section className="bg-card border border-border rounded-xl shadow-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 sm:px-5 py-4 border-b border-border">
              <CreditCard className="h-4 w-4 text-primary" />
              <h3 className="font-heading font-semibold text-foreground text-base">
                Facturation
              </h3>
            </div>
            <div className="p-4 sm:p-5 space-y-5">
              {/* Current plan */}
              {loadingSubscription ? (
                <div className="h-12 bg-muted animate-pulse rounded" />
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-lg font-bold">
                      {currentPlan?.name || "Free"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {currentPlan?.price === 0
                        ? "Gratuit"
                        : `${currentPlan?.price}€/mois`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {subscription?.is_pro ? (
                      <>
                        <Badge variant="default">Actif</Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleManageSubscription}
                          disabled={isPortalLoading}
                        >
                          {isPortalLoading ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <ExternalLink className="mr-2 h-4 w-4" />
                          )}
                          Gérer
                        </Button>
                      </>
                    ) : (
                      <Button size="sm" onClick={handleUpgrade} disabled={isCheckoutLoading}>
                        {isCheckoutLoading && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Passer en Pro
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {subscription?.cancel_at_period_end && (
                <p className="text-sm text-destructive">
                  Votre abonnement sera annulé à la fin de la période en cours.
                </p>
              )}

              <Separator />

              {/* Usage */}
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 mb-3">
                  <Zap className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Utilisation</span>
                </div>
                {loadingUsage ? (
                  <div className="h-8 bg-muted animate-pulse rounded" />
                ) : usage ? (
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-sm">
                        <span>Requêtes chat / jour</span>
                        <span className="text-muted-foreground">
                          {usage.daily_chat_requests}
                          {usage.daily_chat_limit !== null && ` / ${usage.daily_chat_limit}`}
                          {usage.is_pro && " (illimité)"}
                        </span>
                      </div>
                      {usage.daily_chat_limit !== null && (
                        <Progress
                          value={(usage.daily_chat_requests / usage.daily_chat_limit) * 100}
                        />
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-sm">
                        <span>Fichiers</span>
                        <span className="text-muted-foreground">
                          {usage.total_files}
                          {usage.file_limit !== null && ` / ${usage.file_limit}`}
                          {usage.is_pro && " (illimité)"}
                        </span>
                      </div>
                      {usage.file_limit !== null && (
                        <Progress
                          value={(usage.total_files / usage.file_limit) * 100}
                        />
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Aucune donnée disponible</p>
                )}
              </div>

              <Separator />

              {/* Plans */}
              {plans && plans.length > 0 && (
                <div className="space-y-3">
                  <span className="text-sm font-medium">Plans disponibles</span>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {plans.map((plan: Plan) => {
                      const isCurrent = plan.id === subscription?.plan
                      return (
                        <div
                          key={plan.id}
                          className={cn(
                            "rounded-lg border p-4 space-y-2",
                            isCurrent && "border-primary",
                            plan.popular && !isCurrent && "border-primary/50"
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">{plan.name}</span>
                            {plan.popular && (
                              <Badge className="text-[10px]">Populaire</Badge>
                            )}
                          </div>
                          <p className="text-lg font-bold">
                            {plan.price === 0 ? "Gratuit" : `${plan.price}€`}
                            {plan.price > 0 && (
                              <span className="text-sm font-normal text-muted-foreground">/mois</span>
                            )}
                          </p>
                          <ul className="space-y-1 text-xs text-muted-foreground">
                            {plan.features.map((f) => (
                              <li key={f} className="flex items-center gap-1.5">
                                <Check className="h-3 w-3 text-primary" />
                                {f}
                              </li>
                            ))}
                          </ul>
                          {isCurrent ? (
                            <Badge variant="outline" className="w-full justify-center text-xs">
                              Plan actuel
                            </Badge>
                          ) : plan.price > 0 ? (
                            <Button
                              size="sm"
                              className="w-full"
                              onClick={handleUpgrade}
                              disabled={isCheckoutLoading}
                            >
                              Choisir
                            </Button>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Invoices link */}
              {subscription?.is_pro && (
                <>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">Factures</span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleManageSubscription}
                      disabled={isPortalLoading}
                    >
                      Voir les factures
                      <ExternalLink className="ml-2 h-3.5 w-3.5" />
                    </Button>
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* ── Invite Dialog ── */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Inviter un collaborateur</DialogTitle>
            <DialogDescription>
              Le membre doit déjà avoir un compte. Il recevra une invitation.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (inviteEmail.trim()) inviteMutation.mutate(inviteEmail.trim())
            }}
          >
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Adresse email</label>
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
                  <Input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="collaborateur@entreprise.com"
                    autoFocus
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setInviteOpen(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={!inviteEmail.trim() || inviteMutation.isPending}>
                {inviteMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                Inviter
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Remove Confirmation ── */}
      <AlertDialog open={!!removingMember} onOpenChange={() => setRemovingMember(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Retirer ce membre ?</AlertDialogTitle>
            <AlertDialogDescription>
              {removingMember?.name || removingMember?.email} sera retiré de l'organisation.
              Ses permissions sur les assistants seront également supprimées.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => removingMember && removeMutation.mutate(removingMember.id)}
            >
              {removeMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Retirer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ── Stat Card ──
function StatCard({
  label,
  value,
  icon: Icon,
  highlight,
}: {
  label: string
  value: string | number
  icon: React.ComponentType<{ className?: string }>
  highlight?: boolean
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-3 space-y-1">
      <div className="flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className={cn("text-lg font-bold", highlight && "text-primary")}>{value}</p>
    </div>
  )
}

// ── Member Row ──
function MemberRow({
  member,
  onRoleChange,
  onRemove,
  isUpdating,
}: {
  member: OrgMember
  onRoleChange: (role: string) => void
  onRemove: () => void
  isUpdating: boolean
}) {
  return (
    <div className="flex items-center justify-between px-4 sm:px-5 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
          <span className="text-xs font-bold text-primary uppercase">
            {(member.name || member.email || "?").charAt(0)}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {member.name || member.email}
          </p>
          {member.name && (
            <p className="text-xs text-muted-foreground truncate">{member.email}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {member.status === "invited" && (
          <Badge variant="outline" className="text-xs">
            Invité
          </Badge>
        )}

        <Select
          value={member.role}
          onValueChange={onRoleChange}
          disabled={isUpdating}
        >
          <SelectTrigger className="w-[110px] h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="admin">
              <div className="flex items-center gap-1.5">
                <Crown className="h-3 w-3" />
                Admin
              </div>
            </SelectItem>
            <SelectItem value="member">
              <div className="flex items-center gap-1.5">
                <Users className="h-3 w-3" />
                Membre
              </div>
            </SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={onRemove}
        >
          <UserMinus className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
