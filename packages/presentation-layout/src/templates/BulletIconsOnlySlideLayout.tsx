import * as LucideIcons from "lucide-react";
import StaticImage from "../StaticImage.js";
import StaticText from "../StaticText.js";

/**
 * BulletIconsOnlySlideLayout - Grid of icon bullets.
 *
 * Fields: title, image, bulletPoints[]{title, subtitle?, icon}
 */

interface BulletPoint {
  title?: string;
  subtitle?: string;
  icon?: string;
}

interface BulletIconsOnlySlideData {
  title?: string;
  image?: { __image_url__?: string };
  bulletPoints?: BulletPoint[];
}

function SlideIcon({ name, className }: { name?: string; className?: string }) {
  if (!name) return null;
  const Icon = (LucideIcons as any)[name] || LucideIcons.Circle;
  return <Icon className={className} />;
}

export default function BulletIconsOnlySlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as BulletIconsOnlySlideData;
  const bullets = d.bulletPoints ?? [];

  const gridCols =
    bullets.length <= 2 ? "grid-cols-2"
    : bullets.length === 3 ? "grid-cols-3"
    : "grid-cols-2";

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
          className="text-3xl font-bold leading-tight tracking-tight mb-6"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <div className={`grid ${gridCols} gap-4`}>
          {bullets.map((bullet, i) => (
            <div
              key={i}
              className="flex flex-col items-start gap-2 p-4 rounded-lg"
              style={{
                backgroundColor: "var(--card-color, #F8F7F6)",
                border: "1px solid var(--stroke, #E5E7EB)",
              }}
            >
              <div
                className="flex items-center justify-center w-8 h-8 rounded-lg"
                style={{
                  backgroundColor: "color-mix(in srgb, var(--primary-color, #323F50) 10%, transparent)",
                }}
              >
                <SlideIcon name={bullet.icon} className="w-4 h-4" />
              </div>

              <StaticText
                value={bullet.title}
                as="p"
                className="text-sm font-semibold leading-snug"
                style={{ color: "var(--primary-color, #323F50)" }}
              />
              <StaticText
                value={bullet.subtitle}
                as="p"
                className="text-xs leading-snug opacity-70"
                style={{ color: "var(--background-text, #323F50)" }}
              />
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
