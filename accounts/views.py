from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .forms import InscriptionForm, ConnexionForm, VehiculeForm
from .models import Vehicule

def inscription(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "Veuillez vous authentifier de nouveau pour continuer.")

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
        logout(request)
        messages.info(request, "Session précédente fermée. Veuillez vous reconnecter.")

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

# ── Véhicules ─────────────────────────────────────────────────────

@login_required
def liste_vehicules(request):
    """Liste tous les véhicules de l'utilisateur connecté."""
    vehicules = Vehicule.objects.filter(proprietaire=request.user)
    return render(request, 'accounts/vehicules.html', {'vehicules': vehicules})


@login_required
def ajouter_vehicule(request):
    """Ajoute un nouveau véhicule au compte de l'utilisateur."""
    if request.method == 'POST':
        form = VehiculeForm(request.POST)
        if form.is_valid():
            vehicule = form.save(commit=False)
            vehicule.proprietaire = request.user   # lier au user connecté
            vehicule.save()
            messages.success(request, f"Véhicule {vehicule.plaque} ajouté avec succès.")
            return redirect('accounts:liste_vehicules')
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = VehiculeForm()

    return render(request, 'accounts/vehicule_form.html', {
        'form':  form,
        'titre': 'Ajouter un véhicule',
    })


@login_required
def modifier_vehicule(request, pk):
    """Modifie un véhicule appartenant à l'utilisateur connecté."""
    vehicule = get_object_or_404(Vehicule, pk=pk, proprietaire=request.user)

    if request.method == 'POST':
        form = VehiculeForm(request.POST, instance=vehicule)
        if form.is_valid():
            form.save()
            messages.success(request, f"Véhicule {vehicule.plaque} mis à jour.")
            return redirect('accounts:liste_vehicules')
        messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = VehiculeForm(instance=vehicule)

    return render(request, 'accounts/vehicule_form.html', {
        'form':     form,
        'vehicule': vehicule,
        'titre':    'Modifier le véhicule',
    })


@login_required
@require_POST
def supprimer_vehicule(request, pk):
    """Supprime un véhicule — bloqué si une réservation active existe."""
    vehicule = get_object_or_404(Vehicule, pk=pk, proprietaire=request.user)

    # Vérifier qu'aucune réservation active ne dépend de ce véhicule
    reservations_actives = vehicule.reservations.filter(
        statut__in=['en_attente', 'active']
    )
    if reservations_actives.exists():
        messages.error(
            request,
            f"Impossible de supprimer {vehicule.plaque} : "
            f"{reservations_actives.count()} réservation(s) active(s) en cours."
        )
        return redirect('accounts:liste_vehicules')

    plaque = vehicule.plaque
    vehicule.delete()
    messages.success(request, f"Véhicule {plaque} supprimé.")
    return redirect('accounts:liste_vehicules')