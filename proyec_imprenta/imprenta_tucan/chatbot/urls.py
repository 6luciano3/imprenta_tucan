from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('api/', views.chatbot_api, name='api'),
]
