import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const items = [
  "Recherche documentaire en 2 clics.",
  "Rédaction 3x plus rapide.",
  "Calendriers synchronisés.",
  "100 % souverain – Mistral AI + France/UE.",
  "Conçu par des dirigeants, pour des dirigeants.",
];

const RecapSection = () => (
  <section className="py-20 bg-muted/30">
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
      <motion.h2
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-12"
      >
        Ce qu'il faut retenir
      </motion.h2>

      <div className="space-y-4 mb-12">
        {items.map((item, i) => (
          <motion.div
            key={item}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            className="flex items-start space-x-3 text-left max-w-2xl mx-auto"
          >
            <CheckCircle2 className="h-6 w-6 text-primary flex-shrink-0 mt-0.5" />
            <span className="text-lg text-foreground">{item}</span>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.5 }}
      >
        <h3 className="font-heading font-semibold text-2xl text-foreground mb-6">
          Prêt à gagner du temps ?
        </h3>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/onboarding">
            <Button size="lg">Commencer l'essai gratuit</Button>
          </Link>
          <Link to="/pricing">
            <Button size="lg" variant="outline">Voir les tarifs</Button>
          </Link>
        </div>
      </motion.div>
    </div>
  </section>
);

export default RecapSection;
