from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT' , 'student',
        PROFESSOR = "PROFESSOR", 'professor',
        ADMIN = "ADMIN", 'admin',

    email        = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100)
    first_name   = models.CharField(max_length=50)
    last_name    = models.CharField(max_length=50)
    middle_name  = models.CharField(max_length=20, null=True, blank=True)
    role         = models.CharField(max_length=20, choices=Role.choices)

    # email verification
    is_verified  = models.BooleanField(default=False)

    # FCM token for push notifications
    fcm_token    = models.CharField(max_length=255, blank=True, null=True)

    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['display_name', 'first_name', 'last_name']

    @property
    def is_teacher(self):
        return self.role == self.Role.PROFESSOR

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
    
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def __str__(self):
        middle = f' {self.middle_name}' if self.middle_name else ''
        return f'{self.first_name}{middle} {self.last_name}'


class EmailVerificationToken(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token      = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f'Token for {self.user.email}'


class StudentProfile(models.Model):


    student_id = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField('profiles.User', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        middle = f'{self.middle_name}' if self.middle_name else ''
        return f'{self.first_name}{middle} {self.last_name}'
    

class TeacherProfile(models.Model):
    user = models.OneToOneField('profiles.User', on_delete=models.CASCADE)


    employee_id  = models.CharField(max_length=10, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=20, null=True, blank=True)
    department = models.ForeignKey('system.College', on_delete=models.PROTECT)


    def __str__(self):
        middle = f'{self.middle_name}' if self.middle_name else ''
        return f'{self.first_name}{middle} {self.last_name}'
