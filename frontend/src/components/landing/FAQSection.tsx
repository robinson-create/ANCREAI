import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "Quels outils puis-je connecter à Ancre ?",
    a: "Gmail, Outlook, Drive, SharePoint, Dropbox, Pipedrive, HubSpot, Odoo, Notion, Google Calendar, Outlook Calendar et bien d'autres grâce à nos connecteurs natifs.",
  },
  {
    q: "Mes données sont-elles sécurisées ?",
    a: "Oui, absolument. Nous utilisons l'IA française Mistral AI, un hébergement en France et en Europe conforme RGPD, et des accès contrôlés par utilisateur.",
  },
  {
    q: "Puis-je tester Ancre gratuitement ?",
    a: "Oui, vous bénéficiez d'un essai gratuit de 10 jours, sans carte bancaire requise.",
  },
  {
    q: "Comment fonctionne la tarification ?",
    a: "Nous proposons des offres flexibles de 1 à 100+ utilisateurs. Consultez notre page tarifs pour plus de détails.",
  },
];

const FAQSection = () => {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section id="faq" className="py-20 bg-background">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center font-heading font-bold text-3xl md:text-4xl text-foreground mb-12"
        >
          FAQ
        </motion.h2>

        <div className="space-y-4">
          {faqs.map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="glass rounded-xl overflow-hidden"
            >
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between p-5 text-left hover:bg-muted/50 transition-colors"
              >
                <span className="font-heading font-semibold text-foreground">{f.q}</span>
                <ChevronDown
                  className={`h-5 w-5 text-muted-foreground transition-transform ${
                    open === i ? "transform rotate-180" : ""
                  }`}
                />
              </button>

              <AnimatePresence>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-hidden"
                  >
                    <div className="px-5 pb-5 text-muted-foreground">{f.a}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FAQSection;
