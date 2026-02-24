import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
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
import type { Contact, ContactUpdateData } from "@/api/contacts"

const schema = z.object({
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  phone: z.string().optional(),
  title: z.string().optional(),
  contact_type: z.enum([
    "client",
    "prospect",
    "partenaire",
    "fournisseur",
    "candidat",
    "interne",
    "autre",
  ]).optional(),
  language: z.string().optional(),
  timezone: z.string().optional(),
  country: z.string().optional(),
  city: z.string().optional(),
  notes: z.string().optional(),
})

type FormData = z.infer<typeof schema>

interface ContactEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ContactUpdateData) => Promise<void>
  contact: Contact | null
}

export function ContactEditDialog({
  open,
  onOpenChange,
  onSubmit,
  contact,
}: ContactEditDialogProps) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const contactType = watch("contact_type")

  useEffect(() => {
    if (open && contact) {
      reset({
        first_name: contact.first_name || "",
        last_name: contact.last_name || "",
        phone: contact.phone || "",
        title: contact.title || "",
        contact_type: contact.contact_type as FormData["contact_type"],
        language: contact.language || "",
        timezone: contact.timezone || "",
        country: contact.country || "",
        city: contact.city || "",
        notes: contact.notes || "",
      })
    }
  }, [open, contact, reset])

  const handleFormSubmit = async (data: FormData) => {
    await onSubmit({
      first_name: data.first_name || undefined,
      last_name: data.last_name || undefined,
      phone: data.phone || undefined,
      title: data.title || undefined,
      contact_type: data.contact_type,
      language: data.language || undefined,
      timezone: data.timezone || undefined,
      country: data.country || undefined,
      city: data.city || undefined,
      notes: data.notes || undefined,
    })
    onOpenChange(false)
  }

  if (!contact) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Modifier le contact</DialogTitle>
          <DialogDescription>
            Modifiez les informations de {contact.first_name || ""}{" "}
            {contact.last_name || contact.primary_email}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(handleFormSubmit)}>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">Prénom</Label>
                <Input
                  id="first_name"
                  placeholder="Jean"
                  {...register("first_name")}
                />
                {errors.first_name && (
                  <p className="text-sm text-destructive">
                    {errors.first_name.message}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Nom</Label>
                <Input
                  id="last_name"
                  placeholder="Dupont"
                  {...register("last_name")}
                />
                {errors.last_name && (
                  <p className="text-sm text-destructive">
                    {errors.last_name.message}
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={contact.primary_email} disabled />
              <p className="text-xs text-muted-foreground">
                L'email ne peut pas être modifié
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Téléphone</Label>
              <Input
                id="phone"
                placeholder="+33 6 12 34 56 78"
                {...register("phone")}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="title">Fonction</Label>
              <Input
                id="title"
                placeholder="Directeur Commercial"
                {...register("title")}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="contact_type">Type de contact</Label>
              <Select
                value={contactType}
                onValueChange={(value) =>
                  setValue("contact_type", value as FormData["contact_type"])
                }
              >
                <SelectTrigger id="contact_type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="client">Client</SelectItem>
                  <SelectItem value="prospect">Prospect</SelectItem>
                  <SelectItem value="partenaire">Partenaire</SelectItem>
                  <SelectItem value="fournisseur">Fournisseur</SelectItem>
                  <SelectItem value="candidat">Candidat</SelectItem>
                  <SelectItem value="interne">Interne</SelectItem>
                  <SelectItem value="autre">Autre</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="language">Langue</Label>
                <Input
                  id="language"
                  placeholder="fr"
                  {...register("language")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">Fuseau horaire</Label>
                <Input
                  id="timezone"
                  placeholder="Europe/Paris"
                  {...register("timezone")}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="country">Pays</Label>
                <Input id="country" placeholder="France" {...register("country")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="city">Ville</Label>
                <Input id="city" placeholder="Paris" {...register("city")} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                placeholder="Notes additionnelles..."
                rows={3}
                {...register("notes")}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
