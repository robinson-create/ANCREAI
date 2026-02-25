import { Loader2 } from "lucide-react"
import { Progress } from "@/components/ui/progress"

interface GenerationProgressProps {
  message: string
  progress?: number
  slideCount?: { current: number; total: number }
}

export function GenerationProgress({
  message,
  progress,
  slideCount,
}: GenerationProgressProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-4">
      <Loader2 className="h-10 w-10 animate-spin text-primary" />
      <p className="text-lg font-medium text-foreground">{message}</p>

      {slideCount && (
        <div className="w-full max-w-sm space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Slide {slideCount.current} / {slideCount.total}</span>
            <span>{Math.round((slideCount.current / slideCount.total) * 100)}%</span>
          </div>
          <Progress value={(slideCount.current / slideCount.total) * 100} />
        </div>
      )}

      {progress !== undefined && !slideCount && (
        <div className="w-full max-w-sm space-y-2">
          <Progress value={progress} />
          <p className="text-sm text-muted-foreground text-center">{Math.round(progress)}%</p>
        </div>
      )}
    </div>
  )
}
