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
ARRIVEE_ANTICIPATION_MINUTES = 60
SORTIE_GRACE_MINUTES = 15

def get_systeme():
    global _systeme
    if _systeme is None:
        _systeme = SystemeReconnaissance()
    return _systeme


def _trouver_reservation_valide(plaque_lue: str, reservations):
    for reservation in reservations:
        plaque_ref = reservation.vehicule.plaque

        # Priorité 1 : comparaison complète Levenshtein
        if SystemeReconnaissance.comparer_plaques(plaque_lue, plaque_ref, tolerance=1):
            return reservation

        # Priorité 2 : fallback chiffres si la lettre est potentiellement mal lue
        if '?' in plaque_lue or 'ا' in plaque_lue:
            if SystemeReconnaissance.comparer_numeros_seulement(plaque_lue, plaque_ref):
                return reservation

    return None


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
            'evenement': 'refuse',
        })

    # 2. Chercher des réservations compatibles
    now = timezone.now()
    fenetre_entree = timedelta(minutes=ARRIVEE_ANTICIPATION_MINUTES)
    fenetre_sortie = timedelta(minutes=SORTIE_GRACE_MINUTES)

    reservations_entree = Reservation.objects.filter(
        statut=Reservation.Statut.EN_ATTENTE,
        heure_debut__lte=now + fenetre_entree,
        heure_fin__gte=now,
    ).select_related('vehicule', 'place', 'utilisateur')

    reservations_sortie = Reservation.objects.filter(
        statut=Reservation.Statut.ACTIVE,
        heure_fin__gte=now - fenetre_sortie,
    ).select_related('vehicule', 'place')

    # 3. Priorité sortie (si réservation déjà active), sinon entrée
    reservation_sortie = _trouver_reservation_valide(plaque_lue, reservations_sortie)
    if reservation_sortie:
        reservation_sortie.terminer()

        JournalAcces.objects.create(
            plaque_detectee = plaque_lue,
            reservation     = reservation_sortie,
            type_evenement  = JournalAcces.TypeEvenement.SORTIE,
            score_confiance = confiance,
        )

        return Response({
            'autorise':      True,
            'evenement':     'sortie',
            'plaque_lue':    plaque_lue,
            'confiance':     round(confiance, 2),
            'place':         reservation_sortie.place.numero,
            'utilisateur':   reservation_sortie.utilisateur.get_full_name(),
            'message':       f'Sortie autorisée — Place {reservation_sortie.place.numero}',
        })

    reservation_entree = _trouver_reservation_valide(plaque_lue, reservations_entree)
    if reservation_entree:
        reservation_entree.confirmer_entree()

        JournalAcces.objects.create(
            plaque_detectee = plaque_lue,
            reservation     = reservation_entree,
            type_evenement  = JournalAcces.TypeEvenement.ENTREE,
            score_confiance = confiance,
        )

        return Response({
            'autorise':      True,
            'evenement':     'entree',
            'plaque_lue':    plaque_lue,
            'confiance':     round(confiance, 2),
            'place':         reservation_entree.place.numero,
            'utilisateur':   reservation_entree.utilisateur.get_full_name(),
            'message':       f'Accès autorisé — Place {reservation_entree.place.numero}',
        })

    # Accès refusé
    JournalAcces.objects.create(
        plaque_detectee = plaque_lue,
        type_evenement  = JournalAcces.TypeEvenement.REFUSE,
        score_confiance = confiance,
    )

    return Response({
        'autorise':   False,
        'evenement':  'refuse',
        'plaque_lue': plaque_lue,
        'confiance':  round(confiance, 2),
        'message':    'Aucune reservation valide pour cette plaque.',
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
