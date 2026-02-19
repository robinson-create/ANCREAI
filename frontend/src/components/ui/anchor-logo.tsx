import { Anchor } from "lucide-react"
import { cn } from "@/lib/utils"
import ancreLogo from "@/assets/ancre-logo.png"

interface AnchorLogoProps {
  streaming?: boolean
  size?: "sm" | "md" | "lg"
  className?: string
}

const sizeClasses = {
  sm: "h-6 w-6",
  md: "h-8 w-8",
  lg: "h-10 w-10",
}

const iconSizes = {
  sm: "h-3.5 w-3.5",
  md: "h-4 w-4",
  lg: "h-5 w-5",
}

export function AnchorLogo({
  streaming = false,
  size = "md",
  className,
}: AnchorLogoProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden shrink-0",
        sizeClasses[size],
        streaming ? "anchor-streaming rounded-lg border border-border bg-card" : "",
        className
      )}
      aria-label="Ancre"
    >
      {/* Sheen overlay during streaming */}
      {streaming && <div className="absolute inset-0 anchor-sheen" />}

      {/* Logo image (or fallback icon during streaming) */}
      <div className="relative grid h-full w-full place-items-center">
        {streaming ? (
          <Anchor className={cn(iconSizes[size], "text-primary")} />
        ) : (
          <img
            src={ancreLogo}
            alt="Ancre"
            className="h-full w-full object-contain"
          />
        )}
      </div>

      {/* Blue dot indicator during streaming */}
      {streaming && (
        <span className="absolute bottom-0.5 right-0.5 h-1.5 w-1.5 rounded-full bg-primary" />
      )}
    </div>
  )
}
