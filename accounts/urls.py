from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('inscription/', views.inscription, name='inscription'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
     # Véhicules
    path('vehicules/',                    views.liste_vehicules,   name='liste_vehicules'),
    path('vehicules/ajouter/',            views.ajouter_vehicule,  name='ajouter_vehicule'),
    path('vehicules/<int:pk>/modifier/',  views.modifier_vehicule, name='modifier_vehicule'),
    path('vehicules/<int:pk>/supprimer/', views.supprimer_vehicule, name='supprimer_vehicule'),
]