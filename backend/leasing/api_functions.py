from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from leasing.utils import calculate_increase_with_360_day_calendar


class CalculateIncreaseSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    percentage = serializers.DecimalField(max_digits=None, decimal_places=None)
    amount = serializers.DecimalField(max_digits=None, decimal_places=None)


class CalculateIncreaseWith360DayCalendar(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        return self.process_request(request, request.data)

    def get(self, request, format=None):
        return self.process_request(request, request.query_params)

    def process_request(self, request, data):
        serializer = CalculateIncreaseSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]
        percentage = serializer.validated_data["percentage"]
        amount = serializer.validated_data["amount"]

        result_dict = {}
        result_dict["result"] = calculate_increase_with_360_day_calendar(
            start_date, end_date, percentage, amount
        )

        return Response(result_dict)
