import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Placeholder from "@tiptap/extension-placeholder"
import { useEffect, useRef } from "react"
import { normalizeProseMirror } from "@/lib/prosemirror"
import { Button } from "@/components/ui/button"
import {
  Bold,
  Italic,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Quote,
} from "lucide-react"

interface TiptapCanvasProps {
  blockId: string
  content: Record<string, unknown>
  onChange: (content: Record<string, unknown>) => void
  editable?: boolean
  placeholder?: string
}

export function TiptapCanvas({
  blockId: _blockId,
  content,
  onChange,
  editable = true,
  placeholder = "Commencez a ecrire...",
}: TiptapCanvasProps) {
  const normalizedContent = normalizeProseMirror(content)
  // Guard to prevent onUpdate from firing during programmatic setContent
  const isSyncingRef = useRef(false)
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder }),
    ],
    content: normalizedContent as Record<string, unknown>,
    editable,
    onUpdate: ({ editor }) => {
      if (isSyncingRef.current) return
      onChange(editor.getJSON() as Record<string, unknown>)
    },
  })

  // Sync external content changes (e.g., from AI patches)
  useEffect(() => {
    if (editor && content) {
      const normalized = normalizeProseMirror(content)
      const currentJSON = JSON.stringify(editor.getJSON())
      const newJSON = JSON.stringify(normalized)
      if (currentJSON !== newJSON) {
        isSyncingRef.current = true
        editor.commands.setContent(normalized as Record<string, unknown>)
        isSyncingRef.current = false
      }
    }
  }, [content]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!editor) return null

  return (
    <div className="rounded-[var(--radius)] border border-border bg-card shadow-soft overflow-hidden">
      {editable && (
        <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => editor.chain().focus().toggleBold().run()}
            data-active={editor.isActive("bold")}
          >
            <Bold className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            data-active={editor.isActive("italic")}
          >
            <Italic className="h-3.5 w-3.5" />
          </Button>
          <div className="w-px h-4 bg-border mx-1" />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 1 }).run()
            }
            data-active={editor.isActive("heading", { level: 1 })}
          >
            <Heading1 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 2 }).run()
            }
            data-active={editor.isActive("heading", { level: 2 })}
          >
            <Heading2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() =>
              editor.chain().focus().toggleHeading({ level: 3 }).run()
            }
            data-active={editor.isActive("heading", { level: 3 })}
          >
            <Heading3 className="h-3.5 w-3.5" />
          </Button>
          <div className="w-px h-4 bg-border mx-1" />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            data-active={editor.isActive("bulletList")}
          >
            <List className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            data-active={editor.isActive("orderedList")}
          >
            <ListOrdered className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            data-active={editor.isActive("blockquote")}
          >
            <Quote className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
      <EditorContent
        editor={editor}
        className="prose prose-zinc prose-sm max-w-none px-4 py-3 min-h-[80px] prose-p:leading-relaxed focus-within:outline-none [&_.ProseMirror]:outline-none [&_.ProseMirror_p.is-editor-empty:first-child::before]:text-muted-foreground [&_.ProseMirror_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)] [&_.ProseMirror_p.is-editor-empty:first-child::before]:float-left [&_.ProseMirror_p.is-editor-empty:first-child::before]:pointer-events-none [&_.ProseMirror_p.is-editor-empty:first-child::before]:h-0"
      />
    </div>
  )
}
