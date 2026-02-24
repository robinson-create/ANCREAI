import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { onboardingApi } from "@/api/onboarding";

interface TransitionState {
  firstName?: string;
  lastName?: string;
  company?: string;
  role?: string;
  teamEmails?: string;
  initialQuery?: string;
}

const OnboardingTransition = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const state = (location.state || {}) as TransitionState;

  useEffect(() => {
    // Si pas de state, rediriger vers l'onboarding
    if (!state.firstName) {
      navigate("/app/onboarding");
    }
  }, [state, navigate]);

  const handleSkip = async () => {
    try {
      // Marquer l'onboarding comme complété
      await onboardingApi.complete({
        first_name: state.firstName || "",
        last_name: state.lastName || "",
        company_name: state.company || "",
        memories: "",
        website_urls: [],
      });

      // Rediriger vers l'app
      navigate("/app/search");
    } catch (error) {
      console.error("Error completing onboarding:", error);
      // Rediriger quand même vers l'app
      navigate("/app/search");
    }
  };

  const handleConfigure = () => {
    // Rediriger vers le setup fonctionnel
    navigate("/app/onboarding/setup", { state });
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-2xl"
      >
        <Card className="shadow-xl">
          <CardHeader className="text-center space-y-2">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: "spring" }}
              className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4"
            >
              <svg
                className="w-8 h-8 text-primary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </motion.div>
            <CardTitle className="text-3xl font-heading">Félicitations, {state.firstName} !</CardTitle>
            <CardDescription className="text-base">
              Vous êtes prêt à utiliser Ancre. Souhaitez-vous configurer vos intégrations maintenant ?
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="p-6 rounded-xl bg-muted/50 border border-border space-y-4">
              <h3 className="font-heading font-semibold text-foreground">
                Configuration optionnelle
              </h3>
              <p className="text-sm text-muted-foreground">
                Pour tirer le maximum d'Ancre, connectez vos outils dès maintenant :
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-center space-x-2">
                  <span className="text-primary">•</span>
                  <span>Votre boîte mail (Gmail, Outlook)</span>
                </li>
                <li className="flex items-center space-x-2">
                  <span className="text-primary">•</span>
                  <span>Vos documents (Drive, SharePoint, Dropbox)</span>
                </li>
                <li className="flex items-center space-x-2">
                  <span className="text-primary">•</span>
                  <span>Vos outils métier (CRM, ERP, Notion)</span>
                </li>
              </ul>
              <p className="text-xs text-muted-foreground italic">
                Vous pourrez toujours le faire plus tard depuis les paramètres.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Button variant="outline" onClick={handleSkip} className="flex-1">
                Je le ferai plus tard
              </Button>
              <Button onClick={handleConfigure} className="flex-1">
                Configurer maintenant
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

export default OnboardingTransition;
