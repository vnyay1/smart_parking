import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, Vehicule
from parking.models import PlaceParking, Reservation, JournalAcces


class DetecterPlaqueAPITests(TestCase):
    def setUp(self):
        self.url = reverse("api:detecter_plaque")

        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="secret123",
            first_name="Yaya",
            last_name="Test",
            email="yaya@example.com",
        )

    def _post_image(self, image="dummy-base64"):
        return self.client.post(
            self.url,
            data=json.dumps({"image": image}),
            content_type="application/json",
        )

    @patch("api.views.get_systeme")
    def test_entree_autorisee_active_reservation_and_occupies_place(self, mock_get_systeme):
        mock_get_systeme.return_value.analyser_base64.return_value = ("12345-A-6", 0.91)

        place = PlaceParking.objects.create(numero=101, statut=PlaceParking.Statut.RESERVEE, etage=1)
        vehicule = Vehicule.objects.create(proprietaire=self.user, plaque="12345-A-6")
        reservation = Reservation.objects.create(
            utilisateur=self.user,
            place=place,
            vehicule=vehicule,
            heure_debut=timezone.now(),
            heure_fin=timezone.now() + timedelta(hours=1),
            statut=Reservation.Statut.EN_ATTENTE,
        )

        response = self._post_image()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["autorise"])
        self.assertEqual(payload["evenement"], "entree")

        reservation.refresh_from_db()
        place.refresh_from_db()
        self.assertEqual(reservation.statut, Reservation.Statut.ACTIVE)
        self.assertEqual(place.statut, PlaceParking.Statut.OCCUPEE)

        self.assertTrue(
            JournalAcces.objects.filter(
                reservation=reservation,
                type_evenement=JournalAcces.TypeEvenement.ENTREE,
            ).exists()
        )

    @patch("api.views.get_systeme")
    def test_sortie_autorisee_termines_reservation_and_frees_place(self, mock_get_systeme):
        mock_get_systeme.return_value.analyser_base64.return_value = ("65528-I-8", 0.84)

        place = PlaceParking.objects.create(numero=102, statut=PlaceParking.Statut.OCCUPEE, etage=1)
        vehicule = Vehicule.objects.create(proprietaire=self.user, plaque="65528-I-8")
        reservation = Reservation.objects.create(
            utilisateur=self.user,
            place=place,
            vehicule=vehicule,
            heure_debut=timezone.now() - timedelta(hours=2),
            heure_fin=timezone.now() + timedelta(hours=1),
            statut=Reservation.Statut.ACTIVE,
            heure_entree_reelle=timezone.now() - timedelta(hours=1),
        )

        response = self._post_image()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["autorise"])
        self.assertEqual(payload["evenement"], "sortie")

        reservation.refresh_from_db()
        place.refresh_from_db()
        self.assertEqual(reservation.statut, Reservation.Statut.TERMINEE)
        self.assertEqual(place.statut, PlaceParking.Statut.LIBRE)

        self.assertTrue(
            JournalAcces.objects.filter(
                reservation=reservation,
                type_evenement=JournalAcces.TypeEvenement.SORTIE,
            ).exists()
        )

    @patch("api.views.get_systeme")
    def test_refus_when_no_matching_reservation(self, mock_get_systeme):
        mock_get_systeme.return_value.analyser_base64.return_value = ("99999-Z-99", 0.77)

        response = self._post_image()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["autorise"])
        self.assertIn("Aucune reservation valide", payload["message"])
