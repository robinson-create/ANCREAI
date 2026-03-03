import * as LucideIcons from "lucide-react";
import StaticImage from "../StaticImage.js";
import StaticText from "../StaticText.js";

/**
 * BulletWithIconsSlideLayout - Bullet list with descriptions.
 *
 * Fields: title, description, image, bulletPoints[]{title, description, icon}
 */

interface BulletPoint {
  title?: string;
  description?: string;
  icon?: string;
}

interface BulletWithIconsSlideData {
  title?: string;
  description?: string;
  image?: { __image_url__?: string };
  bulletPoints?: BulletPoint[];
}

function SlideIcon({ name, className }: { name?: string; className?: string }) {
  if (!name) return null;
  const Icon = (LucideIcons as any)[name] || LucideIcons.Circle;
  return <Icon className={className} />;
}

export default function BulletWithIconsSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as BulletWithIconsSlideData;
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
        <StaticText
          value={d.title}
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-2"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <StaticText
          value={d.description}
          as="p"
          className="text-base leading-relaxed mb-5 opacity-75 max-w-lg"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />

        <div className="flex flex-col gap-3">
          {bullets.map((bullet, i) => (
            <div
              key={i}
              className="flex items-start gap-3 p-3 rounded-lg"
              style={{
                backgroundColor: "var(--card-color, #F8F7F6)",
                border: "1px solid var(--stroke, #E5E7EB)",
              }}
            >
              <div
                className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0 mt-0.5"
                style={{
                  backgroundColor: "color-mix(in srgb, var(--primary-color, #323F50) 10%, transparent)",
                }}
              >
                <SlideIcon name={bullet.icon} className="w-4 h-4" />
              </div>

              <div className="flex-1 min-w-0">
                <StaticText
                  value={bullet.title}
                  as="p"
                  className="text-sm font-semibold leading-snug mb-0.5"
                  style={{ color: "var(--primary-color, #323F50)" }}
                />
                <StaticText
                  value={bullet.description}
                  as="p"
                  className="text-xs leading-relaxed opacity-70 line-clamp-2"
                  style={{ color: "var(--background-text, #323F50)" }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <StaticImage
        imageUrl={d.image?.__image_url__}
        className="w-1/3 m-6"
      />
    </div>
  );
}
