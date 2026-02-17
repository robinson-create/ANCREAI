import { Link } from "react-router-dom"
import {
  Bot,
  FileText,
  MessageSquare,
  Upload,
  CreditCard,
  Settings,
  Database,
  Clock,
  Layers,
  Check,
  ArrowRight,
  Users,
  Shield,
  Zap,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const benefits = [
  {
    icon: Database,
    title: "Centralisation de l'expertise",
    description:
      "Ne perdez plus de temps à chercher l'information dispersée ; vos assistants synthétisent vos PDF, Word et textes en quelques secondes.",
  },
  {
    icon: MessageSquare,
    title: "Réponses contextuelles précises",
    description:
      "Contrairement aux IA génériques, nos assistants répondent uniquement en se basant sur la base de connaissances que vous leur fournissez (fiches techniques, procédures, contrats).",
  },
  {
    icon: Zap,
    title: "Autonomie immédiate",
    description:
      "Une interface pensée pour les professionnels, permettant de créer, modifier et interroger vos assistants sans formation préalable.",
  },
]

const steps = [
  {
    number: "1",
    icon: CreditCard,
    title: "Créez votre compte et choisissez votre offre",
    description:
      "Sélectionnez le plan adapté à vos besoins (3, 5 ou 10 assistants) via notre page de pricing transparente.",
  },
  {
    number: "2",
    icon: Upload,
    title: "Renseignez vos documents",
    description:
      "Importez vos fichiers (glisser-déposer) pour nourrir la mémoire de chaque assistant.",
  },
  {
    number: "3",
    icon: MessageSquare,
    title: "Questionnez votre assistant",
    description:
      "Posez vos questions en langage naturel via l'interface de chat et obtenez des réponses basées exclusivement sur vos sources.",
  },
]

const assistantFeatures = [
  {
    icon: Settings,
    title: "Configuration du rôle (System Prompt)",
    description:
      "Définissez la personnalité et le rôle de l'assistant (ex: « Expert Juridique », « Support Technique », « Assistant RH »). C'est ici que vous donnez l'instruction racine qui guidera son comportement.",
  },
  {
    icon: FileText,
    title: "Alimentation de la mémoire",
    description:
      "L'ajout de documents se fait via une interface d'upload simplifiée ou par simple \"drag and drop\". Il n'y a pour l'instant aucune limite stricte au volume de fichiers importés, permettant de constituer une base documentaire exhaustive.",
  },
  {
    icon: Layers,
    title: "Flexibilité des abonnements",
    description:
      "Si votre besoin évolue et que vous atteignez la limite de votre plan (par exemple 3 assistants sur 3), le système vous notifie et vous propose de passer au plan supérieur (5 ou 10 assistants) en un clic.",
  },
]

const chatFeatures = [
  "Le nom de votre assistant expert en en-tête.",
  "Une zone d'historique sur la gauche pour retrouver vos échanges précédents.",
  "Une barre de discussion centrale pour poser vos questions.",
]

const keyPoints = [
  {
    icon: Bot,
    title: "Création sur mesure",
    description:
      "Configurez jusqu'à 10 assistants spécialisés selon votre abonnement.",
  },
  {
    icon: Layers,
    title: "Interface unifiée",
    description:
      "Un dashboard unique pour gérer les assistants, les documents (upload illimité) et la facturation.",
  },
  {
    icon: Database,
    title: "Technologie RAG",
    description:
      "L'IA répond en utilisant exclusivement vos documents comme source de vérité.",
  },
  {
    icon: Upload,
    title: "Simplicité d'usage",
    description:
      "Une expérience utilisateur fluide, du drag & drop des fichiers au chat conversationnel.",
  },
  {
    icon: Users,
    title: "Scalabilité",
    description:
      "Des offres évolutives (3, 5, 10 assistants) adaptées à la taille de votre structure.",
  },
]

// Placeholder logos for trust section
const trustedLogos = [
  { name: "Pivert Funéraire", initials: "PF" },
  { name: "Hey Dom", initials: "HD" },
  { name: "RI Direct", initials: "RI" },
]

export function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-primary/5 to-background py-20 md:py-32">
        <div className="container relative z-10">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl lg:text-6xl">
              Vos assistants experts :{" "}
              <span className="text-primary">
                Transformez vos documents en dialogue intelligent
              </span>
            </h1>
            <p className="mt-6 text-lg text-muted-foreground md:text-xl max-w-3xl mx-auto">
              Notre solution permet aux dirigeants de PME de configurer des
              assistants intelligents capables d'analyser, de comprendre et de
              restituer l'information contenue dans vos propres documents
              d'entreprise, sans aucune compétence technique.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" asChild>
                <Link to="/pricing">
                  Découvrir les offres
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/signup">Essai gratuit</Link>
              </Button>
            </div>
          </div>
        </div>

        {/* Background decoration */}
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute -top-1/2 left-1/2 h-[800px] w-[800px] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
        </div>
      </section>

      {/* Trust Section */}
      <section className="border-y bg-muted/30 py-12">
        <div className="container">
          <p className="text-center text-sm font-medium text-muted-foreground mb-8">
            Ils nous font confiance pour leur gestion documentaire
          </p>
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-16">
            {trustedLogos.map((logo) => (
              <div
                key={logo.name}
                className="flex items-center gap-3 text-muted-foreground hover:text-foreground transition-colors"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-muted border font-bold text-lg">
                  {logo.initials}
                </div>
                <span className="font-medium">{logo.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why Section */}
      <section className="py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Pourquoi adopter un assistant IA personnalisé ?
            </h2>
          </div>

          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {benefits.map((benefit) => (
              <Card
                key={benefit.title}
                className="border-2 hover:border-primary/50 transition-colors"
              >
                <CardHeader>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <benefit.icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle className="text-xl">{benefit.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">
                    {benefit.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="border-y bg-muted/30 py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Comment ça marche ?
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Votre expert dédié en 3 étapes. L'outil a été conçu pour une prise
              en main immédiate.
            </p>
          </div>

          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {steps.map((step) => (
              <div key={step.number} className="relative">
                <div className="flex flex-col items-center text-center">
                  <div className="relative">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground text-2xl font-bold">
                      {step.number}
                    </div>
                    <div className="absolute -bottom-1 -right-1 flex h-8 w-8 items-center justify-center rounded-full bg-background border-2 border-primary">
                      <step.icon className="h-4 w-4 text-primary" />
                    </div>
                  </div>
                  <h3 className="mt-6 text-xl font-semibold">{step.title}</h3>
                  <p className="mt-2 text-muted-foreground">
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Technology Section */}
      <section className="py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-3xl">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl text-center">
              Une technologie puissante au service de votre productivité
            </h2>
            <div className="mt-8 space-y-6 text-muted-foreground">
              <p>
                Dans un contexte économique où la rapidité d'accès à
                l'information est critique, l'automatisation documentaire
                devient un levier de performance incontournable. Notre
                plateforme ne se contente pas de stocker vos fichiers ; elle les
                rend « intelligents ».
              </p>
              <p>
                Le cœur de notre système repose sur une interface de gestion
                fluide. Dès votre connexion, vous accédez à un tableau de bord
                (dashboard) épuré. Le menu latéral vous offre un accès direct à
                votre profil, à la facturation (billing) et surtout, à la
                gestion de vos assistants IA personnalisés.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Assistant Management Section */}
      <section className="border-y bg-muted/30 py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Gestion intuitive de vos assistants
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              La page « Mes Assistants » est le centre de contrôle de votre
              activité. Vous y visualisez l'ensemble de vos agents virtuels sous
              forme de cartes claires.
            </p>
          </div>

          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {assistantFeatures.map((feature) => (
              <Card key={feature.title} className="border-2">
                <CardHeader>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <feature.icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Chat Experience Section */}
      <section className="py-20 md:py-32">
        <div className="container">
          <div className="grid gap-12 lg:grid-cols-2 items-center">
            <div>
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
                Une expérience conversationnelle fluide
              </h2>
              <p className="mt-4 text-muted-foreground">
                Lorsque vous cliquez sur l'un de vos assistants, vous basculez
                vers l'interface de conversation. Conçue pour être familière aux
                utilisateurs d'outils comme ChatGPT, elle présente :
              </p>
              <ul className="mt-6 space-y-3">
                {chatFeatures.map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-8 p-4 rounded-lg bg-primary/5 border border-primary/20">
                <p className="text-sm">
                  <strong className="text-primary">
                    Technologie RAG (Retrieval-Augmented Generation) :
                  </strong>{" "}
                  Chaque réponse fournie par l'assistant est générée après
                  analyse des documents que vous lui avez attribués, garantissant
                  ainsi fiabilité et confidentialité.
                </p>
              </div>
            </div>
            <div className="relative">
              <div className="aspect-video rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 border-2 border-primary/20 flex items-center justify-center">
                <div className="text-center p-8">
                  <MessageSquare className="h-16 w-16 text-primary/40 mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    Interface de chat intuitive
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Admin Section */}
      <section className="border-y bg-muted/30 py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-3xl text-center">
            <Clock className="h-12 w-12 text-primary mx-auto mb-6" />
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Maîtrise des coûts et administration
            </h2>
            <p className="mt-6 text-muted-foreground">
              L'aspect administratif a été réduit à l'essentiel pour ne pas
              encombrer l'utilisateur. Le menu déroulant du profil permet
              d'accéder rapidement à la section « Billing » pour télécharger vos
              factures ou modifier votre moyen de paiement. La page de pricing
              est accessible à tout moment pour ajuster votre capacité (nombre
              d'assistants) en fonction de la croissance de votre entreprise.
            </p>
            <div className="mt-8 p-6 rounded-lg bg-background border-2">
              <p className="text-lg font-medium">
                En résumé, notre solution transforme votre{" "}
                <span className="text-primary">passif documentaire</span> en{" "}
                <span className="text-primary">actif conversationnel</span>.
              </p>
              <p className="mt-4 text-muted-foreground">
                Que ce soit pour onboarder un nouveau collaborateur grâce à un
                assistant RH qui connaît toutes vos procédures, ou pour aider un
                technicien à trouver une référence dans 500 pages de manuels,
                votre assistant IA personnalisé est opérationnel 24h/24.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Key Points Section */}
      <section className="py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <Shield className="h-12 w-12 text-primary mx-auto mb-6" />
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ce qu'il faut retenir
            </h2>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {keyPoints.map((point) => (
              <div
                key={point.title}
                className="flex flex-col items-center text-center p-6 rounded-lg border-2 hover:border-primary/50 transition-colors bg-background"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
                  <point.icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="font-semibold mb-2">{point.title}</h3>
                <p className="text-sm text-muted-foreground">
                  {point.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t bg-gradient-to-b from-primary/5 to-background py-20">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Prêt à transformer vos documents ?
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Créez votre premier assistant IA en quelques minutes. Essai
              gratuit de 10 jours, sans carte bancaire.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" asChild>
                <Link to="/pricing">
                  Voir les tarifs
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/signup">Commencer gratuitement</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
