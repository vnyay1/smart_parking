from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import InscriptionForm, ConnexionForm

def inscription(request):
    if request.user.is_authenticated:
        return redirect('parking:dashboard')  # déjà connecté → rediriger

    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # connecter directement après inscription
            messages.success(request, f"Bienvenue {user.first_name} ! Compte créé avec succès.")
            return redirect('parking:dashboard')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = InscriptionForm()

    return render(request, 'accounts/inscription.html', {'form': form})


def connexion(request):
    if request.user.is_authenticated:
        return redirect('parking:dashboard')

    if request.method == 'POST':
        form = ConnexionForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Bon retour, {user.first_name} !")
            # Rediriger vers la page demandée si ?next=... existe
            next_url = request.GET.get('next', 'parking:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Identifiants incorrects.")
    else:
        form = ConnexionForm()

    return render(request, 'accounts/connexion.html', {'form': form})


@login_required
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect('accounts:connexion')