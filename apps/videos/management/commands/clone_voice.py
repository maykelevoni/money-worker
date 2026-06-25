"""One-time: clone Mayke's voice on ElevenLabs and print the voice_id.

Usage:
    python manage.py clone_voice path/to/sample1.mp3 path/to/sample2.mp3 --name "Mayke"

Record 1-3 clean samples (~30-60s total, quiet room, your normal speaking voice —
Portuguese is fine; it narrates English cross-lingually). Then put the printed id
into ELEVENLABS_VOICE_ID in your .env.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.videos.services import voice


class Command(BaseCommand):
    help = "Create an ElevenLabs instant-clone voice from audio samples."

    def add_arguments(self, parser):
        parser.add_argument("samples", nargs="+", help="Paths to audio sample files")
        parser.add_argument("--name", default="Mayke", help="Name for the cloned voice")

    def handle(self, *args, **opts):
        try:
            voice_id = voice.clone_voice(opts["name"], opts["samples"])
        except voice.NotConfigured as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Cloning failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Cloned voice id: {voice_id}"))
        self.stdout.write("Add this line to your .env:")
        self.stdout.write(f"  ELEVENLABS_VOICE_ID={voice_id}")
