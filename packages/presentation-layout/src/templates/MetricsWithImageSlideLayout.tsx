/**
 * MetricsWithImageSlideLayout - Metrics with image.
 *
 * Fields: title, description, image, metrics[]{label, value}
 */
import StaticImage from "../StaticImage.js";
import StaticText from "../StaticText.js";

interface Metric {
  label?: string;
  value?: string;
}

interface MetricsWithImageSlideData {
  title?: string;
  description?: string;
  image?: { __image_url__?: string };
  metrics?: Metric[];
}

export default function MetricsWithImageSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as MetricsWithImageSlideData;
  const metrics = d.metrics ?? [];
  const compact = metrics.length > 4;

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <StaticImage
        imageUrl={d.image?.__image_url__}
        className="w-2/5 m-6 mr-0"
      />

      <div className="flex-1 flex flex-col justify-center px-10 py-8">
        <div
          className="w-10 h-1 mb-4 rounded-full"
          style={{ backgroundColor: "var(--primary-color, #323F50)" }}
        />

        <StaticText
          value={d.title}
          as="h2"
          className={`font-bold leading-tight tracking-tight ${compact ? "text-2xl mb-1" : "text-3xl mb-2"}`}
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <StaticText
          value={d.description}
          as="p"
          className={`leading-relaxed opacity-75 ${compact ? "text-xs mb-3" : "text-sm mb-6"}`}
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />

        {metrics.length > 0 && (
          <div className={`grid ${compact ? "grid-cols-3 gap-2" : "grid-cols-2 gap-3"}`}>
            {metrics.map((metric, i) => (
              <div
                key={i}
                className={`rounded-lg ${compact ? "p-2" : "p-3"}`}
                style={{
                  backgroundColor: "var(--card-color, #F8F7F6)",
                  border: "1px solid var(--stroke, #E5E7EB)",
                }}
              >
                <StaticText
                  value={metric.value}
                  as="p"
                  className={`font-bold leading-none mb-1 ${compact ? "text-base" : "text-xl"}`}
                  style={{ color: "var(--primary-color, #323F50)" }}
                />
                <StaticText
                  value={metric.label}
                  as="p"
                  className={`leading-snug opacity-70 ${compact ? "text-[10px]" : "text-xs"}`}
                  style={{ color: "var(--background-text, #323F50)" }}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
