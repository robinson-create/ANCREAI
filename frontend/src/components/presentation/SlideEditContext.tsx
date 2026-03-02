/**
 * SlideEditContext — provides edit capabilities to slide templates.
 *
 * Templates are pure render components that only receive `data`. This context
 * lets them trigger image uploads and text edits without prop drilling.
 */
import { createContext, useContext } from "react"

export interface SlideEditContextValue {
  /** Upload an image for a field in the slide's content_json.
   *  fieldPath examples: "image", "backgroundImage", "teamMembers.0.image"
   */
  onImageUpload: (fieldPath: string, file: File) => Promise<void>
  /** Update a text field in the slide's content_json.
   *  fieldPath examples: "title", "description", "bulletPoints.0.title"
   */
  onFieldUpdate: (fieldPath: string, value: string) => void
  /** Whether the slide is in edit mode (show upload affordances, editable text). */
  isEditable: boolean
}

const SlideEditContext = createContext<SlideEditContextValue | null>(null)

export function SlideEditProvider({
  children,
  value,
}: {
  children: React.ReactNode
  value: SlideEditContextValue
}) {
  return (
    <SlideEditContext.Provider value={value}>
      {children}
    </SlideEditContext.Provider>
  )
}

export function useSlideEdit(): SlideEditContextValue | null {
  return useContext(SlideEditContext)
}
