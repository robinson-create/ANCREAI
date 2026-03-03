/**
 * StaticImage — pure render image component for slide templates.
 *
 * Unlike ImageUploadZone (frontend), this component has zero interactivity:
 * no file input, no upload, no hover overlay. Safe for SSR.
 */

interface StaticImageProps {
  imageUrl?: string;
  className?: string;
  placeholder?: string;
  circular?: boolean;
  children?: React.ReactNode;
}

export default function StaticImage({
  imageUrl,
  className = "",
  placeholder = "Image",
  circular = false,
  children,
}: StaticImageProps) {
  const roundedClass = circular ? "rounded-full" : "rounded-lg";

  if (imageUrl) {
    return (
      <div className={`relative overflow-hidden ${roundedClass} ${className}`}>
        <img
          src={imageUrl}
          alt=""
          className={`w-full h-full object-cover ${roundedClass}`}
        />
      </div>
    );
  }

  return (
    <div
      className={`relative overflow-hidden flex flex-col items-center justify-center gap-1.5 ${roundedClass} ${className}`}
      style={{
        backgroundColor: "var(--card-color, #F8F7F6)",
        border: "1px dashed var(--stroke, #E5E7EB)",
      }}
    >
      {children ? (
        children
      ) : (
        <span className="text-xs opacity-30">{placeholder}</span>
      )}
    </div>
  );
}
