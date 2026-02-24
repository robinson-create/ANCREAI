import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail, Link2, FileText, CheckCircle2 } from "lucide-react";
import { onboardingApi } from "@/api/onboarding";

interface SetupState {
  firstName?: string;
  lastName?: string;
  company?: string;
  role?: string;
  teamEmails?: string;
  initialQuery?: string;
}

const setupSteps = [
  {
    id: "email",
    title: "Connecter votre email",
    description: "Gmail, Outlook, ou autre",
    icon: Mail,
    action: "Configurer",
    route: "/app/profile", // Redirige vers la page de profile où les intégrations sont gérées
  },
  {
    id: "connectors",
    title: "Connecter vos outils",
    description: "Drive, SharePoint, CRM, ERP",
    icon: Link2,
    action: "Configurer",
    route: "/app/profile",
  },
  {
    id: "documents",
    title: "Importer vos documents",
    description: "Glissez-déposez vos fichiers",
    icon: FileText,
    action: "Importer",
    route: "/app/documents",
  },
];

const OnboardingSetup = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const state = (location.state || {}) as SetupState;
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  const handleStepClick = (step: typeof setupSteps[0]) => {
    // Marquer comme complété
    if (!completedSteps.includes(step.id)) {
      setCompletedSteps([...completedSteps, step.id]);
    }
    // Rediriger vers la page appropriée
    navigate(step.route);
  };

  const handleFinish = async () => {
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

  const handleSkip = async () => {
    await handleFinish();
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-3xl"
      >
        <Card className="shadow-xl">
          <CardHeader className="text-center space-y-2">
            <CardTitle className="text-3xl font-heading">Configuration optionnelle</CardTitle>
            <CardDescription className="text-base">
              Configurez vos intégrations pour tirer le maximum d'Ancre
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="space-y-3">
              {setupSteps.map((step, i) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.1 }}
                >
                  <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => handleStepClick(step)}>
                    <CardContent className="flex items-center justify-between p-6">
                      <div className="flex items-center space-x-4">
                        <div className={`p-3 rounded-xl ${completedSteps.includes(step.id) ? "bg-success/10" : "bg-primary/10"}`}>
                          {completedSteps.includes(step.id) ? (
                            <CheckCircle2 className="h-6 w-6 text-success" />
                          ) : (
                            <step.icon className="h-6 w-6 text-primary" />
                          )}
                        </div>
                        <div>
                          <h3 className="font-heading font-semibold text-foreground">{step.title}</h3>
                          <p className="text-sm text-muted-foreground">{step.description}</p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm">
                        {step.action}
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>

            <div className="pt-6 border-t border-border">
              <p className="text-sm text-muted-foreground text-center mb-6">
                Vous pourrez toujours configurer ces options plus tard depuis les paramètres
              </p>

              <div className="flex flex-col sm:flex-row gap-3">
                <Button variant="outline" onClick={handleSkip} className="flex-1">
                  Passer pour l'instant
                </Button>
                <Button onClick={handleFinish} className="flex-1">
                  Terminer la configuration
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

export default OnboardingSetup;
