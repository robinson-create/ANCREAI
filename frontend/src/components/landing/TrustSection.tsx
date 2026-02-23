import { motion } from "framer-motion";

const logos = ["Pivert Funéraire", "Hey Dom", "RI Direct"];

const TrustSection = () => (
  <section className="py-12 bg-muted/30">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <motion.h3
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center text-sm font-medium text-muted-foreground mb-8"
      >
        Ils nous font confiance
      </motion.h3>

      <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12">
        {logos.map((name, i) => (
          <motion.div
            key={name}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
            className="flex items-center justify-center"
          >
            <span className="text-xl font-heading font-semibold text-foreground/60">{name}</span>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

export default TrustSection;
