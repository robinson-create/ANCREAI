/**
 * MetricsSlideLayout - Key metrics display.
 *
 * Fields: title, metrics[]{label, value, description}
 */
import EditableText from "../EditableText";

interface Metric {
  label?: string;
  value?: string;
  description?: string;
}

interface MetricsSlideData {
  title?: string;
  metrics?: Metric[];
}

export default function MetricsSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as MetricsSlideData;
  const metrics = d.metrics ?? [];

  const gridCols =
    metrics.length <= 2
      ? "grid-cols-2"
      : metrics.length === 3
        ? "grid-cols-3"
        : "grid-cols-4";

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-center px-14 py-8"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <EditableText
        value={d.title}
        fieldPath="title"
        as="h2"
        className="text-3xl font-bold leading-tight tracking-tight mb-8 text-center"
        style={{
          color: "var(--primary-color, #323F50)",
          fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
        }}
        placeholder="Titre"
      />

      <div className={`grid ${gridCols} gap-4`}>
        {metrics.map((metric, i) => (
          <div
            key={i}
            className="flex flex-col items-center text-center p-6 rounded-lg"
            style={{
              backgroundColor: "var(--card-color, #F8F7F6)",
              border: "1px solid var(--stroke, #E5E7EB)",
            }}
          >
            <EditableText
              value={metric.value}
              fieldPath={`metrics.${i}.value`}
              as="p"
              className="text-3xl font-bold leading-none mb-2"
              style={{ color: "var(--primary-color, #323F50)" }}
            />
            <EditableText
              value={metric.label}
              fieldPath={`metrics.${i}.label`}
              as="p"
              className="text-sm font-semibold leading-snug mb-1 uppercase tracking-wide"
              style={{ color: "var(--primary-color, #323F50)", opacity: 0.8 }}
            />
            <EditableText
              value={metric.description}
              fieldPath={`metrics.${i}.description`}
              as="p"
              className="text-xs leading-relaxed opacity-60 line-clamp-2"
              style={{ color: "var(--background-text, #323F50)" }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
