from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # On étend le User Django par héritage
    telephone = models.CharField(max_length=20, blank=True)
    # is_admin existe déjà via is_staff dans AbstractUser

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

class Vehicule(models.Model):
    proprietaire = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='vehicules'
    )
    plaque = models.CharField(max_length=20, unique=True)
    marque = models.CharField(max_length=50, blank=True)
    modele = models.CharField(max_length=50, blank=True)
    couleur = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.plaque} — {self.proprietaire}"
