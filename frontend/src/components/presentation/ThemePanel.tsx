import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, Plus, X, Palette } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { presentationsApi } from "@/api/presentations"
import type { ThemeData, ThemeColors, ThemeFonts } from "@/types"

interface ThemePanelProps {
  presentationId: string
  currentThemeId?: string | null
  onClose: () => void
}

const DEFAULT_THEME: ThemeData = {
  colors: {
    primary: "#6C63FF",
    secondary: "#2D2B55",
    accent: "#FF6584",
    background: "#FFFFFF",
    text: "#333333",
    heading: "#1a1a2e",
    muted: "#6b7280",
  },
  fonts: {
    heading: "Inter",
    body: "Inter",
  },
  border_radius: "12px",
}

const BUILTIN_THEMES: { name: string; colors: Partial<ThemeColors> }[] = [
  { name: "Violet", colors: { primary: "#6C63FF", secondary: "#2D2B55", accent: "#FF6584", background: "#FFFFFF" } },
  { name: "Ocean", colors: { primary: "#0EA5E9", secondary: "#0C4A6E", accent: "#38BDF8", background: "#F0F9FF" } },
  { name: "Forest", colors: { primary: "#16A34A", secondary: "#14532D", accent: "#4ADE80", background: "#F0FDF4" } },
  { name: "Sunset", colors: { primary: "#EA580C", secondary: "#7C2D12", accent: "#FB923C", background: "#FFF7ED" } },
  { name: "Rose", colors: { primary: "#E11D48", secondary: "#881337", accent: "#FB7185", background: "#FFF1F2" } },
  { name: "Sombre", colors: { primary: "#A78BFA", secondary: "#1E1B4B", accent: "#C4B5FD", background: "#0F172A", text: "#E2E8F0", heading: "#F8FAFC", muted: "#94A3B8" } },
  { name: "Charbon", colors: { primary: "#F59E0B", secondary: "#1C1917", accent: "#FBBF24", background: "#1C1917", text: "#E7E5E4", heading: "#FAFAF9", muted: "#A8A29E" } },
  { name: "Minimaliste", colors: { primary: "#000000", secondary: "#171717", accent: "#525252", background: "#FFFFFF", text: "#171717", heading: "#000000", muted: "#737373" } },
]

const FONT_OPTIONS = [
  "Inter",
  "Roboto",
  "Open Sans",
  "Lato",
  "Montserrat",
  "Poppins",
  "Playfair Display",
  "Merriweather",
  "Source Sans Pro",
  "Raleway",
  "Nunito",
  "DM Sans",
]

function ColorInput({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-6 w-6 rounded border cursor-pointer shrink-0"
      />
      <span className="text-xs text-muted-foreground flex-1">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-20 text-xs border rounded px-1.5 py-0.5 font-mono bg-background"
      />
    </div>
  )
}

function ThemePreview({
  colors,
  name,
  isSelected,
  onClick,
}: {
  colors: Partial<ThemeColors>
  name: string
  isSelected: boolean
  onClick: () => void
}) {
  const bg = colors.background || "#FFFFFF"
  const primary = colors.primary || "#6C63FF"
  const text = colors.text || "#333333"
  const heading = colors.heading || "#1a1a2e"

  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-lg border-2 p-1.5 transition-all text-left w-full",
        isSelected ? "border-primary ring-1 ring-primary/20" : "border-border hover:border-primary/40",
      )}
    >
      <div className="aspect-video rounded overflow-hidden relative" style={{ backgroundColor: bg }}>
        <div className="p-1.5 space-y-0.5">
          <div className="h-1 w-2/3 rounded-sm" style={{ backgroundColor: heading }} />
          <div className="h-0.5 w-full rounded-sm" style={{ backgroundColor: text, opacity: 0.3 }} />
          <div className="h-0.5 w-4/5 rounded-sm" style={{ backgroundColor: text, opacity: 0.3 }} />
          <div className="flex gap-0.5 mt-1">
            <div className="flex-1 h-3 rounded-sm" style={{ backgroundColor: primary, opacity: 0.2 }} />
            <div className="flex-1 h-3 rounded-sm" style={{ backgroundColor: primary, opacity: 0.2 }} />
          </div>
        </div>
        {isSelected && (
          <div className="absolute top-0.5 right-0.5 h-3 w-3 rounded-full bg-primary flex items-center justify-center">
            <Check className="h-2 w-2 text-primary-foreground" />
          </div>
        )}
      </div>
      <p className="text-[10px] font-medium mt-1 text-center truncate">{name}</p>
    </button>
  )
}

