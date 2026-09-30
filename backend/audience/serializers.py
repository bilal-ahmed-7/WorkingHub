from rest_framework import serializers

from audience.models import Audience


class AudienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Audience
        fields = [
            "id",
            "email",
            "mobile",
            "zipcode",
            "city",
            "street",
            "state",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
