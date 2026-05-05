from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/transcribe/', views.transcribe_audio, name='transcribe'),
    path('api/chat/', views.chat, name='chat'),
    path('api/clear/', views.clear_history, name='clear_history'),
]
