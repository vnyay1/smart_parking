from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import Levenshtein
from parking.models import PlaceParking, Reservation, JournalAcces
from vision.plate_recognizer import PlateRecognizer

@api_view(['GET'])
def spots_status(request):
    # Remplace GET /api/spots/status de Flask
    places = PlaceParking.objects.values('id', 'numero', 'statut')
    return Response(list(places))

@api_view(['POST'])
def detect_plate(request):
    # Remplace POST /api/detect-plate de Flask
    image_data = request.data.get('image')
    if not image_data:
        return Response({'error': 'Image manquante'}, status=400)
    recognizer = PlateRecognizer()
    plaque_lue, confiance = recognizer.process_image(image_data)

    # Chercher réservation active (fenêtre ±15 min)
    now = timezone.now()
    fenetre = now - timedelta(minutes=15)
    reservations = Reservation.objects.filter(
        statut='en_attente',
        heure_debut__gte=fenetre,
        heure_debut__lte=now + timedelta(minutes=15),
    )

    # Tolérance Levenshtein ≤ 1
    reservation_trouvee = None
    for r in reservations:
        if Levenshtein.distance(plaque_lue, r.vehicule.plaque) <= 1:
            reservation_trouvee = r; break
        
    if reservation_trouvee:
        reservation_trouvee.statut = 'active'
        reservation_trouvee.heure_entree_reelle = now
        reservation_trouvee.save()
        reservation_trouvee.place.statut = 'occupee'
        reservation_trouvee.place.save()
        JournalAcces.objects.create(
            plaque_detectee=plaque_lue,
            reservation=reservation_trouvee,
            type_evenement='entree',
            score_confiance=confiance
        )
        return Response({'autorise': True, 'place': reservation_trouvee.place.numero})

    JournalAcces.objects.create(plaque_detectee=plaque_lue, type_evenement='refuse')
    return Response({'autorise': False, 'message': 'Aucune réservation valide'})

@api_view(['POST'])
def barrier_open(request):
    # Simulation barrière
    return Response({'status': 'open', 'duration': 5})
