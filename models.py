from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтвержден'),
        ('delivered', 'Доставлен'),
    ]
    user_id = models.BigIntegerField()
    from_address = models.TextField()
    to_address = models.TextField()
    phone = models.CharField(max_length=20)
    package_type = models.CharField(max_length=50)
    photo = models.ImageField(upload_to='orders/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"Заказ {self.id} от {self.user_id}"
