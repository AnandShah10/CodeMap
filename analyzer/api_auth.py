import random
import logging
from datetime import timedelta
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.timezone import now
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt

from django.core.mail import send_mail
from django.conf import settings as django_settings
from .models import EmailOTP

logger = logging.getLogger('django')

def sendOTP(email):
    """Generate a random 6-digit OTP, save to DB, and send via email."""
    # Generate 6 digit string
    otp = f"{random.randint(100000, 999999)}"
    
    # Save to database
    EmailOTP.objects.create(email=email, otp=otp)
    
    # Send email
    subject = f"{otp} is your CodeMap verification code"
    message = f"Your verification code for CodeMap is: {otp}\n\nThis code will expire in 5 minutes."
    html_message = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
        <h2 style="color: #1e293b; margin-bottom: 24px;">CodeMap Verification</h2>
        <p style="color: #475569; font-size: 16px; line-height: 24px;">
            Hello,<br><br>
            Use the following one-time password (OTP) to complete your login/signup process on CodeMap:
        </p>
        <div style="background: #f8fafc; padding: 16px; border-radius: 8px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #2563eb;">{otp}</span>
        </div>
        <p style="color: #64748b; font-size: 14px;">
            This code is valid for 5 minutes. If you did not request this code, please ignore this email.
        </p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 32px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">
            &copy; 2026 CodeMap AI. All rights reserved.
        </p>
    </div>
    """
    
    try:
        send_mail(
            subject,
            message,
            django_settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"OTP sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {str(e)}")
        # Fallback for dev: still print to console if email fails or is console backend
        print(f"\n[DEV/FAIL MAIL] OTP for {email}: {otp}\n")


def test_auth(email):
    """Placeholder equivalent to reference code test_auth"""
    # E.g. skip auth for certain test emails, return Response if short-circuited
    return None


def get_permanent_token(user):
    """Generate simplejwt token."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def signup_api(request):
    """
    Step 1: Request OTP for signup
    """
    email = request.data.get("email", "").lower()
    if not email:
        return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
    res = test_auth(email)
    if res:
        return res
    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered. Try login instead."}, status=status.HTTP_400_BAD_REQUEST)

    # rate limit: max 3 OTPs in 5 mins
    recent_otps = EmailOTP.objects.filter(email=email, created_at__gte=now() - timedelta(minutes=5))
    if recent_otps.count() >= 3:
        return Response({"error": "Too many OTP requests. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    sendOTP(email)
    return Response({
        "success": True,
        "message": "OTP sent successfully for signup.",
        "type": "signup"
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_api(request):
    """
    Step 1: Request OTP for login
    """
    email = request.data.get("email", "").lower()
    if not email:
        return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
    res = test_auth(email)
    if res:
        return res
    if not User.objects.filter(email=email).exists():
        return Response({"error": "Email not found. Please signup first."}, status=status.HTTP_404_NOT_FOUND)

    # rate limit
    recent_otps = EmailOTP.objects.filter(email=email, created_at__gte=now() - timedelta(minutes=5))
    if recent_otps.count() >= 3:
        return Response({"error": "Too many OTP requests. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    sendOTP(email)
    return Response({
        "success": True,
        "message": "OTP sent successfully for login.",
        "type": "login"
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_otp_api(request):
    """
    Step 2: Verify OTP (signup/login)
    """
    email = request.data.get("email", "").lower()
    otp = request.data.get("otp")
    otp_type = request.data.get("type", "login")  # default to login

    if not email or not otp:
        return Response({"error": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        latest_otp = EmailOTP.objects.filter(email=email).latest("created_at")
    except EmailOTP.DoesNotExist:
        return Response({"error": "No OTP found for this email."}, status=status.HTTP_404_NOT_FOUND)

    # Too many wrong tries
    if latest_otp.failed_attempts >= 5:
        return Response({"error": "Too many incorrect attempts. Please request a new OTP."}, status=status.HTTP_403_FORBIDDEN)

    # Validate OTP
    if latest_otp.otp == str(otp) and latest_otp.is_valid():
        # ✅ OTP success
        latest_otp.delete()  # clear OTP

        if otp_type == "signup":
            if User.objects.filter(email=email).exists():
                return Response({"error": "Email already registered. Try login instead."}, status=status.HTTP_400_BAD_REQUEST)
            # only now create the user
            user = User.objects.create_user(username=email, email=email)
        else:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"error": "User not found. Please signup first."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure active Django session is set, so the non-SPA UI still works cleanly
        login(request, user)

        # generate auth token for typical SPA integration
        token = get_permanent_token(user)
        return Response({
            "success": True,
            "message": f"OTP verified successfully for {otp_type}.",
            "user_id": user.id,
            "email": user.email,
            "token": token
        }, status=status.HTTP_200_OK)

    else:
        # ❌ Wrong OTP
        latest_otp.failed_attempts += 1
        latest_otp.save(update_fields=["failed_attempts"])
        err_msg = "Invalid OTP." if latest_otp.is_valid() else "OTP expired."
        return Response({"error": err_msg}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_otp_api(request):
    """
    Resend OTP (for signup/login)
    """
    email = request.data.get("email", "").lower()
    if not email:
        return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

    recent_otps = EmailOTP.objects.filter(email=email, created_at__gte=now() - timedelta(minutes=5))
    if recent_otps.count() >= 3:
        return Response({"error": "Too many OTP requests. Try again later."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    sendOTP(email)
    return Response({
        "success": True,
        "message": "OTP resent successfully."
    }, status=status.HTTP_200_OK)
