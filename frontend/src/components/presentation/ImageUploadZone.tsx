/**
 * ImageUploadZone — clickable image area for slide templates.
 *
 * Shows the image when available, or a placeholder with upload affordance.
 * Uses SlideEditContext to trigger the upload flow.
 */
import { useRef, useState } from "react"
import { ImagePlus, Loader2 } from "lucide-react"
import { useSlideEdit } from "./SlideEditContext"

interface ImageUploadZoneProps {
  /** Current image URL (from __image_url__ in content_json). */
  imageUrl?: string
  /** Field path in content_json, e.g. "image" or "teamMembers.0.image". */
  fieldPath: string
  /** Additional CSS classes for the container. */
  className?: string
  /** Placeholder text when no image. */
  placeholder?: string
  /** Whether to show as circular (for avatars). */
  circular?: boolean
  /** Children to render instead of default placeholder (when no image). */
  children?: React.ReactNode
}

export default function ImageUploadZone({
  imageUrl,
  fieldPath,
  className = "",
  placeholder = "Image",
  circular = false,
  children,
}: ImageUploadZoneProps) {
  const ctx = useSlideEdit()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const isEditable = ctx?.isEditable ?? false

  const handleClick = () => {
    if (!isEditable || uploading) return
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !ctx) return

    setUploading(true)
    try {
      await ctx.onImageUpload(fieldPath, file)
    } finally {
      setUploading(false)
      // Reset input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const roundedClass = circular ? "rounded-full" : "rounded-lg"

  // Image present — show it with optional replace overlay on hover
  if (imageUrl) {
    return (
      <div
        className={`relative overflow-hidden group ${roundedClass} ${className}`}
        onClick={handleClick}
        style={{ cursor: isEditable ? "pointer" : "default" }}
      >
        <img
          src={imageUrl}
          alt=""
          className={`w-full h-full object-cover ${roundedClass}`}
        />
        {isEditable && (
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            {uploading ? (
              <Loader2 className="w-6 h-6 text-white animate-spin" />
            ) : (
              <ImagePlus className="w-6 h-6 text-white" />
            )}
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>
    )
  }

  // No image — show placeholder with upload affordance
  return (
    <div
      className={`relative overflow-hidden flex flex-col items-center justify-center gap-1.5 ${roundedClass} ${className}`}
      onClick={handleClick}
      style={{
        cursor: isEditable ? "pointer" : "default",
        backgroundColor: "var(--card-color, #F8F7F6)",
        border: "1px dashed var(--stroke, #E5E7EB)",
      }}
    >
      {uploading ? (
        <Loader2 className="w-5 h-5 opacity-40 animate-spin" />
      ) : children ? (
        children
      ) : (
        <>
          <ImagePlus
            className="w-5 h-5 opacity-30"
            style={{ color: "var(--background-text, #323F50)" }}
          />
          <span className="text-xs opacity-30">{placeholder}</span>
        </>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  )
}
