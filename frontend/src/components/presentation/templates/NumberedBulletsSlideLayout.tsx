/**
 * NumberedBulletsSlideLayout - Numbered list.
 *
 * Fields: title, image, bulletPoints[]{title, description}
 */
import ImageUploadZone from "../ImageUploadZone";
import EditableText from "../EditableText";

interface BulletPoint {
  title?: string;
  description?: string;
}

interface NumberedBulletsSlideData {
  title?: string;
  image?: { __image_url__?: string };
  bulletPoints?: BulletPoint[];
}

export default function NumberedBulletsSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as NumberedBulletsSlideData;
  const bullets = d.bulletPoints ?? [];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <div className="flex flex-col justify-center px-14 py-8 flex-1">
        <EditableText
          value={d.title}
          fieldPath="title"
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-6"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <div className="flex flex-col gap-4">
          {bullets.map((bullet, i) => (
            <div key={i} className="flex items-start gap-4">
              <div
                className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0 text-sm font-bold"
                style={{
                  backgroundColor: "var(--primary-color, #323F50)",
                  color: "var(--primary-text, #FFFFFF)",
                }}
              >
                {String(i + 1).padStart(2, "0")}
              </div>

              <div className="flex-1 min-w-0 pt-0.5">
                <EditableText
                  value={bullet.title}
                  fieldPath={`bulletPoints.${i}.title`}
                  as="p"
                  className="text-sm font-semibold leading-snug mb-0.5"
                  style={{ color: "var(--primary-color, #323F50)" }}
                />
                <EditableText
                  value={bullet.description}
                  fieldPath={`bulletPoints.${i}.description`}
                  as="p"
                  className="text-xs leading-relaxed opacity-70 line-clamp-2"
                  style={{ color: "var(--background-text, #323F50)" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <ImageUploadZone
        imageUrl={d.image?.__image_url__}
        fieldPath="image"
        className="w-1/3 m-6"
      />
    </div>
  );
}
