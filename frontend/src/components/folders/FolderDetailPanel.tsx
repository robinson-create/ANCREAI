import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useSearchParams } from "react-router-dom"
import {
  X,
  MessageSquare,
  FileText,
  Mail,
  Loader2,
  Trash2,
  Pencil,
  ExternalLink,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { foldersApi } from "@/api/folders"
import type { FolderItem } from "@/types"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useToast } from "@/hooks/use-toast"

const TABS = [
  { value: "all", label: "Tout" },
  { value: "conversation", label: "Conversations" },
  { value: "document", label: "Documents" },
  { value: "email_thread", label: "Emails" },
] as const

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 1) return "À l'instant"
  if (diffMins < 60) return `Il y a ${diffMins} min`
  if (diffHours < 24) return `Il y a ${diffHours}h`
  if (diffDays < 7) return `Il y a ${diffDays}j`
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
}

function itemIcon(type: FolderItem["item_type"]) {
  switch (type) {
    case "conversation":
      return MessageSquare
    case "document":
      return FileText
    case "email_thread":
      return Mail
    default:
      return FileText
  }
}

interface FolderDetailPanelProps {
  folderId: string
  onClose: () => void
}

export function FolderDetailPanel({ folderId, onClose }: FolderDetailPanelProps) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]["value"]>("all")
  const [editOpen, setEditOpen] = useState(false)

  const assistantParam = searchParams.get("assistant")
  const accountIdParam = searchParams.get("account_id")

  const { data: folder, isLoading: folderLoading } = useQuery({
    queryKey: ["folder", folderId],
    queryFn: () => foldersApi.get(folderId),
    enabled: !!folderId,
  })

  const { data: items = [], isLoading: itemsLoading } = useQuery({
    queryKey: ["folder-items", folderId, activeTab],
    queryFn: () =>
      foldersApi.listItems(
        folderId,
        activeTab === "all" ? undefined : { item_type: activeTab }
      ),
    enabled: !!folderId,
  })

  const updateMutation = useMutation({
    mutationFn: ({ name }: { name: string }) =>
      foldersApi.update(folderId, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      queryClient.invalidateQueries({ queryKey: ["folder", folderId] })
      toast({ title: "Dossier mis à jour" })
      setEditOpen(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => foldersApi.delete(folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] })
      toast({ title: "Dossier supprimé" })
      onClose()
    },
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: string) =>
      foldersApi.removeItem(folderId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folder-items", folderId] })
      queryClient.invalidateQueries({ queryKey: ["folder", folderId] })
    },
  })

  const handleOpenItem = (item: FolderItem) => {
    if (item.item_type === "conversation") {
      navigate(
        `/app/search?assistant=${assistantParam || ""}&conversation=${item.item_id}`
      )
      onClose()
    } else if (item.item_type === "document") {
      navigate(`/app/documents/${item.item_id}`)
      onClose()
    } else if (item.item_type === "email_thread") {
      navigate(`/app/email?account_id=${accountIdParam || ""}&thread=${item.item_id}`)
      onClose()
    }
  }

  if (!folder && !folderLoading) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-black/30 animate-fade-in"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md bg-background shadow-xl animate-slide-in-right flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2 min-w-0">
            {folder?.color && (
              <div
                className="w-2 h-8 rounded-full shrink-0"
                style={{ backgroundColor: folder.color }}
              />
            )}
            <div className="min-w-0">
              {editOpen ? (
                <Input
                  defaultValue={folder?.name}
                  className="h-8"
                  onBlur={(e) => {
                    const v = e.target.value.trim()
                    if (v && v !== folder?.name) {
                      updateMutation.mutate({ name: v })
                    }
                    setEditOpen(false)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.currentTarget.blur()
                    }
                  }}
                  autoFocus
                />
              ) : (
                <h2 className="font-semibold truncate">{folder?.name}</h2>
              )}
            </div>
            {!editOpen && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex gap-1 p-2 border-b overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap ${
                activeTab === tab.value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted/50 hover:bg-muted text-muted-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-3">
          {itemsLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              Aucun élément dans ce dossier.
            </div>
          ) : (
            <div className="space-y-1">
              {items.map((item) => {
                const Icon = itemIcon(item.item_type)
                return (
                  <div
                    key={item.id}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent"
                  >
                    <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center shrink-0">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <button
                      onClick={() => handleOpenItem(item)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <div className="text-sm font-medium truncate">
                        {item.title}
                      </div>
                      {item.subtitle && (
                        <div className="text-xs text-muted-foreground truncate">
                          {item.subtitle}
                        </div>
                      )}
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        {formatRelativeDate(item.date)}
                      </div>
                    </button>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => handleOpenItem(item)}
                      >
                        <ExternalLink className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive"
                        onClick={() => removeItemMutation.mutate(item.id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
