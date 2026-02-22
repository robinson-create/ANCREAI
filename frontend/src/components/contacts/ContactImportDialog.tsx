import { useState, useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2, Mail, CheckCircle2, AlertCircle } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { mailApi } from "@/api/mail"
import type { ContactImportRequest, ContactImportReport } from "@/api/contacts"

const schema = z.object({
  mail_account_id: z.string().min(1, "Sélectionnez un compte email"),
  date_range_days: z.number().int().min(1).max(365).default(90),
})

type FormData = z.infer<typeof schema>

interface ContactImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ContactImportRequest) => Promise<ContactImportReport>
}

export function ContactImportDialog({
  open,
  onOpenChange,
  onSubmit,
}: ContactImportDialogProps) {
  const [importResult, setImportResult] = useState<ContactImportReport | null>(
    null
  )
  const [importError, setImportError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      date_range_days: 90,
    },
  })

  const mailAccountId = watch("mail_account_id")

  const { data: mailAccounts = [], isLoading: isLoadingAccounts } = useQuery({
    queryKey: ["mailAccounts"],
    queryFn: () => mailApi.listAccounts(),
    enabled: open,
  })

  useEffect(() => {
    if (open) {
      reset({ mail_account_id: "", date_range_days: 90 })
      setImportResult(null)
      setImportError(null)
    }
  }, [open, reset])

  const handleFormSubmit = async (data: FormData) => {
    try {
      setImportError(null)
      const result = await onSubmit({
        mail_account_id: data.mail_account_id,
        date_range_days: data.date_range_days,
      })
      setImportResult(result)
    } catch (err) {
      setImportError(
        err instanceof Error ? err.message : "Erreur lors de l'import"
      )
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setTimeout(() => {
      setImportResult(null)
      setImportError(null)
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Importer des contacts</DialogTitle>
          <DialogDescription>
            Importez automatiquement des contacts depuis vos emails.
          </DialogDescription>
        </DialogHeader>

        {!importResult ? (
          <form onSubmit={handleSubmit(handleFormSubmit)}>
            <div className="space-y-4 py-4">
              {isLoadingAccounts ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : mailAccounts.length === 0 ? (
                <Alert>
                  <Mail className="h-4 w-4" />
                  <AlertDescription>
                    Aucun compte email connecté. Connectez d'abord un compte
                    email dans la section Emails.
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="mail_account_id">
                      Compte email <span className="text-destructive">*</span>
                    </Label>
                    <Select
                      value={mailAccountId}
                      onValueChange={(value) =>
                        setValue("mail_account_id", value)
                      }
                    >
                      <SelectTrigger id="mail_account_id">
                        <SelectValue placeholder="Sélectionnez un compte" />
                      </SelectTrigger>
                      <SelectContent>
                        {mailAccounts.map((account) => (
                          <SelectItem key={account.id} value={account.id}>
                            <div className="flex items-center gap-2">
                              <Mail className="h-4 w-4" />
                              {account.email_address || account.provider}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.mail_account_id && (
                      <p className="text-sm text-destructive">
                        {errors.mail_account_id.message}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="date_range_days">
                      Période d'import (jours)
                    </Label>
                    <Input
                      id="date_range_days"
                      type="number"
                      min={1}
                      max={365}
                      placeholder="90"
                      {...register("date_range_days", { valueAsNumber: true })}
                    />
                    <p className="text-xs text-muted-foreground">
                      Nombre de jours à scanner (max 365)
                    </p>
                    {errors.date_range_days && (
                      <p className="text-sm text-destructive">
                        {errors.date_range_days.message}
                      </p>
                    )}
                  </div>

                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="text-xs">
                      L'import analysera les expéditeurs et destinataires de vos
                      emails pour créer automatiquement des contacts. Les
                      adresses no-reply et newsletters seront ignorées.
                    </AlertDescription>
                  </Alert>
                </>
              )}

              {importError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{importError}</AlertDescription>
                </Alert>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Annuler
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || mailAccounts.length === 0}
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Importer
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="space-y-4 py-4">
            <div className="flex items-center gap-3 rounded-lg bg-green-50 p-4 dark:bg-green-950">
              <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
              <div>
                <p className="font-medium text-green-900 dark:text-green-100">
                  Import terminé
                </p>
                <p className="text-sm text-green-700 dark:text-green-300">
                  {importResult.contacts_created} contact(s) créé(s),{" "}
                  {importResult.contacts_updated} mis à jour,{" "}
                  {importResult.contacts_skipped} ignoré(s)
                </p>
              </div>
            </div>

            {importResult.errors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-medium">
                    {importResult.errors.length} erreur(s) détectée(s)
                  </p>
                  <ul className="mt-2 text-xs space-y-1">
                    {importResult.errors.slice(0, 5).map((err, idx) => (
                      <li key={idx}>• {err}</li>
                    ))}
                    {importResult.errors.length > 5 && (
                      <li>
                        ... et {importResult.errors.length - 5} autre(s) erreur(s)
                      </li>
                    )}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              <Button onClick={handleClose}>Fermer</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
