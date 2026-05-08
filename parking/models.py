from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class PlaceParking(models.Model):
    class Statut(models.TextChoices):
        LIBRE = 'libre', 'Libre'
        RESERVEE = 'reservee', 'Réservée'
        OCCUPEE = 'occupee', 'Occupée'

    numero = models.PositiveIntegerField(unique=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.LIBRE
    )
    etage = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['numero']
        verbose_name = 'Place de parking'
        verbose_name_plural = 'Places de parking'

    def __str__(self):
        return f"Place {self.numero} — {self.get_statut_display()}"

    def est_disponible(self):
        return self.statut == self.Statut.LIBRE

    def reserver(self):
        self.statut = self.Statut.RESERVEE
        self.save(update_fields=['statut', 'updated_at'])

    def occuper(self):
        self.statut = self.Statut.OCCUPEE
        self.save(update_fields=['statut', 'updated_at'])

    def liberer(self):
        self.statut = self.Statut.LIBRE
        self.save(update_fields=['statut', 'updated_at'])
class Reservation(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACTIVE = 'active', 'Active'
        EXPIREE = 'expiree', 'Expirée'
        ANNULEE = 'annulee', 'Annulée'
        TERMINEE = 'terminee', 'Terminée'

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    place = models.ForeignKey(PlaceParking, on_delete=models.PROTECT)
    vehicule = models.ForeignKey('accounts.Vehicule', on_delete=models.PROTECT)
    heure_debut = models.DateTimeField()
    heure_fin = models.DateTimeField()
    heure_entree_reelle = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Réservation'

    def __str__(self):
        return f"Réservation #{self.pk} — {self.utilisateur} — Place {self.place.numero}"

    # ── Méthodes métier ───────────────────────────────────────────

    def est_dans_fenetre_arrivee(self, tolerance_min=15):
        """True si l'heure actuelle est dans la fenêtre de ±15 min autour de heure_debut."""
        now = timezone.now()
        return (self.heure_debut - timedelta(minutes=tolerance_min)) <= now <= (self.heure_debut + timedelta(minutes=tolerance_min))

    def get_duree_prevue_minutes(self):
        delta = self.heure_fin - self.heure_debut
        return int(delta.total_seconds() / 60)

    def annuler(self):
        self.statut = self.Statut.ANNULEE
        self.save(update_fields=['statut'])
        self.place.liberer()

    def confirmer_entree(self):
        self.statut = self.Statut.ACTIVE
        self.heure_entree_reelle = timezone.now()
        self.save(update_fields=['statut', 'heure_entree_reelle'])
        self.place.occuper()

    def terminer(self):
        self.statut = self.Statut.TERMINEE
        self.save(update_fields=['statut'])
        self.place.liberer()

    @staticmethod
    def verifier_conflit(place, heure_debut, heure_fin, exclude_id=None):
        """
        Retourne True si une réservation active existe déjà
        sur cette place pour ce créneau.
        """
        qs = Reservation.objects.filter(
            place=place,
            statut__in=[Reservation.Statut.EN_ATTENTE, Reservation.Statut.ACTIVE],
            heure_debut__lt=heure_fin,
            heure_fin__gt=heure_debut,
        )
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        return qs.exists()
    
class JournalAcces(models.Model):
    class TypeEvenement(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'
        REFUSE = 'refuse', 'Refusé'

    plaque_detectee = models.CharField(max_length=20)
    reservation = models.ForeignKey(Reservation, null=True, blank=True, on_delete=models.SET_NULL)
    type_evenement = models.CharField(max_length=10, choices=TypeEvenement.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    score_confiance = models.FloatField(default=0.0)
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Journal d\'accès'
        verbose_name_plural = 'Journal des accès'

    def __str__(self):
        return f"{self.get_type_evenement_display()} — {self.plaque_detectee} — {self.timestamp:%d/%m/%Y %H:%M}"