from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import PlaceParking, Reservation
from .forms import ReservationForm
from accounts.models import Vehicule
from accounts.forms import VehiculeForm
from django.utils import timezone
from datetime import date

@login_required
def dashboard(request):
    if request.method == 'POST' and request.POST.get('action') == 'add_vehicle':
        vehicle_form = VehiculeForm(request.POST)
        if vehicle_form.is_valid():
            vehicle = vehicle_form.save(commit=False)
            vehicle.proprietaire = request.user
            vehicle.save()
            messages.success(request, "Véhicule ajouté avec succès.")
            return redirect('parking:dashboard')
        messages.error(request, "Impossible d'ajouter le véhicule. Vérifiez le formulaire.")
    else:
        vehicle_form = VehiculeForm()

    now = timezone.now()
    places = PlaceParking.objects.all().order_by('numero')
    free_spots = places.filter(statut=PlaceParking.Statut.LIBRE).count()
    taken_spots = places.filter(statut=PlaceParking.Statut.OCCUPEE).count()
    total_spots = places.count()
    occupancy_percent = int((taken_spots / total_spots) * 100) if total_spots else 0

    active_reservation = Reservation.objects.filter(
        utilisateur=request.user,
        statut=Reservation.Statut.ACTIVE
    ).select_related('place', 'vehicule').order_by('heure_fin').first()

    upcoming_reservations = Reservation.objects.filter(
        utilisateur=request.user,
        statut=Reservation.Statut.EN_ATTENTE,
        heure_fin__gte=now
    ).select_related('place', 'vehicule').order_by('heure_debut')[:5]

    history_qs = Reservation.objects.filter(
        utilisateur=request.user,
        statut__in=[Reservation.Statut.TERMINEE, Reservation.Statut.ANNULEE, Reservation.Statut.EXPIREE]
    ).select_related('place').order_by('-heure_fin')[:5]

    history = [
        {
            'date': item.heure_debut,
            'spot': item.place.numero,
            'duration': f"{item.get_duree_prevue_minutes()} min",
            'status': item.get_statut_display(),
        }
        for item in history_qs
    ]

    vehicles = Vehicule.objects.filter(proprietaire=request.user).order_by('-id')

    return render(request, 'parking/dashboard.html', {
        'active_reservation': active_reservation,
        'upcoming_reservations': upcoming_reservations,
        'free_spots': free_spots,
        'taken_spots': taken_spots,
        'occupancy_percent': occupancy_percent,
        'history': history,
        'vehicles': vehicles,
        'vehicle_form': vehicle_form,
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
    reservations_qs = Reservation.objects.filter(
        utilisateur=request.user
    ).select_related('place', 'vehicule').order_by('-created_at')

    status = request.GET.get('status', '').strip()
    selected_date = request.GET.get('date', '').strip()

    status_map = {
        'active': Reservation.Statut.ACTIVE,
        'upcoming': Reservation.Statut.EN_ATTENTE,
        'cancelled': Reservation.Statut.ANNULEE,
    }
    if status in status_map:
        reservations_qs = reservations_qs.filter(statut=status_map[status])

    parsed_date = None
    if selected_date:
        try:
            parsed_date = date.fromisoformat(selected_date)
            reservations_qs = reservations_qs.filter(heure_debut__date=parsed_date)
        except ValueError:
            messages.error(request, "Date invalide. Utilisez le format YYYY-MM-DD.")

    reservations = list(reservations_qs)
    has_filters = bool(status or selected_date)
    no_results = has_filters and len(reservations) == 0
    if no_results:
        messages.error(request, "Aucune réservation ne correspond aux critères de filtre.")

    return render(request, 'parking/mes_reservations.html', {
        'reservations': reservations,
        'selected_status': status,
        'selected_date': selected_date,
        'no_results': no_results,
    })


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

