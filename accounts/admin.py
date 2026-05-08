from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Vehicule

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter   = ['is_staff', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering      = ['-date_joined']

    # Ajouter le champ telephone dans le formulaire d'édition
    fieldsets = UserAdmin.fieldsets + (
        ('Informations supplémentaires', {'fields': ('telephone',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations supplémentaires', {'fields': ('telephone',)}),
    )


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display  = ['plaque', 'proprietaire', 'marque', 'modele', 'couleur']
    search_fields = ['plaque', 'proprietaire__username', 'proprietaire__email']
    list_filter   = ['marque']
    autocomplete_fields = ['proprietaire']