export function ThemePanel({
  presentationId,
  currentThemeId,
  onClose,
}: ThemePanelProps) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<"presets" | "custom">("presets")
  const [customColors, setCustomColors] = useState<ThemeColors>(DEFAULT_THEME.colors)
  const [customFonts, setCustomFonts] = useState<ThemeFonts>(DEFAULT_THEME.fonts)
  const [customName, setCustomName] = useState("")

  const { data: themes } = useQuery({
    queryKey: ["presentation-themes"],
    queryFn: presentationsApi.listThemes,
  })

  const applyThemeMutation = useMutation({
    mutationFn: (themeId: string) => presentationsApi.applyTheme(presentationId, themeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["presentation", presentationId] })
    },
  })

  const createThemeMutation = useMutation({
    mutationFn: () =>
      presentationsApi.createTheme({
        name: customName || "Mon thème",
        theme_data: {
          colors: customColors,
          fonts: customFonts,
          border_radius: "12px",
        },
      }),
    onSuccess: (newTheme) => {
      queryClient.invalidateQueries({ queryKey: ["presentation-themes"] })
      applyThemeMutation.mutate(newTheme.id)
      setCustomName("")
    },
  })

  const handleColorChange = useCallback(
    (key: keyof ThemeColors, value: string) => {
      setCustomColors((prev) => ({ ...prev, [key]: value }))
    },
    [],
  )

  const handleApplyBuiltin = useCallback(
    (preset: (typeof BUILTIN_THEMES)[number]) => {
      const themeData: ThemeData = {
        colors: { ...DEFAULT_THEME.colors, ...preset.colors },
        fonts: DEFAULT_THEME.fonts,
        border_radius: "12px",
      }
      // Find matching saved theme or create one
      const existing = themes?.find(
        (t) => t.name === preset.name && t.is_builtin,
      )
      if (existing) {
        applyThemeMutation.mutate(existing.id)
      } else {
        // Create as custom theme with preset values
        presentationsApi
          .createTheme({ name: preset.name, theme_data: themeData })
          .then((t) => {
            queryClient.invalidateQueries({ queryKey: ["presentation-themes"] })
            applyThemeMutation.mutate(t.id)
          })
      }
    },
    [themes, applyThemeMutation, queryClient],
  )

  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4" />
          <h3 className="text-sm font-semibold">Thème & Style</h3>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        <button
          className={cn(
            "flex-1 py-2 text-sm font-medium transition-colors",
            tab === "presets" ? "border-b-2 border-primary text-primary" : "text-muted-foreground",
          )}
          onClick={() => setTab("presets")}
        >
          Préréglages
        </button>
        <button
          className={cn(
            "flex-1 py-2 text-sm font-medium transition-colors",
            tab === "custom" ? "border-b-2 border-primary text-primary" : "text-muted-foreground",
          )}
          onClick={() => setTab("custom")}
        >
          Personnalisé
        </button>
      </div>

      <ScrollArea className="flex-1">
        {tab === "presets" ? (
          <div className="p-3 space-y-4">
            {/* Built-in presets */}
            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Thèmes prédéfinis</Label>
              <div className="grid grid-cols-2 gap-2">
                {BUILTIN_THEMES.map((preset) => (
                  <ThemePreview
                    key={preset.name}
                    name={preset.name}
                    colors={preset.colors}
                    isSelected={false}
                    onClick={() => handleApplyBuiltin(preset)}
                  />
                ))}
              </div>
            </div>

            {/* Custom themes from DB */}
            {themes && themes.length > 0 && (
              <div>
                <Separator className="mb-3" />
                <Label className="text-xs text-muted-foreground mb-2 block">Vos thèmes</Label>
                <div className="grid grid-cols-2 gap-2">
                  {themes.map((theme) => (
                    <ThemePreview
                      key={theme.id}
                      name={theme.name}
                      colors={theme.theme_data.colors}
                      isSelected={currentThemeId === theme.id}
                      onClick={() => applyThemeMutation.mutate(theme.id)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-3 space-y-4">
            {/* Colors */}
            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Couleurs</Label>
              <div className="space-y-2">
                <ColorInput label="Primaire" value={customColors.primary} onChange={(v) => handleColorChange("primary", v)} />
                <ColorInput label="Secondaire" value={customColors.secondary} onChange={(v) => handleColorChange("secondary", v)} />
                <ColorInput label="Accent" value={customColors.accent} onChange={(v) => handleColorChange("accent", v)} />
                <ColorInput label="Fond" value={customColors.background} onChange={(v) => handleColorChange("background", v)} />
                <ColorInput label="Texte" value={customColors.text} onChange={(v) => handleColorChange("text", v)} />
                <ColorInput label="Titres" value={customColors.heading} onChange={(v) => handleColorChange("heading", v)} />
                <ColorInput label="Atténué" value={customColors.muted} onChange={(v) => handleColorChange("muted", v)} />
              </div>
            </div>

            <Separator />

            {/* Fonts */}
            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Polices</Label>
              <div className="space-y-2">
                <div>
                  <Label className="text-xs mb-1 block">Titres</Label>
                  <select
                    value={customFonts.heading}
                    onChange={(e) => setCustomFonts((f) => ({ ...f, heading: e.target.value }))}
                    className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
                  >
                    {FONT_OPTIONS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label className="text-xs mb-1 block">Corps</Label>
                  <select
                    value={customFonts.body}
                    onChange={(e) => setCustomFonts((f) => ({ ...f, body: e.target.value }))}
                    className="w-full border rounded-md px-2 py-1.5 text-sm bg-background"
                  >
                    {FONT_OPTIONS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <Separator />

            {/* Preview */}
            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Aperçu</Label>
              <div
                className="aspect-video rounded-lg border p-3 space-y-1"
                style={{ backgroundColor: customColors.background }}
              >
                <div
                  className="text-xs font-bold"
                  style={{ color: customColors.heading, fontFamily: customFonts.heading }}
                >
                  Titre de présentation
                </div>
                <div
                  className="text-[9px]"
                  style={{ color: customColors.text, fontFamily: customFonts.body }}
                >
                  Texte de contenu avec des informations détaillées.
                </div>
                <div className="flex gap-1 mt-1">
                  <div
                    className="flex-1 h-4 rounded text-[7px] flex items-center justify-center text-white"
                    style={{ backgroundColor: customColors.primary }}
                  >
                    Primaire
                  </div>
                  <div
                    className="flex-1 h-4 rounded text-[7px] flex items-center justify-center text-white"
                    style={{ backgroundColor: customColors.accent }}
                  >
                    Accent
                  </div>
                </div>
              </div>
            </div>

            <Separator />

            {/* Save */}
            <div className="space-y-2">
              <Input
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="Nom du thème"
                className="text-sm"
              />
              <Button
                className="w-full gap-1.5"
                size="sm"
                onClick={() => createThemeMutation.mutate()}
                disabled={createThemeMutation.isPending}
              >
                <Plus className="h-3.5 w-3.5" />
                Sauvegarder et appliquer
              </Button>
            </div>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
