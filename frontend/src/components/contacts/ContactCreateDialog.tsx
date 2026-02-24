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
import type { ContactCreateData } from "@/api/contacts"

const schema = z.object({
  primary_email: z.string().email("Email invalide").min(1, "L'email est requis"),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  phone: z.string().optional(),
  company_name: z.string().optional(),
  title: z.string().optional(),
  contact_type: z.enum([
    "client",
    "prospect",
    "partenaire",
    "fournisseur",
    "candidat",
    "interne",
    "autre",
  ]).default("autre"),
  notes: z.string().optional(),
})

type FormData = z.infer<typeof schema>

interface ContactCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ContactCreateData) => Promise<void>
}

export function ContactCreateDialog({
  open,
  onOpenChange,
  onSubmit,
}: ContactCreateDialogProps) {
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
      contact_type: "autre",
    },
  })

  const contactType = watch("contact_type")

  useEffect(() => {
    if (open) {
      reset({
        primary_email: "",
        first_name: "",
        last_name: "",
        phone: "",
        company_name: "",
        title: "",
        contact_type: "autre",
        notes: "",
      })
    }
  }, [open, reset])

  const handleFormSubmit = async (data: FormData) => {
    await onSubmit({
      primary_email: data.primary_email,
      first_name: data.first_name || undefined,
      last_name: data.last_name || undefined,
      phone: data.phone || undefined,
      title: data.title || undefined,
      contact_type: data.contact_type,
      notes: data.notes || undefined,
      source: "manual",
    })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouveau contact</DialogTitle>
          <DialogDescription>
            Ajoutez un nouveau contact à votre CRM.
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
              <Label htmlFor="primary_email">
                Email <span className="text-destructive">*</span>
              </Label>
              <Input
                id="primary_email"
                type="email"
                placeholder="jean.dupont@example.com"
                {...register("primary_email")}
              />
              {errors.primary_email && (
                <p className="text-sm text-destructive">
                  {errors.primary_email.message}
                </p>
              )}
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
              <Label htmlFor="company_name">Entreprise</Label>
              <Input
                id="company_name"
                placeholder="Acme Corp"
                {...register("company_name")}
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
              Créer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
