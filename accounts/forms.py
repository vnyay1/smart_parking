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


# Lettres arabes valides sur les plaques marocaines
LETTRES_ARABES_PLAQUE = 'ابتثجحخدذرزسشصضطظعغفقكلمنهويآإأ'

# Pattern acceptant lettre arabe OU latine au milieu
PATTERN_PLAQUE = re.compile(
    r'^\d{1,5}'           # 1 à 5 chiffres (numéro véhicule)
    r'-'
    r'(?:[' + LETTRES_ARABES_PLAQUE + r']{1,2}|[A-Z]{1,2})'  # 1-2 lettres arabe OU latine
    r'-'
    r'\d{1,2}$'           # 1 à 2 chiffres (numéro wilaya)
)

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
        widgets = {
            'plaque': forms.TextInput(attrs={
                'class':       'w-full px-3 py-2 rounded-lg border border-slate-200 '
                               'focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue '
                               'outline-none font-mono',
                'placeholder': 'Ex: 12345-ب-6  ou  12345-A-6',
                'dir':         'ltr',   # toujours gauche → droite même avec lettres arabes
            }),
            'marque': forms.TextInput(attrs={
                'class':       'w-full px-3 py-2 rounded-lg border border-slate-200 '
                               'focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue outline-none',
                'placeholder': 'Ex: Renault',
            }),
            'modele': forms.TextInput(attrs={
                'class':       'w-full px-3 py-2 rounded-lg border border-slate-200 '
                               'focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue outline-none',
                'placeholder': 'Ex: Clio',
            }),
            'couleur': forms.TextInput(attrs={
                'class':       'w-full px-3 py-2 rounded-lg border border-slate-200 '
                               'focus:ring-2 focus:ring-brand-blue/30 focus:border-brand-blue outline-none',
                'placeholder': 'Ex: Gris',
            }),
        }

    def clean_plaque(self):
        plaque = self.cleaned_data.get('plaque', '').strip()

        # Normaliser : majuscules pour la partie latine uniquement
        # (ne pas toucher aux lettres arabes)
        def normaliser(p):
            parties = p.split('-')
            if len(parties) == 3:
                parties[1] = parties[1].upper() if re.match(r'^[A-Za-z]+$', parties[1]) else parties[1]
            return '-'.join(parties)

        plaque = normaliser(plaque)

        if not PATTERN_PLAQUE.match(plaque):
            raise forms.ValidationError(
                "Format invalide. "
                "Exemples valides : 12345-ب-6  |  90743-ب-26  |  23242-آ-55  |  13456-A-6"
            )

        # Vérifier unicité
        qs = Vehicule.objects.filter(plaque=plaque)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette plaque est déjà enregistrée.")

        return plaque