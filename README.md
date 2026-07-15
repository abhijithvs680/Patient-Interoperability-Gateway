# Patient Interoperability Gateway (PIG)

A Django microservice that ingests FHIR R4 Patient resources, stores them with HIPAA-compliant encryption, and exposes a sanitized retrieval API.

## Setup

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (for PostgreSQL and Redis)

### Steps

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Start the backing services:
   ```bash
   docker-compose up -d
   ```

3. Copy and configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Generate a Fernet encryption key and paste it into `.env`:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Run migrations and create a superuser:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. Generate an API token (needed for authenticated requests):
   ```bash
   python manage.py shell -c "
   from rest_framework.authtoken.models import Token
   from django.contrib.auth.models import User
   t, _ = Token.objects.get_or_create(user=User.objects.first())
   print(t.key)
   "
   ```

## Running the Server

```bash
python manage.py runserver
```

For the Celery worker (handles async tasks like the welcome email):
```bash
celery -A pig worker --loglevel=info
```

## API Usage

### Ingest a patient

```bash
curl -X POST http://localhost:8000/api/patient-intake/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Patient",
    "id": "example-123",
    "active": true,
    "name": [{"use": "official", "family": "Chalmers", "given": ["Peter", "James"]}],
    "gender": "male",
    "birthDate": "1980-12-25",
    "identifier": [{"system": "http://hl7.org/fhir/sid/us-ssn", "value": "000-12-3456"}],
    "telecom": [{"system": "phone", "value": "(555) 555-5555", "use": "home"}]
  }'
```

### Retrieve a patient (SSN will be masked)

```bash
curl http://localhost:8000/api/patients/1/ \
  -H "Authorization: Token YOUR_TOKEN"
```

## Running Tests

```bash
python manage.py test gateway -v 2
```

Tests override the encryption key internally, so the `FIELD_ENCRYPTION_KEY` env var isn't needed to run them. You do need the database running though (or switch to SQLite for a quick check).

## Design Decision: SSN Encryption

I used Fernet symmetric encryption from Python's `cryptography` library, wrapped in a custom Django model field (`EncryptedCharField` in `gateway/fields.py`).

**Why Fernet?**
- It gives you authenticated encryption (AES-128-CBC + HMAC) out of the box, so the data is encrypted and tamper-proof.
- The `cryptography` library is well-audited and widely used — no reason to roll our own.
- The custom field handles encrypt-on-save and decrypt-on-read transparently, so the rest of the codebase doesn't need to care about it.

**How it works:**
- The encryption key lives in an environment variable (`FIELD_ENCRYPTION_KEY`), keeping it out of the codebase. Key rotation is as simple as updating that env var (with a migration step for existing data).
- The field stores ciphertext as a `TextField` since encrypted output is always longer than the plaintext input.
- If decryption fails (e.g. after a key rotation), `from_db_value` falls back to returning the raw value instead of crashing. In production you'd want to log that and alert on it.

**Trade-offs:**
- You can't do SQL-level queries against encrypted fields (e.g. `WHERE ssn = '...'`). That's fine here since we never need to search by SSN.
- Key management is delegated to infrastructure. In production I'd use AWS Secrets Manager or HashiCorp Vault instead of a plain env var.
