/**
 * SlideTemplateRenderer — renders a slide using the JSON template system.
 *
 * Pure render component, SSR-safe (no hooks, no effects).
 */
import { TEMPLATE_REGISTRY } from "./templates/index.js";
import { cleanData } from "./utils.js";

interface SlideTemplateRendererProps {
  layoutType: string;
  data: Record<string, any>;
}

function FallbackSlide({ data }: { data: Record<string, any> }) {
  return (
    <div
      className="w-full h-full overflow-hidden flex items-center justify-center"
      style={{
        fontFamily: "var(--heading-font-family, Plus Jakarta Sans)",
        background: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
      }}
    >
      <div className="text-center p-8">
        <h2 className="text-2xl font-bold mb-4">
          {data?.title || data?.heading || "Slide"}
        </h2>
        {data?.description && (
          <p className="text-base opacity-70">{data.description}</p>
        )}
      </div>
    </div>
  );
}

export default function SlideTemplateRenderer({
  layoutType,
  data,
}: SlideTemplateRendererProps) {
  const entry = TEMPLATE_REGISTRY[layoutType];
  const cleaned = cleanData(data || {});

  if (!entry) {
    return <FallbackSlide data={cleaned} />;
  }

  const Template = entry.component;
  return <Template data={cleaned} />;
}
