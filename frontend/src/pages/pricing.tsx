import { Link } from "react-router-dom"
import { Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { SubscriptionPlanDetails } from "@/types"

const plans: SubscriptionPlanDetails[] = [
  {
    id: "starter",
    name: "Starter",
    price: 0,
    max_assistants: 3,
    max_storage_gb: 1,
    max_chat_tokens: 500000,
    features: [
      "3 assistants IA",
      "1 Go de stockage",
      "500k tokens/mois",
      "Support email",
      "Essai gratuit 10 jours",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 29,
    max_assistants: 5,
    max_storage_gb: 5,
    max_chat_tokens: 2000000,
    features: [
      "5 assistants IA",
      "5 Go de stockage",
      "2M tokens/mois",
      "Support prioritaire",
      "API access",
    ],
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 99,
    max_assistants: 10,
    max_storage_gb: 20,
    max_chat_tokens: 10000000,
    features: [
      "10 assistants IA",
      "20 Go de stockage",
      "10M tokens/mois",
      "Support dédié",
      "API access",
      "SSO / SAML",
    ],
  },
]

export function PricingPage() {
  return (
    <div className="py-20">
      <div className="container">
        {/* Header */}
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Tarifs simples et transparents
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Choisissez le plan adapté à vos besoins. Commencez gratuitement
            pendant 10 jours.
          </p>
        </div>

        {/* Plans */}
        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {plans.map((plan) => (
            <Card
              key={plan.id}
              className={cn(
                "relative flex flex-col",
                plan.popular && "border-primary shadow-lg"
              )}
            >
              {plan.popular && (
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">
                  Populaire
                </Badge>
              )}
              <CardHeader>
                <CardTitle className="text-2xl">{plan.name}</CardTitle>
                <CardDescription>
                  <span className="text-4xl font-bold text-foreground">
                    {plan.price === 0 ? "Gratuit" : `${plan.price}€`}
                  </span>
                  {plan.price > 0 && (
                    <span className="text-muted-foreground">/mois</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1">
                <ul className="space-y-3">
                  {plan.features.map((feature: string) => (
                    <li key={feature} className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                <Button
                  className="w-full"
                  variant={plan.popular ? "default" : "outline"}
                  asChild
                >
                  <Link to={`/onboarding?plan=${plan.id}`}>
                    {plan.price === 0 ? "Commencer gratuitement" : "Choisir ce plan"}
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>

        {/* FAQ or additional info */}
        <div className="mt-20 text-center">
          <p className="text-muted-foreground">
            Besoin d'un plan personnalisé ?{" "}
            <a
              href="mailto:contact@mecano-man.com"
              className="font-medium text-primary hover:underline"
            >
              Contactez-nous
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
