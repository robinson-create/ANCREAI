import { Anchor } from "lucide-react"
import { cn } from "@/lib/utils"

interface AnchorLogoProps {
  streaming?: boolean
  size?: "sm" | "md" | "lg"
  className?: string
}

const sizeClasses = {
  sm: "h-7 w-7 rounded-md",
  md: "h-9 w-9 rounded-lg",
  lg: "h-12 w-12 rounded-lg",
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
        "relative border border-border bg-card overflow-hidden shrink-0",
        sizeClasses[size],
        streaming ? "anchor-streaming" : "",
        className
      )}
      aria-label="Ancre"
    >
      {/* Sheen overlay during streaming */}
      {streaming && <div className="absolute inset-0 anchor-sheen" />}

      {/* Anchor icon */}
      <div className="relative grid h-full w-full place-items-center">
        <Anchor className={cn(iconSizes[size], "text-primary")} />
      </div>

      {/* Blue dot indicator during streaming */}
      {streaming && (
        <span className="absolute bottom-0.5 right-0.5 h-1.5 w-1.5 rounded-full bg-primary" />
      )}
    </div>
  )
}
