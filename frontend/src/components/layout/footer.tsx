import { Link } from "react-router-dom"
import { Anchor } from "lucide-react"

export function Footer() {
  return (
    <footer className="border-t bg-background">
      <div className="container py-8 md:py-12">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-4">
          {/* Brand */}
          <div className="space-y-4">
            <Link to="/" className="flex items-center space-x-2">
              <Anchor className="h-6 w-6 text-primary" />
              <span className="font-bold">Ancre</span>
            </Link>
            <p className="text-sm text-muted-foreground">
              Créez et personnalisez vos assistants IA en quelques clics.
            </p>
          </div>

          {/* Product */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold">Produit</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>
                <Link to="/" className="hover:text-foreground">
                  Fonctionnalités
                </Link>
              </li>
              <li>
                <Link to="/pricing" className="hover:text-foreground">
                  Tarifs
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold">Légal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>
                <Link to="/cgv" className="hover:text-foreground">
                  CGV
                </Link>
              </li>
              <li>
                <Link to="/cgv" className="hover:text-foreground">
                  Politique de confidentialité
                </Link>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold">Contact</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>
                <a
                  href="mailto:contact@mecano-man.com"
                  className="hover:text-foreground"
                >
                  contact@mecano-man.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 border-t pt-8 text-center text-sm text-muted-foreground">
          <p>
            &copy; {new Date().getFullYear()} Ancre. Tous droits réservés.
          </p>
        </div>
      </div>
    </footer>
  )
}
