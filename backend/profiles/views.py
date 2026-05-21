from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.utils import timezone
from datetime import timedelta
import secrets

from .models import User, StudentProfile, TeacherProfile, EmailVerificationToken
from .serializers import (
    RegisterSerializer, UserSerializer, LoginSerializer,
    StudentProfileSerializer, TeacherProfileSerializer, UpdateFCMTokenSerializer
)
from .utils import send_verification_email


# ── custom permission classes ────────────────────────────────────────────────

class IsStudent(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'STUDENT'

class IsProfessor(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'PROFESSOR'

class IsAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == 'ADMIN'


# ── auth views ───────────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # ✅ One token per user (atomic)
            verification, _ = EmailVerificationToken.objects.update_or_create(
                user=user,
                defaults={
                    "token": secrets.token_urlsafe(32),
                    "expires_at": timezone.now() + timedelta(hours=24),
                }
            )

            send_verification_email(user.email, verification.token)

            return Response({
                "message": "Registration successful. Please check your email to verify your account.",
                "user": UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        verification = EmailVerificationToken.objects.filter(token=token).first()

        # ── Case 1: Token does NOT exist ─────────────────────────────
        if not verification:
            return Response(
                {
                    "message": "This link is no longer valid. It may have already been used."
                },
                status=status.HTTP_200_OK,
            )

        user = verification.user

        # ── Case 2: Already verified ────────────────────────────────
        if user.is_verified:
            verification.delete()
            return Response(
                {"message": "Email already verified. You can log in."},
                status=status.HTTP_200_OK,
            )

        # ── Case 3: Token expired ───────────────────────────────────
        if verification.is_expired():
            verification.delete()
            return Response(
                {"error": "Verification link has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Case 4: Normal success ──────────────────────────────────
        user.is_verified = True
        user.save()
        verification.delete()

        return Response(
            {"message": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": token.key,
                "user": UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


# ── user views ───────────────────────────────────────────────────────────────

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UpdateFCMTokenSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "FCM token updated."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No account found."}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Return 200 instead of 400 (clean UX)
        if user.is_verified:
            return Response(
                {"message": "Account already verified. You can log in."},
                status=status.HTTP_200_OK
            )

        # ✅ One token per user (atomic)
        verification, _ = EmailVerificationToken.objects.update_or_create(
            user=user,
            defaults={
                "token": secrets.token_urlsafe(32),
                "expires_at": timezone.now() + timedelta(hours=24),
            }
        )

        send_verification_email(user.email, verification.token)

        return Response({"message": "Verification email resent."}, status=status.HTTP_200_OK)


# ── profile views ────────────────────────────────────────────────────────────

class StudentProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsStudent]
    serializer_class = StudentProfileSerializer

    def get_object(self):
        profile, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile


class TeacherProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsProfessor]
    serializer_class = TeacherProfileSerializer

    def get_object(self):
        profile, _ = TeacherProfile.objects.get_or_create(user=self.request.user)
        return profile
    



