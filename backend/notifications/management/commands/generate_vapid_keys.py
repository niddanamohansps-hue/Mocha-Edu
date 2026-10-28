import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Prints a new VAPID key pair for free push notifications. Put both in .env (never commit them)."

    def handle(self, *args, **options):
        key = ec.generate_private_key(ec.SECP256R1())
        private = _b64(key.private_numbers().private_value.to_bytes(32, "big"))
        public = _b64(key.public_key().public_bytes(serialization.Encoding.X962,
                                                    serialization.PublicFormat.UncompressedPoint))
        self.stdout.write("Add these three lines to backend/.env, then restart the server and the Celery worker:\n")
        self.stdout.write(f"WEBPUSH_VAPID_PUBLIC_KEY={public}")
        self.stdout.write(f"WEBPUSH_VAPID_PRIVATE_KEY={private}")
        self.stdout.write("WEBPUSH_CONTACT=mailto:you@yourschoolapp.in")
        self.stdout.write("\nGenerate them once. Changing them later signs every device out of notifications.")
