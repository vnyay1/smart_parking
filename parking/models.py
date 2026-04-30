from django.db import models
from django.conf import settings
from django.utils import timezone

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

    def liberer(self):
        self.statut = self.Statut.LIBRE
        self.save()
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

    def est_dans_fenetre(self, tolerance_min=15):
        from datetime import timedelta
        now = timezone.now()
        return (self.heure_debut - timedelta(minutes=tolerance_min)) <= now
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