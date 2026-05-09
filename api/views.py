# api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from parking.models import PlaceParking, Reservation, JournalAcces
from vision.reconnaissance import SystemeReconnaissance

# Instance globale — évite de recharger EasyOCR à chaque requête
_systeme = None

def get_systeme():
    global _systeme
    if _systeme is None:
        _systeme = SystemeReconnaissance()
    return _systeme


@api_view(['POST'])
@permission_classes([AllowAny])
def detecter_plaque(request):
    """
    Reçoit une image en base64, lit la plaque, vérifie la réservation.
    Retourne : autorisé ou refusé + détails.
    """
    image_b64 = request.data.get('image')
    if not image_b64:
        return Response({'erreur': 'Champ image manquant.'}, status=400)

    systeme = get_systeme()

    # 1. Lire la plaque
    try:
        plaque_lue, confiance = systeme.analyser_base64(image_b64)
    except Exception as e:
        return Response({'erreur': f'Erreur traitement image : {str(e)}'}, status=500)

    if not plaque_lue:
        return Response({
            'autorise':  False,
            'message':   'Plaque illisible ou non détectée.',
            'confiance': 0.0,
        })

    # 2. Chercher une réservation active dans la fenêtre ±15 min
    now     = timezone.now()
    fenetre = timedelta(minutes=15)

    reservations = Reservation.objects.filter(
        statut='en_attente',
        heure_debut__gte=now - fenetre,
        heure_debut__lte=now + fenetre,
    ).select_related('vehicule', 'place')

    # 3. Comparer avec tolérance Levenshtein
    # Dans la vue detecter_plaque, remplacer la boucle de comparaison par :

    reservation_valide = None

    for r in reservations:
        plaque_ref = r.vehicule.plaque

        # Priorité 1 : comparaison complète Levenshtein ≤ 1
        if SystemeReconnaissance.comparer_plaques(plaque_lue, plaque_ref, tolerance=1):
            reservation_valide = r
            print(f"[API] Match Levenshtein : {plaque_lue} ≈ {plaque_ref}")
            break

        # Priorité 2 : comparaison numérique (si lettre illisible = ا ou ?)
        if '?' in plaque_lue or 'ا' in plaque_lue:
            if SystemeReconnaissance.comparer_numeros_seulement(plaque_lue, plaque_ref):
                reservation_valide = r
                print(f"[API] Match numérique : {plaque_lue} ~ {plaque_ref}")
                break
    # 4. Journaliser + répondre
    if reservation_valide:
        reservation_valide.confirmer_entree()

        JournalAcces.objects.create(
            plaque_detectee = plaque_lue,
            reservation     = reservation_valide,
            type_evenement  = JournalAcces.TypeEvenement.ENTREE,
            score_confiance = confiance,
        )

        return Response({
            'autorise':      True,
            'plaque_lue':    plaque_lue,
            'confiance':     round(confiance, 2),
            'place':         reservation_valide.place.numero,
            'utilisateur':   reservation_valide.utilisateur.get_full_name(),
            'message':       f'Accès autorisé — Place {reservation_valide.place.numero}',
        })

    # Accès refusé
    JournalAcces.objects.create(
        plaque_detectee = plaque_lue,
        type_evenement  = JournalAcces.TypeEvenement.REFUSE,
        score_confiance = confiance,
    )

    return Response({
        'autorise':   False,
        'plaque_lue': plaque_lue,
        'confiance':  round(confiance, 2),
        'message':    'Aucune réservation valide pour cette plaque.',
    })


@api_view(['GET'])
def spots_status(request):
    """Retourne le statut de toutes les places — utilisé par le dashboard."""
    places = PlaceParking.objects.values('id', 'numero', 'statut', 'etage')
    return Response(list(places))


@api_view(['POST'])
def barriere_ouvrir(request):
    """Simulation ouverture barrière."""
    return Response({'statut': 'ouverte', 'duree_secondes': 5})