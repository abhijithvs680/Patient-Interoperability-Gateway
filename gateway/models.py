from django.db import models
from django.contrib.auth.models import User
from .fields import EncryptedCharField


class PatientRecord(models.Model):
    fhir_id = models.CharField(max_length=128, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20)
    ssn = EncryptedCharField()
    passport_number = EncryptedCharField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, default='')
    active = models.BooleanField(default=True)
    raw_fhir_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.fhir_id})"


class AccessLog(models.Model):
    patient = models.ForeignKey(
        PatientRecord, on_delete=models.CASCADE, related_name='access_logs'
    )
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Access to {self.patient.fhir_id} at {self.timestamp}"
