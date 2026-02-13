from django.urls import path
from .views import dashboard_tests

urlpatterns = [
    path('tests/', dashboard_tests, name='dashboard_tests'),
]
