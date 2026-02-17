/**
 * AnchorSpinner — Large centered spinning anchor with physics-based inertia.
 *
 * Phases:
 *  1. Spin-up: accelerates from 0 to Vmax over ~1.5s (ease-in feel)
 *  2. Full speed: constant high RPM with motion blur effect
 *  3. Deceleration: when `active` turns false, friction slows to 0 with natural ease-out
 *
 * Uses requestAnimationFrame for smooth 60fps physics.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { Anchor } from "lucide-react"
import { cn } from "@/lib/utils"

interface AnchorSpinnerProps {
  /** Whether generation is in progress */
  active: boolean
  /** Called when the deceleration animation finishes (spinner has stopped) */
  onStopped?: () => void
  className?: string
}

// Physics constants
const TORQUE = 18          // deg/s² acceleration
const MAX_VELOCITY = 1800   // deg/s at full speed
const FRICTION = 4          // deg/s² deceleration (lower = longer coast)
const BLUR_THRESHOLD = 400  // velocity above which blur starts
const MAX_BLUR = 3          // max blur in px at full speed

export function AnchorSpinner({ active, onStopped, className }: AnchorSpinnerProps) {
  const angleRef = useRef(0)
  const velocityRef = useRef(0)
  const phaseRef = useRef<"idle" | "spinning_up" | "full_speed" | "decelerating">("idle")
  const rafRef = useRef<number>(0)
  const lastTimeRef = useRef<number>(0)
  const elementRef = useRef<HTMLDivElement>(null)
  const blurRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  const animate = useCallback((timestamp: number) => {
    if (!lastTimeRef.current) lastTimeRef.current = timestamp
    const dt = Math.min((timestamp - lastTimeRef.current) / 1000, 0.05) // cap dt to avoid jumps
    lastTimeRef.current = timestamp

    const phase = phaseRef.current
    let velocity = velocityRef.current

    // Physics update
    if (phase === "spinning_up") {
      velocity += TORQUE * 60 * dt // accelerate
      if (velocity >= MAX_VELOCITY) {
        velocity = MAX_VELOCITY
        phaseRef.current = "full_speed"
      }
    } else if (phase === "full_speed") {
      velocity = MAX_VELOCITY
    } else if (phase === "decelerating") {
      velocity -= FRICTION * 60 * dt // decelerate
      if (velocity <= 0) {
        velocity = 0
        phaseRef.current = "idle"
        onStopped?.()
        setVisible(false)
        return // stop the loop
      }
    }

    velocityRef.current = velocity
    angleRef.current = (angleRef.current + velocity * dt) % 360

    // Apply transform
    if (elementRef.current) {
      elementRef.current.style.transform = `rotate(${angleRef.current}deg)`
    }

    // Apply motion blur based on velocity
    if (blurRef.current) {
      const blurAmount =
        velocity > BLUR_THRESHOLD
          ? Math.min(((velocity - BLUR_THRESHOLD) / (MAX_VELOCITY - BLUR_THRESHOLD)) * MAX_BLUR, MAX_BLUR)
          : 0
      blurRef.current.style.filter = blurAmount > 0.1 ? `blur(${blurAmount}px)` : "none"
      // Also scale slightly at high speed for dramatic effect
      const scale = 1 + (velocity / MAX_VELOCITY) * 0.05
      blurRef.current.style.transform = `scale(${scale})`
    }

    rafRef.current = requestAnimationFrame(animate)
  }, [onStopped])

  // Start spinning when active becomes true
  useEffect(() => {
    if (active) {
      setVisible(true)
      phaseRef.current = "spinning_up"
      velocityRef.current = 0
      lastTimeRef.current = 0
      rafRef.current = requestAnimationFrame(animate)
    } else if (phaseRef.current === "spinning_up" || phaseRef.current === "full_speed") {
      // Begin deceleration
      phaseRef.current = "decelerating"
    }

    return () => {
      // Don't cancel if we're decelerating — let it finish
      if (phaseRef.current === "idle" && rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [active, animate])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  if (!visible) return null

  return (
    <div
      className={cn(
        "absolute inset-0 z-20 flex flex-col items-center justify-center bg-surface/80 backdrop-blur-sm animate-fade-in",
        className
      )}
    >
      {/* Spinning anchor container */}
      <div ref={blurRef} className="transition-transform">
        <div
          ref={elementRef}
          className="w-20 h-20 rounded-2xl bg-card border-2 border-primary/20 shadow-elevated flex items-center justify-center"
        >
          <Anchor className="h-9 w-9 text-primary" />
        </div>
      </div>

      {/* Label */}
      <p className="mt-6 text-sm font-medium text-muted-foreground animate-pulse">
        Generation en cours…
      </p>
    </div>
  )
}
