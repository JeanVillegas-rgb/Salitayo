from django.core.mail import send_mail
from django.conf import settings

def send_verification_email(email, token):
    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"
    send_mail(
        subject="Verify your SALITAyo Account 🌸",
        message=f"Click the link to verify your account: {verification_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )