/**
 * MetricsWithImageSlideLayout - Metrics with image.
 *
 * Fields: title, description, image, metrics[]{label, value}
 */
import ImageUploadZone from "../ImageUploadZone";
import EditableText from "../EditableText";

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

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <ImageUploadZone
        imageUrl={d.image?.__image_url__}
        fieldPath="image"
        className="w-2/5 m-6 mr-0"
      />

      <div className="flex-1 flex flex-col justify-center px-10 py-8">
        <div
          className="w-10 h-1 mb-4 rounded-full"
          style={{ backgroundColor: "var(--primary-color, #323F50)" }}
        />

        <EditableText
          value={d.title}
          fieldPath="title"
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-2"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <EditableText
          value={d.description}
          fieldPath="description"
          as="p"
          className="text-sm leading-relaxed mb-6 opacity-75"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />

        {metrics.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {metrics.map((metric, i) => (
              <div
                key={i}
                className="p-3 rounded-lg"
                style={{
                  backgroundColor: "var(--card-color, #F8F7F6)",
                  border: "1px solid var(--stroke, #E5E7EB)",
                }}
              >
                <EditableText
                  value={metric.value}
                  fieldPath={`metrics.${i}.value`}
                  as="p"
                  className="text-xl font-bold leading-none mb-1"
                  style={{ color: "var(--primary-color, #323F50)" }}
                />
                <EditableText
                  value={metric.label}
                  fieldPath={`metrics.${i}.label`}
                  as="p"
                  className="text-xs leading-snug opacity-70"
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
