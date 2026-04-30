from  django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import PlaceParking, Reservation
from .forms import ReservationForm
import json

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
