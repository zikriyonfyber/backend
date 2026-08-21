from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscriber
from .serializers import (
    ChipLoginSerializer,
    SubscriberProfileSerializer,
    SubscriberRegisterSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Creates a Subscriber. A staff member/reseller then binds an
    IdentityChip to this subscriber (see admin dashboard or ChipBindView)."""
    queryset = Subscriber.objects.all()
    serializer_class = SubscriberRegisterSerializer
    permission_classes = [permissions.AllowAny]


class ChipLoginView(APIView):
    """Portal/app login using chip ID + password -> JWT pair."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ChipLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.tokens(), status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = SubscriberProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
