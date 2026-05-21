from django.core.management.base import BaseCommand

from profiles.models import User, StudentProfile


class Command(BaseCommand):
    help = 'Create a verified dev student account for Word Proficiency in the portal.'

    def handle(self, *args, **options):
        email = 'student@salitayo.dev'
        password = 'salitayo-dev'

        user, created = User.objects.using('wp').get_or_create(
            email=email,
            defaults={
                'display_name': 'Portal Student',
                'first_name': 'Portal',
                'last_name': 'Student',
                'role': User.Role.STUDENT,
                'is_verified': True,
                'is_active': True,
            },
        )

        if created:
            user.set_password(password)
            user.save(using='wp')
            StudentProfile.objects.using('wp').create(user=user)
            self.stdout.write(self.style.SUCCESS(f'Created dev student: {email}'))
        else:
            user.is_verified = True
            user.is_active = True
            user.role = User.Role.STUDENT
            user.set_password(password)
            user.save(using='wp')
            StudentProfile.objects.using('wp').get_or_create(user=user)
            self.stdout.write(self.style.SUCCESS(f'Updated dev student: {email}'))
