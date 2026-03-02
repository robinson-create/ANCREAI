/**
 * TableOfContentsSlideLayout - TOC slide.
 *
 * Fields: sections[]{number, title, pageNumber}
 */
import EditableText from "../EditableText";

interface Section {
  number?: string | number;
  title?: string;
  pageNumber?: string | number;
}

interface TableOfContentsSlideData {
  sections?: Section[];
}

export default function TableOfContentsSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as TableOfContentsSlideData;
  const sections = d.sections ?? [];

  const midPoint = Math.ceil(sections.length / 2);
  const leftCol = sections.slice(0, midPoint);
  const rightCol = sections.slice(midPoint);

  function renderSection(section: Section, idx: number) {
    return (
      <div
        key={idx}
        className="flex items-center gap-4 py-3 group"
        style={{
          borderBottom: "1px solid var(--stroke, #E5E7EB)",
        }}
      >
        <span
          className="text-xl font-bold shrink-0 w-8 text-right tabular-nums"
          style={{ color: "var(--primary-color, #323F50)", opacity: 0.3 }}
        >
          {section.number ?? idx + 1}
        </span>

        <EditableText
          value={section.title}
          fieldPath={`sections.${idx}.title`}
          as="span"
          className="flex-1 text-sm font-medium leading-snug"
          style={{ color: "var(--background-text, #323F50)" }}
        />

        <span
          className="flex-shrink-0 mx-1 border-b border-dotted flex-1 min-w-4"
          style={{ borderColor: "var(--stroke, #E5E7EB)" }}
        />

        {section.pageNumber != null && (
          <span
            className="text-xs font-medium shrink-0 tabular-nums"
            style={{ color: "var(--primary-color, #323F50)", opacity: 0.5 }}
          >
            {section.pageNumber}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col px-14 py-8"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <EditableText
        value="Table des matières"
        fieldPath="tocTitle"
        as="h2"
        className="text-3xl font-bold leading-tight tracking-tight mb-8"
        style={{
          color: "var(--primary-color, #323F50)",
          fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
        }}
      />

      <div className="flex gap-10 flex-1">
        <div className="flex-1 flex flex-col">
          {leftCol.map((section, i) => renderSection(section, i))}
        </div>

        {rightCol.length > 0 && (
          <div className="flex-1 flex flex-col">
            {rightCol.map((section, i) => renderSection(section, midPoint + i))}
          </div>
        )}
      </div>
    </div>
  );
}
