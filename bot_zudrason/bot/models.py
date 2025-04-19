from django.db import models
from django.utils import timezone


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтвержден'),
        ('paid', 'Оплачен'),
        ('assigned', 'Назначен курьеру'),
        ('in_progress', 'В процессе доставки'),
        ('delivered', 'Доставлен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]
    user_id = models.BigIntegerField()
    from_address = models.TextField()
    to_address = models.TextField()
    phone = models.CharField(max_length=20)
    package_type = models.CharField(max_length=50)
    photo = models.ImageField(upload_to='orders/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    courier_id = models.BigIntegerField(null=True, blank=True)
    courier_link = models.CharField(max_length=100, blank=True, null=True)
    courier_message = models.TextField(blank=True, null=True)
    delivery_message = models.TextField(blank=True, null=True)
    client_feedback = models.TextField(blank=True, null=True)
    client_link = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Ссылка на клиента"
    )
    client_score = models.PositiveSmallIntegerField(
        blank=True, 
        null=True,
        verbose_name="Оценка клиента",
        help_text="Оценка от 1 до 5"
    )
    created_at = models.DateTimeField(default=timezone.now)  # Добавлено
    updated_at = models.DateTimeField(auto_now=True)  # Добавлено

    def __str__(self):
        return f"Заказ #{self.id} ({self.get_status_display()})"

