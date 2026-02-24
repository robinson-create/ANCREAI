import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Search,
  Mail,
  ShieldCheck,
  Users,
  Send,
  Check,
  Calendar,
  FolderOpen,
  Mic,
  Link2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const TOTAL_STEPS = 10;

const roles = [
  "Collaborateur individuel",
  "Manager d'une petite équipe",
  "Manager d'une grande équipe",
  "Directeur / VP",
  "CEO / Dirigeant",
];

type FeatureStep = {
  type: "feature";
  icon: React.ElementType;
  title: string;
  highlight: string;
  description: string;
  visual?: React.ReactNode;
};
type RoleStep = { type: "role" };
type TeamStep = { type: "team" };
type InfoStep = { type: "info" };
type PricingStep = { type: "pricing" };
type Step = RoleStep | FeatureStep | TeamStep | InfoStep | PricingStep;

const DocSearchVisual = () => (
  <div className="space-y-2">
    {[
      { label: "NDA_Partenariat.pdf", sub: "Contrat signé le 12/01" },
      { label: "Facture_2024-089.pdf", sub: "Montant : 4 500 €" },
      { label: "Devis_Refonte_Site.docx", sub: "En attente de validation" },
      { label: "Lettre_Résiliation.pdf", sub: "Envoyée le 03/02" },
    ].map((d, i) => (
      <motion.div
        key={i}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.2 + i * 0.1 }}
        className="p-3 rounded-lg bg-muted border border-border"
      >
        <div className="font-medium text-sm text-foreground">{d.label}</div>
        <div className="text-xs text-muted-foreground">{d.sub}</div>
      </motion.div>
    ))}
  </div>
);

const MailVisual = () => (
  <div className="space-y-3">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      className="p-4 rounded-xl bg-muted border border-border space-y-3"
    >
      <div className="space-y-2">
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-muted-foreground">À :</span>
          <span className="text-foreground font-medium">Client Dupont</span>
          <span className="text-muted-foreground ml-4">CC</span>
          <span className="text-muted-foreground ml-4">BC</span>
        </div>
      </div>
      <div className="text-sm text-foreground">Bonjour M. Dupont, suite à notre échange…</div>
      <Button size="sm" className="w-full">
        <Send className="h-4 w-4 mr-2" />
        Envoyer
      </Button>
    </motion.div>
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5 }}
      className="pt-2 border-t border-border text-xs text-muted-foreground flex items-center justify-between"
    >
      <span>Client Dupont</span>
      <span>Relance devis</span>
      <span className="text-accent">Brouillon</span>
    </motion.div>
  </div>
);

const CalendarVisual = () => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: 0.3 }}
    className="p-4 rounded-xl bg-muted border border-border space-y-2"
  >
    <div className="text-sm text-foreground">
      Quand un client demande un RDV urgent, vérifier mon agenda et proposer un créneau disponible cette semaine.
    </div>
    <div className="text-xs text-muted-foreground text-right">Règle automatique</div>
  </motion.div>
);

const FolderVisual = () => (
  <div className="space-y-2">
    {[
      { name: "Dossier Commercial", items: "12 docs, 5 mails, 2 sites" },
      { name: "Dossier RH", items: "8 docs, 3 mails" },
      { name: "Dossier Juridique", items: "15 contrats, 4 mails" },
    ].map((d, i) => (
      <motion.div
        key={i}
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 + i * 0.12 }}
        className="p-3 rounded-lg bg-muted border border-border"
      >
        <div className="font-medium text-sm text-foreground">{d.name}</div>
        <div className="text-xs text-muted-foreground">{d.items}</div>
      </motion.div>
    ))}
  </div>
);

