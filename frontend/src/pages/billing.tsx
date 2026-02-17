import { useState } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { Check, CreditCard, FileText, Zap, Loader2, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/hooks/use-toast"
import { billingApi, type Plan } from "@/api/billing"
import { cn } from "@/lib/utils"

export function BillingPage() {
  const { toast } = useToast()
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false)
  const [isPortalLoading, setIsPortalLoading] = useState(false)

  const { data: subscription, isLoading: isLoadingSubscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: billingApi.getSubscription,
  })

  const { data: usage, isLoading: isLoadingUsage } = useQuery({
    queryKey: ["billing-usage"],
    queryFn: billingApi.getUsage,
  })

  const { data: plans } = useQuery({
    queryKey: ["plans"],
    queryFn: billingApi.getPlans,
  })

  const handleUpgrade = async () => {
    setIsCheckoutLoading(true)
    try {
      const url = await billingApi.createCheckout(
        `${window.location.origin}/app/billing?success=true`,
        `${window.location.origin}/app/billing?canceled=true`
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
        `${window.location.origin}/app/billing`
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

  const getStatusBadge = () => {
    if (!subscription) return null
    switch (subscription.status) {
      case "active":
        return <Badge variant="default">Actif</Badge>
      case "trialing":
        return <Badge variant="secondary">Essai</Badge>
      case "past_due":
        return <Badge variant="destructive">Paiement en retard</Badge>
      case "canceled":
        return <Badge variant="destructive">Annulé</Badge>
      default:
        return null
    }
  }

  const currentPlan = plans?.find((p) => p.id === subscription?.plan)

  return (
    <div className="container max-w-4xl py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Facturation</h1>
        <p className="mt-1 text-muted-foreground">
          Gérez votre abonnement et consultez votre utilisation
        </p>
      </div>

      {/* Current plan */}
      <Card className="mb-8">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Abonnement actuel</CardTitle>
            </div>
            {getStatusBadge()}
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingSubscription ? (
            <Skeleton className="h-12 w-48" />
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">
                  {currentPlan?.name || "Free"}
                </p>
                <p className="text-muted-foreground">
                  {currentPlan?.price === 0
                    ? "Gratuit"
                    : `${currentPlan?.price}€/mois`}
                </p>
              </div>
              <div className="flex gap-2">
                {subscription?.is_pro ? (
                  <Button
                    variant="outline"
                    onClick={handleManageSubscription}
                    disabled={isPortalLoading}
                  >
                    {isPortalLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <ExternalLink className="mr-2 h-4 w-4" />
                    )}
                    Gérer l'abonnement
                  </Button>
                ) : (
                  <Button onClick={handleUpgrade} disabled={isCheckoutLoading}>
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
            <p className="mt-4 text-sm text-destructive">
              Votre abonnement sera annulé à la fin de la période en cours.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Usage stats */}
      <Card className="mb-8">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Utilisation</CardTitle>
          </div>
          <CardDescription>
            Votre consommation actuelle
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {isLoadingUsage ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : usage ? (
            <>
              {/* Daily chat requests */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Requêtes chat aujourd'hui</span>
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

              {/* Total files */}
              <div className="space-y-2">
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
            </>
          ) : (
            <p className="text-muted-foreground">
              Aucune donnée d'utilisation disponible
            </p>
          )}
        </CardContent>
      </Card>

      {/* Available plans */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Plans disponibles</CardTitle>
          <CardDescription>
            Comparez les plans et choisissez celui qui vous convient
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            {plans?.map((plan: Plan) => {
              const isCurrent = plan.id === subscription?.plan
              return (
                <Card
                  key={plan.id}
                  className={cn(
                    "relative",
                    isCurrent && "border-primary",
                    plan.popular && !isCurrent && "border-primary/50"
                  )}
                >
                  {plan.popular && (
                    <Badge className="absolute -top-2 left-1/2 -translate-x-1/2">
                      Populaire
                    </Badge>
                  )}
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">{plan.name}</CardTitle>
                    <CardDescription>
                      <span className="text-2xl font-bold text-foreground">
                        {plan.price === 0 ? "Gratuit" : `${plan.price}€`}
                      </span>
                      {plan.price > 0 && (
                        <span className="text-muted-foreground">/mois</span>
                      )}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pb-2">
                    <ul className="space-y-1 text-sm">
                      {plan.features.map((feature) => (
                        <li key={feature} className="flex items-center gap-2">
                          <Check className="h-3 w-3 text-primary" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                  <CardFooter>
                    {isCurrent ? (
                      <Badge variant="outline" className="w-full justify-center">
                        Plan actuel
                      </Badge>
                    ) : plan.price > 0 ? (
                      <Button
                        variant="default"
                        className="w-full"
                        size="sm"
                        onClick={handleUpgrade}
                        disabled={isCheckoutLoading}
                      >
                        {isCheckoutLoading && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Choisir
                      </Button>
                    ) : (
                      <Badge variant="secondary" className="w-full justify-center">
                        Plan gratuit
                      </Badge>
                    )}
                  </CardFooter>
                </Card>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Invoices */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <CardTitle>Factures</CardTitle>
            </div>
            {subscription?.is_pro && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleManageSubscription}
                disabled={isPortalLoading}
              >
                Voir les factures
                <ExternalLink className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
          <CardDescription>
            Accédez à vos factures via le portail Stripe
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <p className="text-center text-muted-foreground py-4">
            {subscription?.is_pro
              ? "Cliquez sur \"Voir les factures\" pour accéder à votre historique."
              : "Les factures sont disponibles uniquement pour les abonnements Pro."}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
