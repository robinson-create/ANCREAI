import { motion } from "framer-motion";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import heroBg from "@/assets/fond_rob.jpg";

const Hero = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  const handleStartClick = () => {
    // Stocker la query pour l'onboarding
    if (searchQuery.trim()) {
      sessionStorage.setItem("ancre_initial_query", searchQuery);
    }
    navigate("/onboarding");
  };

  return (
    <section className="relative min-h-screen md:min-h-[700px] flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 z-0 -top-4">
        <img src={heroBg} alt="Hero background" className="w-full h-full min-h-screen object-cover" />
        <div className="hero-overlay absolute inset-0" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-20 md:py-32 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="font-heading font-bold text-4xl sm:text-5xl md:text-6xl lg:text-7xl text-white mb-6"
        >
          La plateforme qui libère <span className="text-cyan-glow">25 %</span> de votre temps quotidien
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-lg sm:text-xl text-white/90 mb-10 max-w-3xl mx-auto"
        >
          Recherche intelligente, rédaction automatisée, gestion des calendriers – le tout 100 % souverain et conçu pour les dirigeants.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12"
        >
          <Button size="lg" onClick={handleStartClick} className="w-full sm:w-auto">
            Essai gratuit 10 jours
          </Button>
          <Link to="/pricing" className="w-full sm:w-auto">
            <Button size="lg" variant="outline" className="w-full bg-white/10 backdrop-blur-sm border-white/20 text-white hover:bg-white/20">
              Voir les tarifs
            </Button>
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="max-w-3xl mx-auto"
        >
          <div className="bg-ocean-deep/80 backdrop-blur-xl rounded-2xl p-6 md:p-8 space-y-4 border border-white/10 shadow-2xl">
            <h3 className="font-heading font-semibold text-xl md:text-2xl text-white">
              Que souhaitez-vous faire ?
            </h3>
            <p className="text-sm text-white/70">
              Décrivez votre besoin ci-dessous ou choisissez une action rapide.
            </p>

            <div className="relative">
              <textarea
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ex : Rédige un email de relance pour le client TechCo concernant le devis en attente…"
                className="w-full rounded-xl bg-white/15 border border-white/20 px-4 py-3 text-white placeholder:text-white/60 focus:outline-none focus:border-cyan-glow focus:ring-2 focus:ring-cyan-glow/20 resize-none h-24"
              />
            </div>

            <div className="flex flex-wrap gap-2 justify-center">
              {["Rédiger un document", "Composer un email", "Rechercher une info"].map((label) => (
                <button
                  key={label}
                  onClick={() => setSearchQuery(label)}
                  className="px-4 py-2 rounded-lg bg-white/15 backdrop-blur-sm border border-white/25 text-sm font-medium text-white/90 hover:bg-white/20 transition-colors"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
