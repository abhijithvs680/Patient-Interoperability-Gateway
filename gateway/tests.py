from datetime import date, timedelta
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from cryptography.fernet import Fernet

from .models import PatientRecord, AccessLog

TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


def _build_fhir_patient(**overrides):

    payload = {
        'resourceType': 'Patient',
        'id': 'test-patient-001',
        'active': True,
        'name': [
            {
                'use': 'official',
                'family': 'Doe',
                'given': ['John'],
            }
        ],
        'gender': 'male',
        'birthDate': '1990-05-15',
        'identifier': [
            {
                'system': 'http://hl7.org/fhir/sid/us-ssn',
                'value': '123-45-6789',
            }
        ],
        'telecom': [
            {
                'system': 'phone',
                'value': '(555) 123-4567',
                'use': 'home',
            }
        ],
    }
    payload.update(overrides)
    return payload


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class PatientIntakeTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.url = '/api/patient-intake/'

    def test_successful_intake(self):
        payload = _build_fhir_patient()
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(PatientRecord.objects.count(), 1)

        patient = PatientRecord.objects.first()
        self.assertEqual(patient.last_name, 'Doe')
        self.assertEqual(patient.first_name, 'John')
        self.assertEqual(patient.gender, 'male')

    def test_reject_minor_patient(self):
        ten_years_ago = date.today() - timedelta(days=365 * 10)
        payload = _build_fhir_patient(birthDate=ten_years_ago.isoformat())
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('birthDate', resp.data)

    def test_reject_invalid_resource_type(self):
        payload = _build_fhir_patient(resourceType='Observation')
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_reject_missing_name(self):
        payload = _build_fhir_patient(name=[])
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_request_rejected(self):
        self.client.credentials()
        payload = _build_fhir_patient()
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_raw_payload_stored(self):
        payload = _build_fhir_patient()
        self.client.post(self.url, payload, format='json')
        patient = PatientRecord.objects.first()
        self.assertEqual(patient.raw_fhir_payload['resourceType'], 'Patient')

    def test_duplicate_fhir_id_returns_409(self):
        payload = _build_fhir_patient()
        self.client.post(self.url, payload, format='json')
        resp = self.client.post(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 409)


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class PatientRetrievalTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.patient = PatientRecord.objects.create(
            fhir_id='test-001',
            first_name='Jane',
            last_name='Smith',
            birth_date=date(1985, 3, 20),
            gender='female',
            ssn='987-65-4321',
            phone='(555) 999-0000',
            raw_fhir_payload={'resourceType': 'Patient'},
        )

    def test_retrieve_patient(self):
        resp = self.client.get(f'/api/patients/{self.patient.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['last_name'], 'Smith')

    def test_ssn_is_masked(self):
        resp = self.client.get(f'/api/patients/{self.patient.id}/')
        self.assertEqual(resp.data['ssn'], '***-**-4321')

    def test_access_log_created(self):
        self.client.get(f'/api/patients/{self.patient.id}/')
        self.assertEqual(AccessLog.objects.count(), 1)

        log = AccessLog.objects.first()
        self.assertEqual(log.patient, self.patient)
        self.assertEqual(log.accessed_by, self.user)

    def test_multiple_accesses_create_multiple_logs(self):
        self.client.get(f'/api/patients/{self.patient.id}/')
        self.client.get(f'/api/patients/{self.patient.id}/')
        self.assertEqual(AccessLog.objects.count(), 2)

    def test_nonexistent_patient_returns_404(self):
        resp = self.client.get('/api/patients/99999/')
        self.assertEqual(resp.status_code, 404)


@override_settings(FIELD_ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class EncryptionTests(TestCase):
    def test_ssn_encrypted_in_database(self):
        patient = PatientRecord.objects.create(
            fhir_id='enc-test-001',
            first_name='Test',
            last_name='Encryption',
            birth_date=date(1990, 1, 1),
            gender='other',
            ssn='111-22-3333',
            raw_fhir_payload={},
        )

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT ssn FROM gateway_patientrecord WHERE id = %s',
                [patient.id],
            )
            raw_ssn = cursor.fetchone()[0]

        self.assertNotEqual(raw_ssn, '111-22-3333')

        patient.refresh_from_db()
        self.assertEqual(patient.ssn, '111-22-3333')
