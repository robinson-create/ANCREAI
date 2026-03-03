import { User } from "lucide-react";
import StaticImage from "../StaticImage.js";
import StaticText from "../StaticText.js";

/**
 * TeamSlideLayout - Team members.
 *
 * Fields: title, companyDescription, teamMembers[]{name, position, description, image}
 */

interface TeamMember {
  name?: string;
  position?: string;
  description?: string;
  image?: { __image_url__?: string };
}

interface TeamSlideData {
  title?: string;
  companyDescription?: string;
  teamMembers?: TeamMember[];
}

export default function TeamSlideLayout({ data }: { data: Record<string, any> }) {
  const d = data as TeamSlideData;
  const members = d.teamMembers ?? [];

  const memberGridCols =
    members.length <= 2 ? "grid-cols-2"
    : members.length === 3 ? "grid-cols-3"
    : "grid-cols-2";

  return (
    <div
      className="relative w-full h-full overflow-hidden flex"
      style={{
        backgroundColor: "var(--background-color, #FFFFFF)",
        color: "var(--background-text, #323F50)",
        fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
      }}
    >
      <div className="w-2/5 flex flex-col justify-center px-14 py-8">
        <div
          className="w-10 h-1 mb-5 rounded-full"
          style={{ backgroundColor: "var(--primary-color, #323F50)" }}
        />

        <StaticText
          value={d.title}
          as="h2"
          className="text-3xl font-bold leading-tight tracking-tight mb-3"
          style={{
            color: "var(--primary-color, #323F50)",
            fontFamily: "var(--heading-font-family, 'Plus Jakarta Sans'), system-ui, sans-serif",
          }}
          placeholder="Titre"
        />

        <StaticText
          value={d.companyDescription}
          as="p"
          className="text-sm leading-relaxed opacity-75"
          style={{ color: "var(--background-text, #323F50)" }}
          placeholder="Description"
        />
      </div>

      <div className="flex-1 flex items-center py-8 pr-10">
        <div className={`grid ${memberGridCols} gap-4 w-full`}>
          {members.map((member, i) => (
            <div
              key={i}
              className="flex flex-col items-center text-center p-4 rounded-lg"
              style={{
                backgroundColor: "var(--card-color, #F8F7F6)",
                border: "1px solid var(--stroke, #E5E7EB)",
              }}
            >
              <StaticImage
                imageUrl={member.image?.__image_url__}
                className="w-14 h-14 mb-3"
                circular
              >
                <User
                  className="w-6 h-6"
                  style={{ color: "var(--primary-color, #323F50)", opacity: 0.4 }}
                />
              </StaticImage>

              <StaticText
                value={member.name}
                as="p"
                className="text-sm font-semibold leading-snug mb-0.5"
                style={{ color: "var(--primary-color, #323F50)" }}
              />
              <StaticText
                value={member.position}
                as="p"
                className="text-xs font-medium leading-snug mb-1.5 uppercase tracking-wide"
                style={{ color: "var(--primary-color, #323F50)", opacity: 0.6 }}
              />
              <StaticText
                value={member.description}
                as="p"
                className="text-xs leading-relaxed opacity-60 line-clamp-2"
                style={{ color: "var(--background-text, #323F50)" }}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
