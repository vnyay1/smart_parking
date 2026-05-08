from django import forms
from django.utils import timezone
from .models import Reservation, PlaceParking
from accounts.models import Vehicule


class ReservationForm(forms.ModelForm):

    class Meta:
        model  = Reservation
        fields = ['place', 'vehicule', 'heure_debut', 'heure_fin']
        widgets = {
            'heure_debut': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'heure_fin':   forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')          # l'utilisateur connecté
        super().__init__(*args, **kwargs)

        # N'afficher que les places libres
        self.fields['place'].queryset = PlaceParking.objects.filter(statut=PlaceParking.Statut.LIBRE)

        # N'afficher que les véhicules de l'utilisateur connecté
        self.fields['vehicule'].queryset = Vehicule.objects.filter(proprietaire=self.user)

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('heure_debut')
        fin   = cleaned.get('heure_fin')
        place = cleaned.get('place')

        if debut and fin:
            # Vérifier que la date est dans le futur
            if debut <= timezone.now():
                self.add_error('heure_debut', "L'heure de début doit être dans le futur.")

            # Vérifier cohérence début < fin
            if fin <= debut:
                self.add_error('heure_fin', "L'heure de fin doit être après l'heure de début.")

            # Vérifier durée minimale (15 min)
            elif (fin - debut).total_seconds() < 900:
                self.add_error('heure_fin', "La durée minimale de réservation est de 15 minutes.")

            # Vérifier conflit avec une réservation existante
            if place and Reservation.verifier_conflit(place, debut, fin):
                self.add_error('place', "Cette place est déjà réservée sur ce créneau.")

        return cleaned