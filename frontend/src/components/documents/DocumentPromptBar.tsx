/**
 * AI Prompt Bar for the document editor.
 * Allows users to type or dictate instructions to generate document blocks via Mistral.
 * Also provides quick-add buttons for manual block creation.
 */

import { useState, useRef, useCallback, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Mic,
  MicOff,
  SendHorizontal,
  Plus,
  FileText,
  Table2,
  Scale,
  ScrollText,
  PenLine,
  Variable,
  ChevronUp,
  Sparkles,
  AlertCircle,
  Copy,
  Check,
  History,
  Clock,
  RotateCcw,
  X,
  Bot,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { assistantsApi } from "@/api/assistants"
import { useDocumentStore } from "@/hooks/use-document-store"
import { useDocumentGeneration } from "@/contexts/document-generation-context"
import type { Assistant, DocBlock, DocBlockKind } from "@/types"

// ── Prompt history ──

interface HistoryEntry {
  prompt: string
  response: string
  timestamp: number
}

const HISTORY_KEY_PREFIX = "ancre_prompt_history_"
const MAX_HISTORY = 20

function getHistory(docId: string): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY_PREFIX + docId)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveHistory(docId: string, entries: HistoryEntry[]) {
  try {
    localStorage.setItem(
      HISTORY_KEY_PREFIX + docId,
      JSON.stringify(entries.slice(0, MAX_HISTORY))
    )
  } catch {
    // localStorage full or unavailable
  }
}

// ── Speech Recognition: see src/speech-recognition.d.ts ──

const BLOCK_TYPES: { type: DocBlockKind; label: string; icon: typeof FileText }[] = [
  { type: "rich_text", label: "Texte riche", icon: FileText },
  { type: "line_items", label: "Lignes (devis/facture)", icon: Table2 },
  { type: "clause", label: "Clause", icon: Scale },
  { type: "terms", label: "Conditions", icon: ScrollText },
  { type: "signature", label: "Signature", icon: PenLine },
  { type: "variables", label: "Variables", icon: Variable },
]

// ── Props ──

interface DocumentPromptBarProps {
  docId: string
  docType: string
  collectionIds?: string[]
  onAddBlock: (type: DocBlockKind) => void
  isEmpty?: boolean
  onGeneratingChange?: (generating: boolean) => void
  initialPrompt?: string
}

