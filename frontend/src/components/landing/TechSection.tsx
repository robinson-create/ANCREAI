import { motion } from "framer-motion";
import { Layout, Cpu, CreditCard } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const techs = [
  {
    icon: Layout,
    title: "Interface intuitive",
    points: ["Tableau de bord clair et ergonomique.", "Recherche ultra-rapide en < 2 secondes."],
  },
  {
    icon: Cpu,
    title: "Technologie RAG avancée",
    points: ["Réponses basées uniquement sur vos documents.", "Données toujours à jour et vérifiées."],
  },
  {
    icon: CreditCard,
    title: "Tarifs transparents",
    points: ["Offres de 1 à 100+ utilisateurs.", "Essai gratuit 10 jours sans carte.", "Abonnements flexibles."],
  },
];

const TechSection = () => (
  <section id="technologie" className="py-20 bg-background">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <motion.h2
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center font-heading font-bold text-3xl md:text-4xl lg:text-5xl text-foreground mb-12"
      >
        Une technologie puissante, simple et souveraine
      </motion.h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {techs.map((t, i) => (
          <motion.div
            key={t.title}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
          >
            <Card className="h-full hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="p-3 rounded-xl bg-accent/10 w-fit mb-4">
                  <t.icon className="h-6 w-6 text-accent" />
                </div>
                <CardTitle className="text-xl font-heading">{t.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {t.points.map((p, j) => (
                    <li key={j} className="text-sm text-muted-foreground">
                      {p}
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

export default TechSection;
