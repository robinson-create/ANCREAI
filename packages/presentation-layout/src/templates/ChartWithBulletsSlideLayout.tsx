import * as LucideIcons from "lucide-react";
import StaticText from "../StaticText.js";

/**
 * ChartWithBulletsSlideLayout - Chart + bullet boxes.
 *
 * In SSR context (no DOM), charts are rendered as styled data tables.
 * Fields: title, description, chartData{type, data[]}, bulletPoints[]{title, description, icon}
 */

interface ChartDataItem {
  label?: string;
  name?: string;
  value?: number;
  count?: number;
  [key: string]: any;
}

interface ChartData {
  type?: "bar" | "line" | "pie" | "area" | "scatter";
  data?: ChartDataItem[];
}

interface BulletPoint {
  title?: string;
  description?: string;
  icon?: string;
}

interface ChartWithBulletsSlideData {
  title?: string;
  description?: string;
  chartData?: ChartData;
  bulletPoints?: BulletPoint[];
}

function SlideIcon({ name, className }: { name?: string; className?: string }) {
  if (!name) return null;
  const Icon = (LucideIcons as any)[name] || LucideIcons.Circle;
  return <Icon className={className} />;
}

const CHART_COLORS = [
  "#323F50", "#8896A6", "#EFEBEA", "#5A6B7D",
  "#A8B5C2", "#D1CBC8", "#4A5968", "#313F4F",
];

function getLabelKey(data: ChartDataItem[]): string {
  if (data.length === 0) return "label";
  const sample = data[0]!;
  if ("label" in sample) return "label";
  if ("name" in sample) return "name";
  return "label";
}

function getValueKey(data: ChartDataItem[]): string {
  if (data.length === 0) return "value";
  const sample = data[0]!;
  if ("value" in sample) return "value";
  if ("count" in sample) return "count";
  if ("y" in sample) return "y";
  return "value";
}

/** SSR-safe chart fallback: renders data as a styled table with bar indicators. */
function ChartFallback({ chartData }: { chartData: ChartData }) {
  const data = chartData.data ?? [];
  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-full border border-dashed rounded-lg"
        style={{
          borderColor: "var(--stroke, #E5E7EB)",
          backgroundColor: "var(--card-color, #F8F7F6)",
        }}
      >
        <span className="text-sm opacity-50">No chart data</span>
      </div>
    );
  }

  const lk = getLabelKey(data);
  const vk = getValueKey(data);
  const maxVal = Math.max(...data.map((d) => Number(d[vk]) || 0), 1);

  return (
    <div className="flex flex-col gap-1.5 h-full justify-center">
      {data.map((item, i) => {
        const val = Number(item[vk]) || 0;
        const pct = Math.round((val / maxVal) * 100);
        return (
          <div key={i} className="flex items-center gap-2">
            <span
              className="text-[10px] w-16 text-right truncate shrink-0"
              style={{ color: "var(--background-text, #323F50)" }}
            >
              {String(item[lk] ?? "")}
            </span>
            <div className="flex-1 h-4 rounded-sm overflow-hidden" style={{ backgroundColor: "var(--card-color, #F8F7F6)" }}>
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${pct}%`,
                  backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                }}
              />
            </div>
            <span
              className="text-[10px] w-10 shrink-0 tabular-nums"
              style={{ color: "var(--background-text, #323F50)" }}
            >
              {val}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function ChartWithBulletsSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as ChartWithBulletsSlideData;
  const bullets = d.bulletPoints ?? [];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col px-14 py-8"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <div className="mb-4">
        <StaticText
          value={d.title}
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-1"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />
        <StaticText
          value={d.description}
          as="p"
          className="text-base leading-relaxed opacity-75"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />
      </div>

      <div className="flex flex-1 gap-6 min-h-0">
        <div
          className="flex-1 rounded-lg p-3"
          style={{
            border: "1px solid var(--stroke, #E5E7EB)",
            backgroundColor: "var(--card-color, #F8F7F6)",
          }}
        >
          {d.chartData ? (
            <ChartFallback chartData={d.chartData} />
          ) : (
            <div className="flex items-center justify-center h-full opacity-40">
              <span className="text-sm">No chart data provided</span>
            </div>
          )}
        </div>

        {bullets.length > 0 && (
          <div className="w-2/5 flex flex-col gap-2 overflow-y-auto">
            {bullets.map((bullet, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-3 rounded-lg"
                style={{
                  backgroundColor: "var(--card-color, #F8F7F6)",
                  border: "1px solid var(--stroke, #E5E7EB)",
                }}
              >
                <div
                  className="flex items-center justify-center w-7 h-7 rounded-md shrink-0"
                  style={{
                    backgroundColor: "color-mix(in srgb, var(--primary-color, #323F50) 10%, transparent)",
                  }}
                >
                  <SlideIcon name={bullet.icon} className="w-3.5 h-3.5" />
                </div>

                <div className="flex-1 min-w-0">
                  <StaticText
                    value={bullet.title}
                    as="p"
                    className="text-xs font-semibold leading-snug mb-0.5"
                    style={{ color: "var(--primary-color, #323F50)" }}
                  />
                  <StaticText
                    value={bullet.description}
                    as="p"
                    className="text-xs leading-snug opacity-70 line-clamp-2"
                    style={{ color: "var(--background-text, #323F50)" }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
