import { motion } from "framer-motion";
import { Search, Mail, Calendar, Shield } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const benefits = [
  {
    icon: Search,
    title: "Centralisez vos informations en un clic",
    points: [
      "Recherche instantanée dans tous vos documents (contrats, procédures, emails, fiches clients).",
      "Connecteurs natifs avec Drive, SharePoint, CRM (Pipedrive, HubSpot), ERP (Odoo), Notion, etc.",
      "Accès unifié : plus besoin de switcher entre outils pour trouver une information.",
    ],
  },
  {
    icon: Mail,
    title: "Rédigez mails et documents 3x plus vite",
    points: [
      "Génération automatique de mails (relances, confirmations, réponses) en 1 clic.",
      "Modèles intelligents pour devis, contrats et comptes-rendus, pré-remplis avec vos données.",
      "Dictée vocale intégrée : rédigez en parlant, sans saisie manuelle.",
    ],
  },
  {
    icon: Calendar,
    title: "Gérez vos calendriers sans effort",
    points: [
      "Planification intelligente avec Google Calendar, Outlook.",
      "Rappels et relances automatiques.",
      "Vue d'ensemble sur vos plannings.",
    ],
  },
  {
    icon: Shield,
    title: "100 % souverain et sécurisé",
    points: [
      "IA française Mistral AI.",
      "Hébergement France/UE, conforme RGPD.",
      "Accès contrôlés par utilisateur.",
    ],
  },
];

const BenefitsSection = () => (
  <section id="pourquoi" className="py-20 bg-background">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <motion.h2
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center font-heading font-bold text-3xl md:text-4xl lg:text-5xl text-foreground mb-12"
      >
        Pourquoi <span className="text-gradient">Ancre</span> ?
      </motion.h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {benefits.map((b, i) => (
          <motion.div
            key={b.title}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
          >
            <Card className="h-full hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-center space-x-4 mb-4">
                  <div className="p-3 rounded-xl bg-primary/10">
                    <b.icon className="h-6 w-6 text-primary" />
                  </div>
                </div>
                <CardTitle className="text-xl font-heading">{b.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {b.points.map((p, j) => (
                    <li key={j} className="flex items-start space-x-2 text-sm text-muted-foreground">
                      <span className="text-primary mt-1">•</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

export default BenefitsSection;
