from rest_framework import serializers

from accounts.models import User
from companies.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """
    Serializer for Company organization details.
    """

    class Meta:
        model = Company
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class WorkerSerializer(serializers.ModelSerializer):
    """
    Serializer for listing and managing company workers.
    """

    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined"]
