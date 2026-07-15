from datetime import date
from rest_framework import serializers
from .models import PatientRecord


class FHIRPatientIntakeSerializer(serializers.Serializer):

    resourceType = serializers.CharField()
    id = serializers.CharField()
    active = serializers.BooleanField(required=False, default=True)
    birthDate = serializers.DateField(input_formats=['%Y-%m-%d'])
    name = serializers.ListField(child=serializers.DictField(), min_length=1)
    gender = serializers.CharField()
    identifier = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    telecom = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )

    def validate_resourceType(self, value):
        if value != 'Patient':
            raise serializers.ValidationError("resourceType must be 'Patient'.")
        return value

    def validate_birthDate(self, value):
        today = date.today()
        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )
        if age < 18:
            raise serializers.ValidationError(
                "Patient must be at least 18 years old."
            )
        return value

    def validate_name(self, value):

        if not value or 'family' not in value[0]:
            raise serializers.ValidationError(
                "At least one name entry with a 'family' field is required."
            )
        return value


class PatientDetailSerializer(serializers.ModelSerializer):
    ssn = serializers.SerializerMethodField()

    class Meta:
        model = PatientRecord
        fields = [
            'id', 'fhir_id', 'first_name', 'last_name',
            'birth_date', 'gender', 'ssn', 'phone',
            'active', 'created_at',
        ]

    def get_ssn(self, obj):
        if not obj.ssn:
            return None
        return f"***-**-{obj.ssn[-4:]}"
