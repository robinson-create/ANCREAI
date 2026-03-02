/**
 * TableInfoSlideLayout - Data table.
 *
 * Fields: title, tableData{headers[], rows[][]}, description
 */
import EditableText from "../EditableText";

interface TableData {
  headers?: string[];
  rows?: string[][];
}

interface TableInfoSlideData {
  title?: string;
  tableData?: TableData;
  description?: string;
}

export default function TableInfoSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as TableInfoSlideData;
  const headers = d.tableData?.headers ?? [];
  const rows = d.tableData?.rows ?? [];

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
        value={d.title}
        fieldPath="title"
        as="h2"
        className="text-3xl font-bold leading-tight tracking-tight mb-5"
        style={{
          color: "var(--primary-color, #323F50)",
          fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
        }}
        placeholder="Titre"
      />

      <div
        className="flex-1 overflow-auto rounded-lg"
        style={{ border: "1px solid var(--stroke, #E5E7EB)" }}
      >
        <table className="w-full text-left border-collapse">
          {headers.length > 0 && (
            <thead>
              <tr style={{ backgroundColor: "var(--primary-color, #323F50)" }}>
                {headers.map((header, i) => (
                  <th
                    key={i}
                    className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider whitespace-nowrap"
                    style={{ color: "var(--primary-text, #FFFFFF)" }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
          )}

          <tbody>
            {rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                style={{
                  backgroundColor:
                    rowIdx % 2 === 0
                      ? "var(--background-color, #FFFFFF)"
                      : "var(--card-color, #F8F7F6)",
                  borderBottom: "1px solid var(--stroke, #E5E7EB)",
                }}
              >
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className="px-4 py-2 text-xs leading-snug"
                    style={{ color: "var(--background-text, #323F50)" }}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <EditableText
        value={d.description}
        fieldPath="description"
        as="p"
        className="text-xs leading-relaxed mt-3 opacity-60"
        style={{ color: "var(--background-text, #323F50)" }}
        placeholder="Description"
      />
    </div>
  );
}
