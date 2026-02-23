import anchorLogo from "@/assets/ancre-logo.png";

const Footer = () => (
  <footer className="bg-ocean-deep text-white py-12">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col items-center space-y-4">
        <div className="flex items-center space-x-2">
          <img src={anchorLogo} alt="Ancre" className="h-8 w-8 invert" />
          <span className="font-heading font-bold text-xl">Ancre</span>
        </div>

        <p className="text-sm text-white/70 text-center">
          Une question ? Écrivez-nous à <a href="mailto:contact@ancreai.eu" className="text-accent hover:underline">contact@ancreai.eu</a>
        </p>

        <p className="text-xs text-white/50">
          © {new Date().getFullYear()} Ancre AI. Tous droits réservés.
        </p>
      </div>
    </div>
  </footer>
);

export default Footer;
