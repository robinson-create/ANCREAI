/**
 * StaticText — pure render text component for slide templates.
 *
 * Unlike EditableText (frontend), this component has zero interactivity:
 * no contentEditable, no hooks, no state. Safe for SSR.
 */

interface StaticTextProps {
  value: string | undefined;
  as?: "h1" | "h2" | "h3" | "p" | "span" | "div";
  className?: string;
  style?: React.CSSProperties;
  placeholder?: string;
}

export default function StaticText({
  value,
  as: Tag = "span",
  className,
  style,
  placeholder,
}: StaticTextProps) {
  const displayText = value || "";

  return (
    <Tag
      className={className}
      style={style}
      data-placeholder={!displayText ? placeholder : undefined}
    >
      {displayText}
    </Tag>
  );
}
