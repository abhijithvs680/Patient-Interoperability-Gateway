import logging
from django.db import IntegrityError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import PatientRecord, AccessLog
from .serializers import FHIRPatientIntakeSerializer, PatientDetailSerializer
from .tasks import send_welcome_email

logger = logging.getLogger(__name__)

SSN_SYSTEM = 'http://hl7.org/fhir/sid/us-ssn'
PASSPORT_SYSTEM = 'http://hl7.org/fhir/sid/passport'


def _extract_identifier(identifiers, system_url):
    for ident in identifiers:
        if ident.get('system') == system_url:
            return ident.get('value')
    return None


def _get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class PatientIntakeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FHIRPatientIntakeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        identifiers = data.get('identifier', [])
        names = data['name'][0]
        telecom = data.get('telecom', [])

        ssn = _extract_identifier(identifiers, SSN_SYSTEM)

        passport = _extract_identifier(identifiers, PASSPORT_SYSTEM)

        phone = ''
        for contact in telecom:
            if contact.get('system') == 'phone':
                phone = contact.get('value', '')
                break

        given_names = names.get('given', [])
        first_name = given_names[0] if given_names else ''

        try:
            patient = PatientRecord.objects.create(
                fhir_id=data['id'],
                first_name=first_name,
                last_name=names.get('family', ''),
                birth_date=data['birthDate'],
                gender=data['gender'],
                ssn=ssn or '',
                passport_number=passport,
                phone=phone,
                active=data.get('active', True),
                raw_fhir_payload=request.data,
            )
        except IntegrityError:
            return Response(
                {'detail': 'A patient with this FHIR ID already exists.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            send_welcome_email.delay(patient.id)
        except Exception as exc:
            logger.warning(f"Could not queue welcome email for patient {patient.id}: {exc}")

        return Response(
            {'id': patient.id, 'fhir_id': patient.fhir_id, 'status': 'accepted'},
            status=status.HTTP_201_CREATED,
        )


class PatientRetrieveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        try:
            patient = PatientRecord.objects.get(pk=patient_id)
        except PatientRecord.DoesNotExist:
            return Response(
                {'detail': 'Patient not found.'}, status=status.HTTP_404_NOT_FOUND
            )

        AccessLog.objects.create(
            patient=patient,
            accessed_by=request.user,
            ip_address=_get_client_ip(request),
        )

        serializer = PatientDetailSerializer(patient)
        return Response(serializer.data)
