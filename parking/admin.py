from django.contrib import admin
from .models import PlaceParking, Reservation, JournalAcces

@admin.register(PlaceParking)
class PlaceParkingAdmin(admin.ModelAdmin):
    list_display = ['numero', 'statut', 'etage', 'updated_at']
    list_filter = ['statut', 'etage']
    list_editable = ['statut']   # modifiable directement dans la liste

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'place', 'vehicule', 'heure_debut', 'statut']
    list_filter = ['statut']
    search_fields = ['utilisateur__email', 'vehicule__plaque']
