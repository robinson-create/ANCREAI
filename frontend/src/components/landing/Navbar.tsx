import { Link } from "react-router-dom";
import anchorLogo from "@/assets/ancre-logo.png";
import { Button } from "@/components/ui/button";

const Navbar = () => {

  return (
    <nav className="fixed top-2 md:top-3 left-1/2 -translate-x-1/2 z-50 w-[96%] md:w-[95%] max-w-4xl">
      <div className="bg-card/90 backdrop-blur-xl border border-border/30 shadow-lg rounded-full px-4 md:px-5 py-2.5 md:py-3">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-1.5 md:space-x-2">
            <img src={anchorLogo} alt="Ancre" className="h-6 md:h-7 w-6 md:w-7" />
            <span className="font-heading font-bold text-sm md:text-base text-foreground">Ancre</span>
          </Link>

          <div className="flex items-center space-x-2 md:space-x-4">
            <Link to="/login" className="text-xs md:text-sm font-medium text-foreground/70 hover:text-foreground transition-colors">
              Connexion
            </Link>
            <Link to="/onboarding">
              <Button size="sm" className="bg-foreground hover:bg-foreground/90 text-white rounded-full px-3 md:px-5 text-xs md:text-sm h-8 md:h-9">
                Essai gratuit
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
