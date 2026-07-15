from django.urls import path
from . import views

urlpatterns = [
    path('patient-intake/', views.PatientIntakeView.as_view(), name='patient-intake'),
    path('patients/<int:patient_id>/', views.PatientRetrieveView.as_view(), name='patient-detail'),
]
