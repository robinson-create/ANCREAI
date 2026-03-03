/**
 * BasicInfoSlideLayout - Clean two-column layout.
 *
 * Fields: title, description, image
 */
import StaticImage from "../StaticImage.js";
import StaticText from "../StaticText.js";

interface BasicInfoSlideData {
  title?: string;
  description?: string;
  image?: { __image_url__?: string };
}

export default function BasicInfoSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as BasicInfoSlideData;

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <div className="flex flex-col justify-center flex-1 px-14 py-8">
        <div
          className="w-10 h-1 mb-5 rounded-full"
          style={{ backgroundColor: "var(--primary-color, #323F50)" }}
        />

        <StaticText
          value={d.title}
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-4"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <StaticText
          value={d.description}
          as="p"
          className="text-base leading-relaxed max-w-lg opacity-80"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />
      </div>

      <StaticImage
        imageUrl={d.image?.__image_url__}
        className="w-2/5 m-6"
      />
    </div>
  );
}
