import * as LucideIcons from "lucide-react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Cell,
  ResponsiveContainer,
} from "recharts";
import EditableText from "../EditableText";

/**
 * ChartWithBulletsSlideLayout - Chart + bullet boxes.
 *
 * Fields: title, description, chartData{type, data[]}, bulletPoints[]{title, description, icon}
 */

interface ChartDataItem {
  label?: string;
  name?: string;
  value?: number;
  count?: number;
  x?: number;
  y?: number;
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
  "#323F50",
  "#8896A6",
  "#EFEBEA",
  "#5A6B7D",
  "#A8B5C2",
  "#D1CBC8",
  "#4A5968",
  "#313F4F",
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

function ChartRenderer({ chartData }: { chartData: ChartData }) {
  const type = chartData.type ?? "bar";
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

  switch (type) {
    case "bar":
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <XAxis dataKey={lk} tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} width={30} />
            <Tooltip contentStyle={{ fontSize: 10 }} />
            <Bar dataKey={vk} radius={[3, 3, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      );

    case "line":
      return (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey={lk} tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} width={30} />
            <Tooltip contentStyle={{ fontSize: 10 }} />
            <Line
              type="monotone"
              dataKey={vk}
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      );

    case "pie":
      return (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey={vk}
              nameKey={lk}
              innerRadius={0}
              outerRadius={70}
              labelLine={false}
              label={({ percent }: { percent?: number }) =>
                percent ? `${Math.round(percent * 100)}%` : ""
              }
            >
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ fontSize: 10 }} />
            <Legend wrapperStyle={{ fontSize: 9 }} />
          </PieChart>
        </ResponsiveContainer>
      );

    case "area":
      return (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="chartAreaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis dataKey={lk} tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 9 }} width={30} />
            <Tooltip contentStyle={{ fontSize: 10 }} />
            <Area
              type="monotone"
              dataKey={vk}
              stroke={CHART_COLORS[0]}
              fill="url(#chartAreaGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      );

    case "scatter":
      return (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <XAxis dataKey="x" tick={{ fontSize: 9 }} />
            <YAxis dataKey="y" tick={{ fontSize: 9 }} width={30} />
            <Tooltip contentStyle={{ fontSize: 10 }} />
            <Scatter data={data} fill={CHART_COLORS[0]} />
          </ScatterChart>
        </ResponsiveContainer>
      );

    default:
      return (
        <div className="flex items-center justify-center h-full opacity-50">
          <span className="text-sm">Unsupported chart type: {type}</span>
        </div>
      );
  }
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
        <EditableText
          value={d.title}
          fieldPath="title"
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-1"
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
            <ChartRenderer chartData={d.chartData} />
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
                  <EditableText
                    value={bullet.title}
                    fieldPath={`bulletPoints.${i}.title`}
                    as="p"
                    className="text-xs font-semibold leading-snug mb-0.5"
                    style={{ color: "var(--primary-color, #323F50)" }}
                  />
                  <EditableText
                    value={bullet.description}
                    fieldPath={`bulletPoints.${i}.description`}
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
