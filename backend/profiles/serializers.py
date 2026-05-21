from rest_framework import serializers
from .models import User, StudentProfile, TeacherProfile, EmailVerificationToken
from django.contrib.auth import authenticate
from django.utils import timezone          # ← was: from datetime import timezone (wrong!)
from datetime import timedelta
import secrets


class RegisterSerializer(serializers.ModelSerializer):
    password         = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = [
            'email', 'display_name',
            'first_name', 'last_name', 'middle_name',
            'role', 'password', 'confirm_password'
        ]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        user.is_active   = True
        user.is_verified = False
        user.save()

        EmailVerificationToken.objects.create(
            user       = user,
            token      = secrets.token_urlsafe(32),
            expires_at = timezone.now() + timedelta(hours=24)  # ← now works correctly
        )
        return user


class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_verified:
            raise serializers.ValidationError("Please verify your email before logging in.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        data['user'] = user
        return data


class UpdateFCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['fcm_token']


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'display_name',
            'first_name', 'last_name', 'middle_name',
            'full_name', 'role', 'is_verified',
            'fcm_token', 'created_at'
        ]
        read_only_fields = ['id', 'is_verified', 'created_at']

    def get_full_name(self, obj):
        middle = f' {obj.middle_name}' if obj.middle_name else ''
        return f'{obj.first_name}{middle} {obj.last_name}'


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudentProfile
        fields = ['first_name', 'last_name', 'middle_name', 'student_id', 'user']


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TeacherProfile
        fields = ['first_name', 'last_name', 'middle_name', 'employee_id', 'department', 'user']