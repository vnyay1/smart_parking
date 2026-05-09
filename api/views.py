# api/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import re
import Levenshtein

from parking.models import PlaceParking, Reservation, JournalAcces
from vision.reconnaissance import SystemeReconnaissance

# Instance globale — évite de recharger EasyOCR à chaque requête
_systeme = None

def get_systeme():
    global _systeme
    if _systeme is None:
        _systeme = SystemeReconnaissance()
    return _systeme


def _trouver_reservation_correspondante(plaque_lue: str, reservations):
    """
    Retourne la meilleure réservation correspondant à la plaque lue.
    """
    candidats = []
    plaque_lue_norm = SystemeReconnaissance._normaliser_plaque(plaque_lue)
    lue_compact = re.sub(r'[^A-Z0-9]', '', plaque_lue_norm)

    for reservation in reservations:
        plaque_ref = reservation.vehicule.plaque
        if not SystemeReconnaissance.comparer_plaques(plaque_lue, plaque_ref):
            continue

        ref_norm = SystemeReconnaissance._normaliser_plaque(plaque_ref)
        ref_compact = re.sub(r'[^A-Z0-9]', '', ref_norm)
        dist = Levenshtein.distance(lue_compact, ref_compact)
        candidats.append((dist, reservation))

    if not candidats:
        return None

    candidats.sort(key=lambda t: t[0])
    # Eviter un faux positif quand deux réservations sont ex aequo.
    if len(candidats) > 1 and candidats[0][0] == candidats[1][0] and candidats[0][0] > 0:
        return None

    return candidats[0][1]


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

    # 1) Préparer les réservations candidates (sert aussi à guider l'OCR)
    now     = timezone.now()
    fenetre = timedelta(minutes=15)

    reservations_entree = Reservation.objects.filter(
        statut=Reservation.Statut.EN_ATTENTE,
        heure_debut__gte=now - fenetre,
        heure_debut__lte=now + fenetre,
    ).select_related('vehicule', 'place', 'utilisateur')

    reservations_sortie = Reservation.objects.filter(
        statut=Reservation.Statut.ACTIVE,
    ).select_related('vehicule', 'place', 'utilisateur')

    expected_plates = [r.vehicule.plaque for r in reservations_entree] + [r.vehicule.plaque for r in reservations_sortie]

    systeme = get_systeme()

    # 2) Lire la plaque (guidé par les plaques attendues)
    try:
        plaque_lue, confiance = systeme.analyser_base64(
            image_b64,
            expected_plates=expected_plates,
        )
    except Exception as e:
        return Response({'erreur': f'Erreur traitement image : {str(e)}'}, status=500)

    if not plaque_lue:
        return Response({
            'autorise':  False,
            'message':   'Plaque illisible ou non detectee.',
            'confiance': 0.0,
        })

    # 3) Associer la plaque lue à une réservation
    reservation_entree = _trouver_reservation_correspondante(plaque_lue, reservations_entree)
    reservation_sortie = _trouver_reservation_correspondante(plaque_lue, reservations_sortie)

    # 4) Cas sortie: place occupee -> libre
    if reservation_sortie and reservation_sortie.place.statut == PlaceParking.Statut.OCCUPEE:
        with transaction.atomic():
            reservation_sortie.terminer()
            JournalAcces.objects.create(
                plaque_detectee=plaque_lue,
                reservation=reservation_sortie,
                type_evenement=JournalAcces.TypeEvenement.SORTIE,
                score_confiance=confiance,
            )

        return Response({
            'autorise': True,
            'evenement': 'sortie',
            'plaque_lue': plaque_lue,
            'confiance': round(confiance, 2),
            'place': reservation_sortie.place.numero,
            'utilisateur': reservation_sortie.utilisateur.get_full_name(),
            'message': f'Sortie autorisee - Place {reservation_sortie.place.numero} liberee',
        })

    # 5) Cas entree: reservation en attente -> active et place occupee
    if reservation_entree:
        with transaction.atomic():
            reservation_entree.confirmer_entree()
            JournalAcces.objects.create(
                plaque_detectee=plaque_lue,
                reservation=reservation_entree,
                type_evenement=JournalAcces.TypeEvenement.ENTREE,
                score_confiance=confiance,
            )

        return Response({
            'autorise': True,
            'evenement': 'entree',
            'plaque_lue': plaque_lue,
            'confiance': round(confiance, 2),
            'place': reservation_entree.place.numero,
            'utilisateur': reservation_entree.utilisateur.get_full_name(),
            'message': f'Acces autorise - Place {reservation_entree.place.numero}',
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
