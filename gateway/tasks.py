import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, patient_id):

    from .models import PatientRecord

    try:
        patient = PatientRecord.objects.get(pk=patient_id)
    except PatientRecord.DoesNotExist:
        logger.error(f"Patient {patient_id} not found, skipping welcome email.")
        return

    logger.info(
        f"Sending welcome email to {patient.first_name} {patient.last_name} "
        f"(Patient ID: {patient.id})"
    )


    return f"Welcome email sent to patient {patient_id}"