const VoiceVisual = () => (
  <motion.div
    initial={{ scale: 0.8, opacity: 0 }}
    animate={{ scale: 1, opacity: 1 }}
    transition={{ delay: 0.3 }}
    className="p-4 rounded-xl bg-muted border border-border"
  >
    <div className="flex items-center justify-center space-x-1 h-16">
      {[3, 5, 8, 12, 8, 5, 10, 6, 4, 7, 11, 6, 3].map((h, i) => (
        <motion.div
          key={i}
          className="w-1 bg-primary rounded-full"
          initial={{ height: `${h * 2}px` }}
          animate={{ height: [`${h * 2}px`, `${h * 4}px`, `${h * 2}px`] }}
          transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.06 }}
        />
      ))}
    </div>
  </motion.div>
);

const SovereignVisual = () => (
  <motion.div
    initial={{ scale: 0.8, opacity: 0 }}
    animate={{ scale: 1, opacity: 1 }}
    transition={{ delay: 0.3 }}
    className="p-4 rounded-xl bg-muted border border-border space-y-3"
  >
    {["Mistral AI – IA française", "Hébergement France / UE", "Conforme RGPD"].map((t, i) => (
      <motion.div
        key={i}
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.4 + i * 0.1 }}
        className="flex items-center space-x-2"
      >
        <ShieldCheck className="h-5 w-5 text-success" />
        <span className="text-sm text-foreground">✓ {t}</span>
      </motion.div>
    ))}
  </motion.div>
);

const steps: Step[] = [
  { type: "info" },
  { type: "role" },
  {
    type: "feature",
    icon: Search,
    title: "Recherchez",
    highlight: "dans tous vos documents",
    description:
      "NDA, contrats, factures, devis, lettres… trouvez n'importe quelle information en langage naturel.",
    visual: <DocSearchVisual />,
  },
  {
    type: "feature",
    icon: Mail,
    title: "Rédigez vos mails",
    highlight: "avec votre contexte",
    description: "Ancre connaît vos dossiers et génère des mails personnalisés en 1 clic.",
    visual: <MailVisual />,
  },
  {
    type: "feature",
    icon: Calendar,
    title: "Gérez votre agenda",
    highlight: "sans effort",
    description: "Synchronisez vos calendriers, proposez des créneaux automatiquement.",
    visual: <CalendarVisual />,
  },
  {
    type: "feature",
    icon: FolderOpen,
    title: "Organisez vos dossiers",
    highlight: "avec tout le contexte",
    description: "Regroupez recherches, mails, documents par contexte.",
    visual: <FolderVisual />,
  },
  {
    type: "feature",
    icon: Mic,
    title: "Dictée vocale",
    highlight: "sur toutes vos interactions",
    description: "Rédigez en parlant, partout dans Ancre.",
    visual: <VoiceVisual />,
  },
  {
    type: "feature",
    icon: ShieldCheck,
    title: "100 % souverain",
    highlight: "et sécurisé",
    description: "IA française, données en France/UE, conforme RGPD.",
    visual: <SovereignVisual />,
  },
  { type: "pricing" },
  { type: "team" },
];

const ProgressBar = ({ current }: { current: number }) => (
  <div className="flex items-center justify-center space-x-2 mb-8">
    {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
      <div
        key={i}
        className={`h-1 rounded-full transition-all duration-300 ${
          i <= current
            ? "w-6 bg-gradient-to-r from-primary to-accent"
            : "w-4 bg-muted"
        }`}
      />
    ))}
  </div>
);

const ContinueButton = ({
  onClick,
  label = "Continuer",
  disabled = false,
}: {
  onClick: () => void;
  label?: string;
  disabled?: boolean;
}) => (
  <div className="flex justify-center">
    <Button
      onClick={onClick}
      disabled={disabled}
      size="lg"
      className="w-full max-w-md hover:scale-105 active:scale-100 transition-transform"
    >
      {label}
    </Button>
  </div>
);

