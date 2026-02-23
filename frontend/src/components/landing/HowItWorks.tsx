import { motion } from "framer-motion";
import { Link2, Settings, Zap } from "lucide-react";

const steps = [
  {
    icon: Link2,
    num: "01",
    title: "Connectez vos outils",
    points: [
      "Importez vos documents (glisser-déposer depuis votre Drive, SharePoint, etc.).",
      "Liez votre boîte mail et votre calendrier (Gmail, Outlook, etc.).",
      "Activez les connecteurs (CRM, ERP, Notion, outils de mailing).",
    ],
  },
  {
    icon: Settings,
    num: "02",
    title: "Personnalisez votre espace",
    points: [
      "Définissez vos modèles de mails et documents (devis, contrats, relances).",
      "Activez la dictée vocale pour rédiger plus vite.",
      "Paramétrez vos rappels et notifications.",
    ],
  },
  {
    icon: Zap,
    num: "03",
    title: "Utilisez Ancre au quotidien",
    points: [
      "Recherchez une information en langage naturel.",
      "Générez un mail en 1 clic, avec toutes les données à jour.",
      "Consultez votre planning et laissez Ancre gérer les invitations.",
    ],
  },
];

const HowItWorks = () => (
  <section id="comment" className="py-20 bg-muted/30">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <motion.h2
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center font-heading font-bold text-3xl md:text-4xl lg:text-5xl text-foreground mb-4"
      >
        Comment ça marche ?
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.1 }}
        className="text-center text-lg text-muted-foreground mb-12"
      >
        Votre assistant opérationnel en 3 étapes
      </motion.p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {steps.map((s, i) => (
          <motion.div
            key={s.num}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.15 }}
            className="relative"
          >
            <div className="glass rounded-2xl p-8 h-full">
              <div className="flex items-center space-x-4 mb-6">
                <div className="text-5xl font-heading font-bold text-primary/20">{s.num}</div>
                <div className="p-3 rounded-xl bg-primary/10">
                  <s.icon className="h-6 w-6 text-primary" />
                </div>
              </div>

              <h3 className="font-heading font-semibold text-xl text-foreground mb-4">{s.title}</h3>

              <ul className="space-y-3">
                {s.points.map((p, j) => (
                  <li key={j} className="flex items-start space-x-2 text-sm text-muted-foreground">
                    <span className="text-primary mt-1">•</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

export default HowItWorks;
