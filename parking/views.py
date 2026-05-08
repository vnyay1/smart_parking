from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import PlaceParking, Reservation
from .forms import ReservationForm
from accounts.models import Vehicule

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


@login_required
def disponibilite(request):
    places = PlaceParking.objects.all().order_by('etage', 'numero')
    zones_map = {}

    for place in places:
        zone_name = place.etage
        if zone_name not in zones_map:
            zones_map[zone_name] = []

        if place.statut == PlaceParking.Statut.LIBRE:
            state = 'free'
        elif place.statut == PlaceParking.Statut.RESERVEE:
            state = 'reserved'
        else:
            state = 'taken'

        zones_map[zone_name].append({
            'label': place.numero,
            'state': state,
        })

    zones = [{'name': zone, 'spots': spots} for zone, spots in sorted(zones_map.items())]

    context = {
        'zones': zones,
        'total_spots': places.count(),
        'free_spots': places.filter(statut=PlaceParking.Statut.LIBRE).count(),
        'reserved_spots': places.filter(statut=PlaceParking.Statut.RESERVEE).count(),
        'taken_spots': places.filter(statut=PlaceParking.Statut.OCCUPEE).count(),
    }
    return render(request, 'parking/disponibilite.html', context)


@login_required
def historique(request):
    reservations = Reservation.objects.filter(
        utilisateur=request.user,
        statut__in=[Reservation.Statut.TERMINEE, Reservation.Statut.ANNULEE, Reservation.Statut.EXPIREE]
    ).select_related('place').order_by('-heure_fin')

    history = []
    for reservation in reservations:
        history.append({
            'date': reservation.heure_debut,
            'spot': reservation.place.numero,
            'duration': f"{reservation.get_duree_prevue_minutes()} min",
            'status': 'completed' if reservation.statut == Reservation.Statut.TERMINEE else 'cancelled',
            'status_label': reservation.get_statut_display(),
        })

    return render(request, 'parking/historique.html', {'history': history})


@login_required
def profil(request):
    vehicles = Vehicule.objects.filter(proprietaire=request.user).order_by('id')

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.telephone = request.POST.get('phone', '').strip()
        request.user.save()

        for index, vehicle in enumerate(vehicles, start=1):
            key = f'plate_{index}'
            new_plate = request.POST.get(key, '').strip().upper()
            if new_plate and new_plate != vehicle.plaque:
                if Vehicule.objects.exclude(pk=vehicle.pk).filter(plaque=new_plate).exists():
                    messages.error(request, f"La plaque {new_plate} existe déjà.")
                else:
                    vehicle.plaque = new_plate
                    vehicle.save(update_fields=['plaque'])

        new_plate = request.POST.get('new_plate', '').strip().upper()
        if new_plate:
            if Vehicule.objects.filter(plaque=new_plate).exists():
                messages.error(request, f"La plaque {new_plate} existe déjà.")
            else:
                Vehicule.objects.create(proprietaire=request.user, plaque=new_plate)
                messages.success(request, "Nouveau véhicule ajouté.")

        messages.success(request, "Profil mis à jour.")
        return redirect('parking:profile')

    return render(request, 'parking/profil.html', {'vehicles': vehicles})

