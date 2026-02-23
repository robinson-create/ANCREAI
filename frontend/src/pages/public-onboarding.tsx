import { SignUp } from "@clerk/clerk-react";
import { motion } from "framer-motion";
import { Sparkles, Shield, Zap } from "lucide-react";

const PublicOnboarding = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 flex items-center justify-center p-4">
      <div className="w-full max-w-6xl grid md:grid-cols-2 gap-8 items-center">
        {/* Left side - Marketing content */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="hidden md:block space-y-8"
        >
          <div>
            <h1 className="font-heading font-bold text-4xl lg:text-5xl text-foreground mb-4">
              Bienvenue sur <span className="text-primary">Ancre</span>
            </h1>
            <p className="text-lg text-muted-foreground">
              La plateforme qui libère 25% de votre temps quotidien
            </p>
          </div>

          <div className="space-y-6">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Sparkles className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-heading font-semibold text-lg text-foreground mb-1">
                  IA française souveraine
                </h3>
                <p className="text-muted-foreground">
                  Propulsé par Mistral AI, vos données restent en France
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-heading font-semibold text-lg text-foreground mb-1">
                  Sécurité & confidentialité
                </h3>
                <p className="text-muted-foreground">
                  Conforme RGPD, hébergement européen, chiffrement de bout en bout
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <Zap className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-heading font-semibold text-lg text-foreground mb-1">
                  Prêt en 2 minutes
                </h3>
                <p className="text-muted-foreground">
                  Créez votre compte et découvrez immédiatement la puissance d'Ancre
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Right side - Clerk SignUp */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="flex justify-center"
        >
          <div className="w-full max-w-md">
            <SignUp
              routing="path"
              path="/onboarding"
              signInUrl="/login"
              afterSignUpUrl="/app/onboarding"
              appearance={{
                elements: {
                  rootBox: "w-full",
                  card: "bg-card/90 backdrop-blur-xl border border-border/30 shadow-2xl rounded-2xl",
                  headerTitle: "font-heading font-bold text-2xl",
                  headerSubtitle: "text-muted-foreground",
                  formButtonPrimary: "bg-foreground hover:bg-foreground/90 rounded-xl",
                  formFieldInput: "rounded-xl border-border focus:border-primary",
                  footerActionLink: "text-primary hover:text-primary/80",
                  dividerLine: "bg-border",
                  dividerText: "text-muted-foreground",
                  socialButtonsBlockButton: "border-border rounded-xl hover:bg-muted",
                  socialButtonsBlockButtonText: "font-medium",
                  identityPreviewEditButton: "text-primary",
                },
              }}
            />
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default PublicOnboarding;
