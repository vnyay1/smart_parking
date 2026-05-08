from django.contrib import admin
from .models import PlaceParking, Reservation, JournalAcces


@admin.register(PlaceParking)
class PlaceParkingAdmin(admin.ModelAdmin):
    list_display   = ['numero', 'statut', 'etage', 'updated_at']
    list_filter    = ['statut', 'etage']
    list_editable  = ['statut']               # modifiable directement dans la liste
    search_fields  = ['numero']
    ordering       = ['numero']
    actions        = ['liberer_selection']

    @admin.action(description='Libérer les places sélectionnées')
    def liberer_selection(self, request, queryset):
        queryset.update(statut=PlaceParking.Statut.LIBRE)
        self.message_user(request, f"{queryset.count()} place(s) libérée(s).")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display        = ['pk', 'utilisateur', 'place', 'vehicule', 'heure_debut', 'heure_fin', 'statut', 'created_at']
    list_filter         = ['statut', 'place__etage']
    search_fields       = ['utilisateur__email', 'vehicule__plaque']
    autocomplete_fields = ['utilisateur', 'vehicule', 'place']
    readonly_fields     = ['created_at', 'heure_entree_reelle']
    date_hierarchy      = 'heure_debut'
    actions             = ['annuler_selection']

    @admin.action(description='Annuler les réservations sélectionnées')
    def annuler_selection(self, request, queryset):
        for r in queryset.filter(statut__in=['en_attente', 'active']):
            r.annuler()
        self.message_user(request, "Réservations annulées et places libérées.")


@admin.register(JournalAcces)
class JournalAccesAdmin(admin.ModelAdmin):
    list_display  = ['timestamp', 'plaque_detectee', 'type_evenement', 'reservation', 'score_confiance']
    list_filter   = ['type_evenement']
    search_fields = ['plaque_detectee']
    readonly_fields = ['timestamp', 'plaque_detectee', 'reservation', 'type_evenement', 'score_confiance']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False         # les logs ne se créent jamais manuellement

    def has_change_permission(self, request, obj=None):
        return False         # lecture seule