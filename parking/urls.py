from django.urls import path
from . import views

app_name = 'parking'

urlpatterns = [
    path('',                            views.dashboard,           name='dashboard'),
    path('reserver/',                   views.creer_reservation,   name='creer_reservation'),
    path('mes-reservations/',           views.mes_reservations,    name='mes_reservations'),
    path('reservation/<int:pk>/',       views.detail_reservation,  name='detail_reservation'),
    path('reservation/<int:pk>/annuler/', views.annuler_reservation, name='annuler_reservation'),
]