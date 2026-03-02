/**
 * IntroSlideLayout - Title/cover slide template.
 *
 * Fields: title, description, presenterName, presentationDate, image
 * Large centered title, description below, presenter info at bottom, image on right side.
 */
import ImageUploadZone from "../ImageUploadZone";
import EditableText from "../EditableText";

interface IntroSlideData {
  title?: string;
  description?: string;
  presenterName?: string;
  presentationDate?: string;
  image?: { __image_url__?: string };
}

export default function IntroSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as IntroSlideData;

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      {/* Left content area */}
      <div className="flex flex-col justify-center flex-1 px-14 py-8">
        {/* Accent line */}
        <div
          className="w-12 h-1 mb-6 rounded-full"
          style={{ backgroundColor: "var(--primary-color, #323F50)" }}
        />

        {/* Title */}
        <EditableText
          value={d.title}
          fieldPath="title"
          as="h1"
          className="text-4xl font-bold leading-tight tracking-tight mb-4"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        {/* Description */}
        <EditableText
          value={d.description}
          fieldPath="description"
          as="p"
          className="text-lg leading-relaxed mb-8 max-w-md opacity-80"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />

        {/* Presenter info */}
        <div className="mt-auto">
          <EditableText
            value={d.presenterName}
            fieldPath="presenterName"
            as="p"
            className="text-base font-semibold"
            style={{ color: "var(--primary-color, #323F50)" }}
            placeholder="Présentateur"
          />
          <EditableText
            value={d.presentationDate}
            fieldPath="presentationDate"
            as="p"
            className="text-sm opacity-60 mt-1"
            style={{ color: "var(--background-text, #323F50)" }}
            placeholder="Date"
          />
        </div>
      </div>

      {/* Right image area */}
      <ImageUploadZone
        imageUrl={d.image?.__image_url__}
        fieldPath="image"
        className="w-2/5"
      />

      {/* Bottom accent bar */}
      <div
        className="absolute bottom-0 left-0 right-0 h-1"
        style={{
          background: `linear-gradient(90deg, var(--primary-color, #323F50) 0%, var(--card-color, #F8F7F6) 100%)`,
        }}
      />
    </div>
  );
}
