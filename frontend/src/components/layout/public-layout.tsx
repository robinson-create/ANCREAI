import { Outlet, useLocation } from "react-router-dom"
import { Header } from "./header"
import { Footer } from "./footer"

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