const pricingPlans = [
  {
    id: "starter",
    name: "Starter",
    price: 0,
    period: "Gratuit",
    popular: false,
    features: [
      "3 assistants IA",
      "1 Go de stockage",
      "500k tokens/mois",
      "Essai gratuit 10 jours",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 29,
    period: "/mois",
    popular: true,
    features: [
      "5 assistants IA",
      "5 Go de stockage",
      "2M tokens/mois",
      "Support prioritaire",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 99,
    period: "/mois",
    popular: false,
    features: [
      "10 assistants IA",
      "20 Go de stockage",
      "10M tokens/mois",
      "Support dédié",
    ],
  },
];

const OnboardingV2 = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string>("starter");
  const [teamEmails, setTeamEmails] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [company, setCompany] = useState("");
  const [initialQuery, setInitialQuery] = useState("");

  useEffect(() => {
    // Récupérer la query initiale depuis la landing page
    const query = sessionStorage.getItem("ancre_initial_query");
    if (query) {
      setInitialQuery(query);
      sessionStorage.removeItem("ancre_initial_query");
    }
  }, []);

  const next = () => {
    if (currentStep < TOTAL_STEPS - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      // Fin du tour - rediriger vers la transition
      navigate("/app/onboarding/transition", {
        state: { firstName, lastName, company, role: selectedRole, teamEmails, initialQuery },
      });
    }
  };

  const step = steps[currentStep];

  if (!step) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-3xl">
        <ProgressBar current={currentStep} />

        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
            className="glass rounded-2xl p-8 md:p-12"
          >
            {step.type === "info" && (
              <>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-4 text-center">
                  Bienvenue sur Ancre
                </h2>
                <p className="text-muted-foreground text-center mb-8">
                  Parlez-nous de vous pour personnaliser votre expérience.
                </p>

                {initialQuery && (
                  <div className="mb-6 p-4 rounded-xl bg-accent/10 border border-accent/20">
                    <p className="text-sm text-foreground">
                      <span className="font-semibold">Vous cherchiez :</span> "{initialQuery}"
                    </p>
                  </div>
                )}

                <div className="space-y-4 mb-8">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Prénom</label>
                    <input
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="Jean"
                      maxLength={100}
                      className="w-full rounded-xl bg-muted border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Nom</label>
                    <input
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Dupont"
                      maxLength={100}
                      className="w-full rounded-xl bg-muted border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-accent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Nom de l'entreprise</label>
                    <input
                      type="text"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Acme Inc."
                      maxLength={200}
                      className="w-full rounded-xl bg-muted border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-accent"
                    />
                  </div>
                </div>

                <ContinueButton
                  onClick={next}
                  disabled={!firstName.trim() || !lastName.trim() || !company.trim()}
                />
              </>
            )}

            {step.type === "role" && (
              <>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-8 text-center">
                  Quel est votre rôle ?
                </h2>

                <div className="space-y-3 mb-8">
                  {roles.map((r) => (
                    <button
                      key={r}
                      onClick={() => setSelectedRole(r)}
                      className={`w-full flex items-center justify-between rounded-xl px-5 py-4 border text-left text-sm font-medium transition-colors ${
                        selectedRole === r
                          ? "bg-card border-accent text-foreground"
                          : "bg-muted border-border text-foreground/80 hover:bg-muted/80"
                      }`}
                    >
                      {r}
                      <div className="flex items-center">
                        {selectedRole === r && (
                          <div className="h-5 w-5 rounded-full bg-accent flex items-center justify-center">
                            <div className="h-2 w-2 rounded-full bg-white" />
                          </div>
                        )}
                      </div>
                    </button>
                  ))}
                </div>

                <ContinueButton onClick={next} disabled={!selectedRole} />
              </>
            )}

            {step.type === "feature" && (
              <>
                {(step as FeatureStep).visual}

                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mt-8 mb-4 text-center">
                  {(step as FeatureStep).title}{" "}
                  <span className="text-gradient">{(step as FeatureStep).highlight}</span>
                </h2>

                <p className="text-muted-foreground text-center mb-8">
                  {(step as FeatureStep).description}
                </p>

                <ContinueButton onClick={next} />
              </>
            )}

            {step.type === "pricing" && (
              <>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-4 text-center">
                  Choisissez votre plan
                </h2>
                <p className="text-muted-foreground text-center mb-8">
                  Commencez avec 10 jours d'essai gratuit. Annulez à tout moment.
                </p>

                <div className="grid gap-4 mb-8 md:grid-cols-3">
                  {pricingPlans.map((plan) => (
                    <motion.button
                      key={plan.id}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.1 }}
                      onClick={() => setSelectedPlan(plan.id)}
                      className={`relative p-6 rounded-xl border-2 text-left transition-all ${
                        selectedPlan === plan.id
                          ? "border-primary bg-primary/5 shadow-lg"
                          : "border-border bg-card hover:border-primary/50"
                      }`}
                    >
                      {plan.popular && (
                        <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-primary to-accent">
                          Populaire
                        </Badge>
                      )}

                      <div className="mb-4">
                        <h3 className="font-heading font-bold text-xl text-foreground mb-2">
                          {plan.name}
                        </h3>
                        <div className="flex items-baseline">
                          <span className="text-3xl font-bold text-foreground">
                            {plan.price === 0 ? "Gratuit" : `${plan.price}€`}
                          </span>
                          {plan.price > 0 && (
                            <span className="text-muted-foreground ml-1">{plan.period}</span>
                          )}
                        </div>
                      </div>

                      <ul className="space-y-2">
                        {plan.features.map((feature, i) => (
                          <li key={i} className="flex items-center gap-2 text-sm">
                            <Check className="h-4 w-4 text-primary flex-shrink-0" />
                            <span className="text-foreground">{feature}</span>
                          </li>
                        ))}
                      </ul>

                      {selectedPlan === plan.id && (
                        <div className="absolute top-4 right-4 h-6 w-6 rounded-full bg-primary flex items-center justify-center">
                          <Check className="h-4 w-4 text-white" />
                        </div>
                      )}
                    </motion.button>
                  ))}
                </div>

                <div className="text-center mb-8">
                  <p className="text-sm text-muted-foreground">
                    🔒 Paiement sécurisé avec Stripe • Annulez à tout moment
                  </p>
                </div>

                <ContinueButton
                  onClick={next}
                  label={selectedPlan === "starter" ? "Commencer l'essai gratuit" : "Continuer vers le paiement"}
                />
              </>
            )}

            {step.type === "team" && (
              <>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-4 text-center">
                  Invitez votre équipe. Travaillez ensemble.
                </h2>
                <p className="text-muted-foreground text-center mb-8">
                  Partagez vos dossiers et gagnez en productivité avec toute votre équipe.
                </p>

                <div className="mb-8 p-6 rounded-xl bg-muted/50 border border-border space-y-4">
                  <h3 className="font-heading font-semibold text-foreground">Comment ça marche :</h3>
                  {[
                    { icon: Link2, text: "Invitez vos collaborateurs" },
                    { icon: Users, text: "Ils rejoignent votre espace" },
                    { icon: FolderOpen, text: "Partagez vos contextes" },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center space-x-3">
                      <item.icon className="h-5 w-5 text-primary" />
                      <span className="text-sm text-foreground">{item.text}</span>
                    </div>
                  ))}
                </div>

                <div className="space-y-2 mb-8">
                  <label className="text-sm font-medium text-foreground">Inviter des collaborateurs</label>
                  <textarea
                    value={teamEmails}
                    onChange={(e) => setTeamEmails(e.target.value)}
                    placeholder="anna@entreprise.com, marc@entreprise.com"
                    className="w-full rounded-xl bg-muted border border-border px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none h-20 focus:outline-none focus:border-accent"
                  />
                </div>

                <ContinueButton
                  onClick={next}
                  label={teamEmails.trim() ? "Inviter et terminer" : "Passer cette étape"}
                />
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
};

export default OnboardingV2;