export function DocumentPromptBar({
  docId,
  docType,
  collectionIds = [],
  onAddBlock,
  isEmpty = false,
  onGeneratingChange,
  initialPrompt,
}: DocumentPromptBarProps) {
  const [prompt, setPrompt] = useState("")
  const [isRecording, setIsRecording] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aiMessage, setAiMessage] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [selectedAssistantId, setSelectedAssistantId] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
  const wantsRecordingRef = useRef(false)

  const { updateBlock, addBlock } = useDocumentStore()
  const docGen = useDocumentGeneration()

  // Fetch assistants for selector
  const { data: assistants = [] } = useQuery({
    queryKey: ["assistants"],
    queryFn: assistantsApi.list,
    staleTime: 30_000,
  })

  // Auto-select first assistant
  useEffect(() => {
    const first = assistants[0]
    if (first && !selectedAssistantId) {
      setSelectedAssistantId(first.id)
    }
  }, [assistants, selectedAssistantId])

  // Compute effective collection IDs from selected assistant
  const selectedAssistant = assistants.find((a: Assistant) => a.id === selectedAssistantId)
  const collectionIdsFromAssistant = selectedAssistant?.collection_ids
  const effectiveCollectionIds =
    collectionIdsFromAssistant && collectionIdsFromAssistant.length > 0
      ? collectionIdsFromAssistant
      : collectionIds

  // Load history on mount
  useEffect(() => {
    setHistory(getHistory(docId))
  }, [docId])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = "auto"
      el.style.height = Math.min(el.scrollHeight, 120) + "px"
    }
  }, [prompt])

  // Auto-fill from initial prompt (dashboard)
  const initialPromptHandled = useRef(false)
  const shouldAutoGenerate = useRef(false)
  useEffect(() => {
    if (initialPrompt && !initialPromptHandled.current) {
      initialPromptHandled.current = true
      shouldAutoGenerate.current = true
      setPrompt(initialPrompt)
    }
  }, [initialPrompt])

  // Clear AI message after 8s (longer so user can copy)
  useEffect(() => {
    if (aiMessage) {
      const timer = setTimeout(() => setAiMessage(null), 8000)
      return () => clearTimeout(timer)
    }
  }, [aiMessage])

  // Reset copied state
  useEffect(() => {
    if (copied) {
      const timer = setTimeout(() => setCopied(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [copied])

  const copyToClipboard = useCallback((text: string) => {
    navigator.clipboard.writeText(text).then(() => setCopied(true))
  }, [])

  // ── Speech Recognition ──

  const startRecording = useCallback(() => {
    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognitionCtor) {
      setError("La reconnaissance vocale n'est pas supportee par ce navigateur.")
      return
    }

    // Stop any existing recording first
    if (recognitionRef.current) {
      wantsRecordingRef.current = false
      recognitionRef.current.stop()
      recognitionRef.current = null
    }

    wantsRecordingRef.current = true
    const recognition = new SpeechRecognitionCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = "fr-FR"

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = ""

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result?.isFinal) {
          finalTranscript += result[0]?.transcript ?? ""
        }
      }

      if (finalTranscript) {
        setPrompt((prev) => {
          const separator = prev && !prev.endsWith(" ") && !prev.endsWith("\n") ? " " : ""
          return prev + separator + finalTranscript
        })
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "aborted") return
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setError("Acces au microphone refuse.")
        wantsRecordingRef.current = false
        recognitionRef.current = null
        setIsRecording(false)
        return
      }
      setError(`Erreur de reconnaissance vocale: ${event.error}`)
    }

    recognition.onend = () => {
      // Auto-restart if user hasn't clicked stop
      if (wantsRecordingRef.current) {
        try {
          recognition.start()
        } catch {
          wantsRecordingRef.current = false
          recognitionRef.current = null
          setIsRecording(false)
        }
        return
      }
      recognitionRef.current = null
      setIsRecording(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsRecording(true)
    setError(null)
  }, [])

  const stopRecording = useCallback(() => {
    wantsRecordingRef.current = false
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      // onend will fire and clean up since wantsRecording is false
    }
  }, [])

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }, [isRecording, startRecording, stopRecording])

  // ── AI Generation (en arrière-plan — peut quitter la page) ──

  const isGeneratingFromContext = docGen?.generatingDocIds.has(docId) ?? false
  const isGenerating = isGeneratingFromContext

  const handleGenerate = useCallback(() => {
    if (!prompt.trim() || isGenerating || !docGen) return

    setError(null)
    setAiMessage(null)

    if (isRecording) stopRecording()

    const sentPrompt = prompt.trim()
    onGeneratingChange?.(true)

    docGen.startGeneration({
      docId,
      prompt: sentPrompt,
      collectionIds: effectiveCollectionIds,
      docType,
    })

    setPrompt("")

    const entry: HistoryEntry = {
      prompt: sentPrompt,
      response: "Génération en cours… Vous pouvez quitter la page.",
      timestamp: Date.now(),
    }
    const updated = [entry, ...history].slice(0, MAX_HISTORY)
    setHistory(updated)
    saveHistory(docId, updated)
  }, [
    prompt,
    isGenerating,
    isRecording,
    stopRecording,
    docId,
    effectiveCollectionIds,
    docType,
    history,
    onGeneratingChange,
    docGen,
  ])

  // Mettre à jour l'entrée d'historique quand la génération se termine (si on est resté sur la page)
  useEffect(() => {
    if (!isGeneratingFromContext && history[0]?.response === "Génération en cours… Vous pouvez quitter la page.") {
      setHistory((prev) =>
        prev.map((h, i) =>
          i === 0 ? { ...h, response: "Contenu généré avec succès." } : h
        )
      )
    }
  }, [isGeneratingFromContext, history])

  // Auto-generate from initial prompt once handleGenerate is available
  useEffect(() => {
    if (shouldAutoGenerate.current && prompt && docGen && !isGenerating) {
      shouldAutoGenerate.current = false
      const timer = setTimeout(() => handleGenerate(), 150)
      return () => clearTimeout(timer)
    }
  }, [prompt, docGen, isGenerating, handleGenerate])

  // ── Keyboard handler ──

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey && prompt.trim()) {
        e.preventDefault()
        handleGenerate()
      }
    },
    [handleGenerate, prompt]
  )

  return (
    <div className="sticky bottom-0 z-10 bg-gradient-to-t from-surface via-surface to-transparent pt-6 pb-4">
      {/* Status messages */}
      {error && (
        <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2 animate-fade-in">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">{error}</span>
        </div>
      )}
      {aiMessage && (
        <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2 text-sm text-primary bg-primary/10 border border-primary/20 rounded-lg px-3 py-2 animate-fade-in">
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">{aiMessage}</span>
          <button
            onClick={() => copyToClipboard(aiMessage)}
            className="shrink-0 p-1 rounded hover:bg-primary/10 transition-colors"
            title="Copier la reponse"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-600" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      )}

      {/* History panel */}
      {showHistory && history.length > 0 && (
        <div className="max-w-3xl mx-auto mb-2 bg-card border border-border rounded-xl shadow-elevated overflow-hidden animate-fade-in">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-muted/30">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <History className="h-3.5 w-3.5" />
              Historique des prompts
            </div>
            <button
              onClick={() => setShowHistory(false)}
              className="p-0.5 rounded hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="max-h-48 overflow-auto divide-y divide-border/50">
            {history.map((entry, i) => (
              <button
                key={entry.timestamp + "-" + i}
                className="flex items-start gap-3 w-full px-4 py-2.5 text-left hover:bg-accent/50 transition-colors group"
                onClick={() => {
                  setPrompt(entry.prompt)
                  setShowHistory(false)
                  textareaRef.current?.focus()
                }}
              >
                <Clock className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-foreground truncate">{entry.prompt}</p>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">{entry.response}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span
                    role="button"
                    className="p-1 rounded hover:bg-accent transition-colors"
                    title="Copier le prompt"
                    onClick={(e) => {
                      e.stopPropagation()
                      copyToClipboard(entry.prompt)
                    }}
                  >
                    <Copy className="h-3 w-3 text-muted-foreground" />
                  </span>
                  <RotateCcw className="h-3 w-3 text-muted-foreground" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Prompt bar */}
      <div className="max-w-3xl mx-auto">
        {isEmpty && !isGenerating && (
          <div className="text-center mb-4 animate-fade-in">
            <Sparkles className="h-8 w-8 text-primary/40 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              Decrivez le contenu souhaite ou dictez vos instructions
            </p>
          </div>
        )}

        <div className={`relative bg-card border rounded-xl shadow-elevated overflow-hidden transition-all focus-within:border-primary/30 focus-within:ring-4 focus-within:ring-ring/10 ${isGenerating ? "border-primary/30 ring-4 ring-ring/10" : "border-border"}`}>
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isGenerating}
            placeholder={
              isEmpty
                ? "Ex : Redige un contrat NDA entre deux parties avec les clauses standards…"
                : "Decrivez ce que vous souhaitez ajouter au document…"
            }
            className="w-full text-sm bg-transparent px-4 pt-3 pb-2 pr-28 outline-none resize-none text-foreground placeholder:text-muted-foreground leading-relaxed disabled:opacity-50"
          />

          {/* Bottom row: block buttons + actions */}
          <div className="flex items-center gap-1.5 px-3 pb-2.5">
            {/* Quick add block dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded-md hover:bg-accent transition-colors"
                  disabled={isGenerating}
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Bloc</span>
                  <ChevronUp className="h-3 w-3" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top">
                {BLOCK_TYPES.map((bt) => (
                  <DropdownMenuItem
                    key={bt.type}
                    onClick={() => onAddBlock(bt.type)}
                  >
                    <bt.icon className="h-4 w-4 mr-2 text-muted-foreground" />
                    {bt.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Assistant selector */}
            {assistants.length > 0 && (
              <div className="flex items-center gap-1 text-xs">
                <Bot className="h-3 w-3 text-muted-foreground shrink-0" />
                <select
                  value={selectedAssistantId || ""}
                  onChange={(e) => setSelectedAssistantId(e.target.value)}
                  disabled={isGenerating}
                  className="bg-transparent border-0 text-xs text-muted-foreground hover:text-foreground outline-none cursor-pointer py-1 pr-4 max-w-[120px] sm:max-w-[160px] truncate"
                >
                  {assistants.map((a: Assistant) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* History button */}
            {history.length > 0 && (
              <button
                onClick={() => setShowHistory((v) => !v)}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-colors ${
                  showHistory
                    ? "text-primary bg-primary/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
                disabled={isGenerating}
                title="Historique des prompts"
              >
                <History className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Historique</span>
              </button>
            )}

            <div className="flex-1" />

            {/* Dictation button */}
            <button
              onClick={toggleRecording}
              disabled={isGenerating}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                isRecording
                  ? "bg-destructive text-destructive-foreground animate-pulse"
                  : "bg-muted hover:bg-accent text-muted-foreground hover:text-foreground"
              } disabled:opacity-50`}
              title={isRecording ? "Arreter la dictee" : "Dicter"}
            >
              {isRecording ? (
                <MicOff className="h-3.5 w-3.5" />
              ) : (
                <Mic className="h-3.5 w-3.5" />
              )}
            </button>

            {/* Send button */}
            <Button
              variant="premium"
              size="icon"
              className="h-8 w-8 rounded-full"
              disabled={!prompt.trim() || isGenerating}
              onClick={handleGenerate}
            >
              <SendHorizontal className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {isRecording && (
          <div className="flex items-center justify-center gap-2 mt-2 text-xs text-destructive animate-fade-in">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive" />
            </span>
            Ecoute en cours… Parlez pour dicter le contenu
          </div>
        )}
      </div>
    </div>
  )
}
