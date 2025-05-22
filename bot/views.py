from django.shortcuts import render
from rest_framework import viewsets
from .models import Order
from .serializers import OrderSerializer

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def my_admin_view(request):
    # Только для персонала
    pass

from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def superuser_only_view(request):
    # Только для суперадмина
    pass