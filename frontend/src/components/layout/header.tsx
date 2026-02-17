import { Link, useNavigate, useLocation } from "react-router-dom"
import { useAuth, useUser, useClerk } from "@clerk/clerk-react"
import {
  Anchor,
  LogOut,
  User,
  CreditCard,
  Bot,
  FolderOpen,
  FileEdit,
  Plug,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

const APP_NAV_ITEMS = [
  { to: "/app/assistants", label: "Assistants", icon: Bot },
  { to: "/app/collections", label: "Collections", icon: FolderOpen },
  { to: "/app/documents", label: "Documents", icon: FileEdit },
  { to: "/app/integrations", label: "Connecteurs", icon: Plug },
] as const

export function Header() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isSignedIn } = useAuth()
  const { user } = useUser()
  const { signOut } = useClerk()

  const isAppRoute = location.pathname.startsWith("/app")

  const handleLogout = async () => {
    await signOut()
    navigate("/")
  }

  const getInitials = (name: string | null | undefined) => {
    if (!name) return "?"
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo */}
        <Link to={isSignedIn ? "/app/assistants" : "/"} className="flex items-center space-x-2">
          <Anchor className="h-8 w-8 text-primary" />
          <span className="text-xl font-bold">Ancre</span>
        </Link>

        {/* App navigation (shown when signed in and on /app routes) */}
        {isSignedIn && isAppRoute ? (
          <nav className="hidden md:flex items-center space-x-1">
            {APP_NAV_ITEMS.map((item) => {
              const isActive =
                location.pathname === item.to ||
                location.pathname.startsWith(item.to + "/")
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        ) : (
          <nav className="hidden md:flex items-center space-x-6">
            <Link
              to="/"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Accueil
            </Link>
            <Link
              to="/pricing"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Tarifs
            </Link>
          </nav>
        )}

        {/* Auth area */}
        <div className="flex items-center space-x-4">
          {isSignedIn && user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="relative h-10 w-10 rounded-full"
                >
                  <Avatar className="h-10 w-10">
                    <AvatarImage src={user.imageUrl} alt={user.fullName || ""} />
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      {getInitials(user.fullName)}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" forceMount>
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-1">
                    <p className="text-sm font-medium leading-none">
                      {user.fullName}
                    </p>
                    <p className="text-xs leading-none text-muted-foreground">
                      {user.primaryEmailAddress?.emailAddress}
                    </p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/app/profile")}>
                  <User className="mr-2 h-4 w-4" />
                  <span>Mon profil</span>
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate("/app/billing")}>
                  <CreditCard className="mr-2 h-4 w-4" />
                  <span>Facturation</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>Déconnexion</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link to="/login">Se connecter</Link>
              </Button>
              <Button asChild>
                <Link to="/signup">Créer un compte</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
