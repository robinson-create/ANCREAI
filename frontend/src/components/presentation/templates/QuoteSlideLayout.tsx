/**
 * QuoteSlideLayout - Quote/testimonial.
 *
 * Fields: heading, quote, author, backgroundImage
 */
import ImageUploadZone from "../ImageUploadZone";
import EditableText from "../EditableText";

interface QuoteSlideData {
  heading?: string;
  quote?: string;
  author?: string;
  backgroundImage?: { __image_url__?: string };
}

export default function QuoteSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as QuoteSlideData;
  const hasBgImage = !!d.backgroundImage?.__image_url__;

  return (
    <div
      className="relative w-full h-full overflow-hidden"
      style={{
        backgroundColor: hasBgImage
          ? "#000000"
          : "var(--primary-color, #323F50)",
      }}
    >
      {/* Background image */}
      {hasBgImage ? (
        <>
          <ImageUploadZone
            imageUrl={d.backgroundImage!.__image_url__}
            fieldPath="backgroundImage"
            className="absolute inset-0 w-full h-full opacity-40"
          />
          <div className="absolute inset-0 bg-black/50 pointer-events-none" />
        </>
      ) : (
        <ImageUploadZone
          fieldPath="backgroundImage"
          className="absolute inset-0 w-full h-full"
          placeholder="Image de fond"
        />
      )}

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center justify-center h-full px-14 py-8 text-center">
        <EditableText
          value={d.heading}
          fieldPath="heading"
          as="p"
          className="text-sm font-semibold uppercase tracking-widest mb-6 opacity-80"
          style={{ color: "var(--primary-text, #FFFFFF)" }}
          placeholder="En-tête"
        />

        <div
          className="text-4xl font-serif leading-none mb-3 opacity-50"
          style={{ color: "var(--primary-text, #FFFFFF)" }}
        >
          &ldquo;
        </div>

        <EditableText
          value={d.quote}
          fieldPath="quote"
          as="p"
          className="text-xl font-medium leading-relaxed max-w-2xl italic"
          style={{
            color: "var(--primary-text, #FFFFFF)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Citation"
        />

        <div
          className="text-4xl font-serif leading-none mt-3 opacity-50"
          style={{ color: "var(--primary-text, #FFFFFF)" }}
        >
          &rdquo;
        </div>

        <div className="mt-6 flex items-center gap-2">
          <div
            className="w-6 h-px"
            style={{ backgroundColor: "var(--primary-text, #FFFFFF)", opacity: 0.5 }}
          />
          <EditableText
            value={d.author}
            fieldPath="author"
            as="p"
            className="text-sm font-medium opacity-80"
            style={{ color: "var(--primary-text, #FFFFFF)" }}
            placeholder="Auteur"
          />
        </div>
      </div>
    </div>
  );
}
