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
  const n = metrics.length;

  // Auto-compact: adapt grid columns and sizing based on item count
  const compact = n > 3;
  const veryCompact = n > 6;

  const gridCols =
    n <= 2
      ? "grid-cols-2"
      : n === 3
        ? "grid-cols-3"
        : n <= 6
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
        className={`font-bold leading-tight tracking-tight text-center ${compact ? "text-2xl mb-4" : "text-3xl mb-8"}`}
        style={{
          color: "var(--primary-color, #323F50)",
          fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
        }}
        placeholder="Titre"
      />

      <div className={`grid ${gridCols} ${veryCompact ? "gap-2" : compact ? "gap-3" : "gap-4"}`}>
        {metrics.map((metric, i) => (
          <div
            key={i}
            className={`flex flex-col items-center text-center rounded-lg ${veryCompact ? "p-2.5" : compact ? "p-3" : "p-6"}`}
            style={{
              backgroundColor: "var(--card-color, #F8F7F6)",
              border: "1px solid var(--stroke, #E5E7EB)",
            }}
          >
            <EditableText
              value={metric.value}
              fieldPath={`metrics.${i}.value`}
              as="p"
              className={`font-bold leading-none ${veryCompact ? "text-lg mb-1" : compact ? "text-xl mb-1" : "text-3xl mb-2"}`}
              style={{ color: "var(--primary-color, #323F50)" }}
            />
            <EditableText
              value={metric.label}
              fieldPath={`metrics.${i}.label`}
              as="p"
              className={`font-semibold leading-snug uppercase tracking-wide ${veryCompact ? "text-[10px] mb-0.5" : compact ? "text-xs mb-0.5" : "text-sm mb-1"}`}
              style={{ color: "var(--primary-color, #323F50)", opacity: 0.8 }}
            />
            {!veryCompact && metric.description && (
              <EditableText
                value={metric.description}
                fieldPath={`metrics.${i}.description`}
                as="p"
                className={`leading-relaxed opacity-60 line-clamp-2 ${compact ? "text-[10px]" : "text-xs"}`}
                style={{ color: "var(--background-text, #323F50)" }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
