from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Vehicule
import re

class InscriptionForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, label="Prénom")
    last_name = forms.CharField(max_length=50, label="Nom")

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ConnexionForm(AuthenticationForm):
    # AuthenticationForm gère déjà username + password
    # On peut juste personnaliser les labels si besoin
    username = forms.CharField(label="Nom d'utilisateur")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)

class VehiculeForm(forms.ModelForm):

    class Meta:
        model  = Vehicule
        fields = ['plaque', 'marque', 'modele', 'couleur']
        labels = {
            'plaque':  'Plaque d\'immatriculation',
            'marque':  'Marque',
            'modele':  'Modèle',
            'couleur': 'Couleur',
        }

    def clean_plaque(self):
        plaque = self.cleaned_data['plaque'].strip().upper()

        # Format plaque marocaine : 12345-A-6
        pattern = r'^\d{1,5}-[A-Z]{1,3}-\d{1,2}$'
        if not re.match(pattern, plaque):
            raise forms.ValidationError(
                "Format invalide. Exemple valide : 12345-A-6"
            )

        # Vérifier unicité (sauf si on modifie le même véhicule)
        qs = Vehicule.objects.filter(plaque=plaque)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette plaque est déjà enregistrée.")

        return plaque