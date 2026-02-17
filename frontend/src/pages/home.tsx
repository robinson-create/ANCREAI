import { Link } from "react-router-dom"
import {
  Search,
  FileText,
  Calendar,
  Shield,
  Check,
  ArrowRight,
  Zap,
  Link2,
  Settings,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const trustedLogos = [
  { name: "Pivert Funéraire", initials: "PF" },
  { name: "Hey Dom", initials: "HD" },
  { name: "RI Direct", initials: "RI" },
]

const whySections = [
  {
    id: "recherche",
    icon: Search,
    title: "Recherche documentaire instantanée",
    bullets: [
      "Trouvez l'information en 2 clics : contrats, procédures, historiques clients, fiches techniques – sans perdre de temps à fouiller vos dossiers.",
      "Interrogez en langage naturel : posez une question, obtenez une réponse exclusivement basée sur vos documents.",
      "Connecteurs intégrés : synchronisation avec votre Drive, SharePoint, CRM (Pipedrive, HubSpot), ERP (Odoo), Notion, etc.",
    ],
  },
  {
    id: "redaction",
    icon: FileText,
    title: "Rédaction de mails et documents optimisée",
    bullets: [
      "Génération automatique de mails : réponses, relances, confirmations – prêtes à envoyer en 1 clic, avec un ton professionnel et personnalisé.",
      "Création de documents simplifiée : devis, contrats, comptes-rendus – modèles pré-remplis à partir de vos données.",
      "Dictée vocale intégrée : rédigez 3x plus vite en parlant, sans saisie manuelle.",
      "Vérification des informations : la plateforme s'assure que tous les détails sont inclus (dates, montants, références, etc.).",
    ],
  },
  {
    id: "calendriers",
    icon: Calendar,
    title: "Gestion des calendriers sans effort",
    bullets: [
      "Planification intelligente : propose des créneaux, envoie des invitations, et synchronise automatiquement avec vos outils (Google Calendar, Outlook, etc.).",
      "Rappels et relances automatiques : plus d'oubli de rendez-vous ou d'échéances.",
      "Vue unifiée : consultez vos plannings, ceux de vos équipes, et vos tâches en un seul endroit.",
    ],
  },
  {
    id: "souverain",
    icon: Shield,
    title: "100 % souverain et sécurisé",
    bullets: [
      "Modèles d'IA français : développés par Mistral AI, pour une maîtrise totale de vos données.",
      "Hébergement en France et en Europe : conformité RGPD, aucune fuite vers des serveurs étrangers.",
      "Accès contrôlés : gérez les permissions par utilisateur ou service, pour une confidentialité absolue.",
    ],
  },
]

const steps = [
  {
    number: "1",
    icon: Link2,
    title: "Connectez vos outils",
    bullets: [
      "Importez vos documents (glisser-déposer depuis votre Drive, SharePoint, etc.).",
      "Liez votre boîte mail et votre calendrier (Gmail, Outlook, etc.).",
      "Ajoutez vos connecteurs (CRM, ERP, Notion, outils de mailing).",
    ],
  },
  {
    number: "2",
    icon: Settings,
    title: "Personnalisez votre espace",
    bullets: [
      "Définissez vos modèles de mails et documents (devis, contrats, relances).",
      "Activez la dictée vocale pour rédiger plus vite.",
      "Paramétrez vos rappels (rendez-vous, échéances, tâches).",
    ],
  },
  {
    number: "3",
    icon: Zap,
    title: "Utilisez la plateforme au quotidien",
    bullets: [
      "Recherchez une information en langage naturel (ex : « Quel est le contrat signé avec le client X en 2025 ? »).",
      "Générez un mail ou un document en 1 clic, avec toutes les données à jour.",
      "Consultez votre planning et laissez la plateforme gérer les invitations et relances.",
    ],
  },
]

const techPoints = [
  {
    icon: Zap,
    title: "Interface intuitive et sans formation",
    description:
      "Tableau de bord clair : accédez à vos mails, documents et calendriers en un coup d'œil. Recherche ultra-rapide : résultats en moins de 2 secondes, même sur des milliers de pages. Dictée vocale et saisie simplifiée : gain de temps garanti sur la rédaction.",
  },
  {
    icon: FileText,
    title: "Technologie RAG (Retrieval-Augmented Generation)",
    description:
      "Réponses 100 % basées sur vos documents : pas d'hallucinations, pas d'erreurs. Mise à jour en temps réel : vos données sont toujours à jour et exploitables.",
  },
  {
    icon: Calendar,
    title: "Tarifs transparents et évolutifs",
    description:
      "Offres adaptées à votre taille (1 à 100+ utilisateurs). Essai gratuit de 10 jours : testez sans carte bancaire. Abonnements flexibles : passez d'un plan à l'autre en 1 clic.",
  },
]

const keyPoints = [
  "Recherche documentaire en 2 clics – plus de temps perdu à chercher.",
  "Rédaction de mails et documents 3x plus rapide – avec dictée vocale et modèles intelligents.",
  "Gestion des calendriers automatisée – invitations, rappels, synchronisation.",
  "100 % souverain – modèles Mistral AI + hébergement en France/UE.",
  "Conçu par des dirigeants, pour des dirigeants – zéro compétence technique requise.",
]

export function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section id="accueil" className="relative overflow-hidden bg-gradient-to-b from-primary/5 to-background py-20 md:py-32">
        <div className="container relative z-10">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl lg:text-6xl">
              Gagnez du temps sur vos mails, documents et plannings
            </h1>
            <p className="mt-4 text-lg font-medium text-primary md:text-xl">
              Une plateforme 100 % souveraine, conçue par des dirigeants pour des
              dirigeants
            </p>
            <p className="mt-6 text-lg text-muted-foreground md:text-xl max-w-3xl mx-auto">
              Recherche, rédaction et calendriers : tout en un, sans compétence
              technique. Connectez vos outils et libérez jusqu'à{" "}
              <strong className="text-foreground">25 % de votre temps quotidien</strong>.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button size="lg" asChild>
                <Link to="/signup">
                  Essai gratuit de 10 jours
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/pricing">Découvrir les offres</Link>
              </Button>
            </div>
          </div>
        </div>
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute -top-1/2 left-1/2 h-[800px] w-[800px] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />
        </div>
      </section>

      {/* Trust Section */}
      <section className="border-y bg-muted/30 py-12">
        <div className="container">
          <p className="text-center text-sm font-medium text-muted-foreground mb-8">
            Ils nous font confiance pour optimiser leur quotidien
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
      <section id="fonctionnalites" className="py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Pourquoi choisir notre plateforme ?
            </h2>
          </div>

          <div className="mt-16 space-y-16">
            {whySections.map((section) => (
              <div key={section.id}>
                <div className="flex items-center gap-3 mb-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <section.icon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-2xl font-semibold">{section.title}</h3>
                </div>
                <ul className="space-y-3">
                  {section.bullets.map((bullet, i) => (
                    <li key={i} className="flex gap-3">
                      <Check className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                      <span className="text-muted-foreground">{bullet}</span>
                    </li>
                  ))}
                </ul>
              </div>
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
              3 étapes pour gagner du temps dès aujourd'hui
            </p>
          </div>

          <div className="mt-16 grid gap-12 md:grid-cols-3">
            {steps.map((step) => (
              <Card key={step.number} className="border-2">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground text-lg font-bold">
                      {step.number}
                    </div>
                    <step.icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle className="text-xl">{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {step.bullets.map((bullet, i) => (
                      <li key={i} className="flex gap-2 text-sm">
                        <span className="text-primary">•</span>
                        <span className="text-muted-foreground">{bullet}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Technology Section */}
      <section className="py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Une technologie pensée pour les dirigeants
            </h2>
          </div>

          <div className="mt-16 grid gap-8 md:grid-cols-3">
            {techPoints.map((point) => (
              <Card
                key={point.title}
                className="border-2 hover:border-primary/50 transition-colors"
              >
                <CardHeader>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <point.icon className="h-6 w-6 text-primary" />
                  </div>
                  <CardTitle className="text-lg">{point.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">
                    {point.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Key Points Section */}
      <section className="border-y bg-muted/30 py-20 md:py-32">
        <div className="container">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ce qu'il faut retenir
            </h2>
          </div>

          <div className="mt-12 space-y-4 max-w-2xl mx-auto">
            {keyPoints.map((point, i) => (
              <div key={i} className="flex gap-3 items-start">
                <Check className="h-6 w-6 text-primary shrink-0 mt-0.5" />
                <span className="text-muted-foreground">{point}</span>
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
              Prêt à optimiser votre quotidien ?
            </h2>
            <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" asChild>
                <Link to="/signup">
                  Essayer gratuitement
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link to="/pricing">Voir les tarifs</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
