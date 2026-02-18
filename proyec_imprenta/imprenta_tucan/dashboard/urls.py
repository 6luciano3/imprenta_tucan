from django.urls import path
from .views_test import DashboardTestView

urlpatterns = [
    path('tests/', DashboardTestView.as_view(), name='dashboard_tests'),
]
