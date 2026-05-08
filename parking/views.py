from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PlaceParking, Reservation
from .forms import ReservationForm

@login_required            
def dashboard(request):
    places = PlaceParking.objects.all().order_by('numero')
    reservations = Reservation.objects.filter(
        utilisateur=request.user, statut='en_attente'
    ).order_by('heure_debut')
    return render(request, 'parking/dashboard.html', {
        'places': places,
        'reservations': reservations,
    })

@login_required
def creer_reservation(request):
    if request.method == 'POST':
        form = ReservationForm(request.POST, user=request.user)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.utilisateur = request.user
            reservation.save()
            reservation.place.statut = 'reservee'
            reservation.place.save()
            return redirect('parking:dashboard')
    else:
        form = ReservationForm(user=request.user)
    return render(request, 'parking/reservation.html', {'form': form})


@login_required
def detail_reservation(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, utilisateur=request.user)
    return render(request, 'parking/detail_reservation.html', {'reservation': reservation})


@login_required
@require_POST
def annuler_reservation(request, pk):
    reservation = get_object_or_404(
        Reservation, pk=pk,
        utilisateur=request.user,
        statut__in=['en_attente', 'active']
    )
    reservation.annuler()
    messages.info(request, f"Réservation #{pk} annulée — la place est maintenant libre.")
    return redirect('parking:dashboard')


@login_required
def mes_reservations(request):
    reservations = Reservation.objects.filter(
        utilisateur=request.user
    ).select_related('place', 'vehicule').order_by('-created_at')

    return render(request, 'parking/mes_reservations.html', {'reservations': reservations})

