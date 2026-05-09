from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('detect/',         views.detecter_plaque, name='detecter_plaque'),
    path('spots/',          views.spots_status,    name='spots_status'),
    path('barriere/open/',  views.barriere_ouvrir, name='barriere_ouvrir'),
]