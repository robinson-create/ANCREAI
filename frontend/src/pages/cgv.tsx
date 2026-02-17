export function CGVPage() {
  return (
    <div className="py-20">
      <div className="container max-w-3xl">
        <h1 className="text-4xl font-bold tracking-tight">
          Conditions Générales de Vente
        </h1>
        <p className="mt-4 text-muted-foreground">
          Dernière mise à jour : {new Date().toLocaleDateString("fr-FR")}
        </p>

        <div className="prose prose-gray mt-12 max-w-none dark:prose-invert">
          <h2>1. Objet</h2>
          <p>
            Les présentes Conditions Générales de Vente (CGV) régissent les
            relations contractuelles entre Mecano Man et ses utilisateurs dans
            le cadre de l'utilisation de la plateforme de création d'assistants
            IA.
          </p>

          <h2>2. Services</h2>
          <p>
            Mecano Man propose une plateforme permettant de créer et gérer des
            assistants IA personnalisés. Les services incluent :
          </p>
          <ul>
            <li>Création et configuration d'assistants IA</li>
            <li>Import de documents contextuels</li>
            <li>Interface de conversation</li>
            <li>Stockage sécurisé des données</li>
          </ul>

          <h2>3. Abonnements et tarifs</h2>
          <p>
            Les tarifs des différentes formules d'abonnement sont indiqués sur
            la page Pricing. Les prix sont exprimés en euros TTC.
          </p>
          <p>
            L'abonnement est mensuel et renouvelé automatiquement sauf
            résiliation par l'utilisateur.
          </p>

          <h2>4. Période d'essai</h2>
          <p>
            Une période d'essai gratuite de 10 jours est proposée pour les
            nouveaux utilisateurs. À l'issue de cette période, l'utilisateur
            devra souscrire à un abonnement payant pour continuer à utiliser le
            service.
          </p>

          <h2>5. Données personnelles</h2>
          <p>
            Les données personnelles collectées sont traitées conformément au
            Règlement Général sur la Protection des Données (RGPD). L'utilisateur
            dispose d'un droit d'accès, de rectification et de suppression de ses
            données.
          </p>

          <h2>6. Propriété intellectuelle</h2>
          <p>
            L'utilisateur conserve la propriété de ses documents et contenus
            importés sur la plateforme. Mecano Man s'engage à ne pas utiliser ces
            données à des fins autres que le fonctionnement du service.
          </p>

          <h2>7. Responsabilité</h2>
          <p>
            Mecano Man s'engage à mettre en œuvre tous les moyens nécessaires
            pour assurer la continuité et la qualité du service. Toutefois, la
            responsabilité de Mecano Man ne saurait être engagée en cas de force
            majeure ou de dysfonctionnement imputable à un tiers.
          </p>

          <h2>8. Résiliation</h2>
          <p>
            L'utilisateur peut résilier son abonnement à tout moment depuis son
            espace personnel. La résiliation prend effet à la fin de la période
            de facturation en cours.
          </p>

          <h2>9. Modification des CGV</h2>
          <p>
            Mecano Man se réserve le droit de modifier les présentes CGV.
            L'utilisateur sera informé de toute modification par email au moins
            30 jours avant son entrée en vigueur.
          </p>

          <h2>10. Droit applicable</h2>
          <p>
            Les présentes CGV sont soumises au droit français. Tout litige
            relatif à leur interprétation ou à leur exécution relève de la
            compétence exclusive des tribunaux français.
          </p>

          <h2>Contact</h2>
          <p>
            Pour toute question relative aux présentes CGV, vous pouvez nous
            contacter à l'adresse suivante :{" "}
            <a href="mailto:contact@mecano-man.com">contact@mecano-man.com</a>
          </p>
        </div>
      </div>
    </div>
  )
}
