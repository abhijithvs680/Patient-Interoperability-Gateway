from django.contrib import admin
from .models import PatientRecord, AccessLog


@admin.register(PatientRecord)
class PatientRecordAdmin(admin.ModelAdmin):
    list_display = ('fhir_id', 'last_name', 'first_name', 'birth_date', 'created_at')
    search_fields = ('fhir_id', 'last_name', 'first_name')
    readonly_fields = ('raw_fhir_payload', 'created_at', 'updated_at')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('patient', 'accessed_by', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    readonly_fields = ('patient', 'accessed_by', 'ip_address', 'timestamp')
