from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from .models import Order
from django.utils.html import format_html
from django.contrib.admin import DateFieldListFilter

# Отмена регистрации стандартных моделей
admin.site.unregister(User)
admin.site.unregister(Group)

# Кастомный админ для User
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser')

admin.site.register(User, CustomUserAdmin)

# Кастомный админ для Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'status_badge', 
        'user_link', 
        'client_link_display',  # Добавлено отображение client_link
        'from_address_short', 
        'to_address_short', 
        'price',
        'courier_link', 
        'get_created_at',
        'client_score_display',
        'feedback_preview'  # Добавлено отображение client_feedback
    )
    list_filter = (
        'status',
        ('created_at', DateFieldListFilter),
    )
    search_fields = ('id', 'user_id', 'from_address', 'to_address', 'phone', 'client_feedback')
    readonly_fields = ('created_at', 'updated_at', 'photo_preview', 'client_link_display', 'feedback_preview')
    list_per_page = 20
    actions = ['mark_as_delivered', 'mark_as_paid']

    fieldsets = (
        ('Основная информация', {
            'fields': ('status', 'user_id', 'client_link_display', 'from_address', 'to_address', 'phone')
        }),
        ('Детали заказа', {
            'fields': ('package_type', 'price', 'photo_preview', 'photo')
        }),
        ('Курьерская информация', {
            'fields': ('courier_id', 'courier_link', 'courier_message', 'delivery_message')
        }),
        ('Оценка и отзыв', {
            'fields': ('client_score', 'feedback_preview')  # Изменено на метод
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    # Метод для отображения client_link
    def client_link_display(self, obj):
        if obj.client_link:
            return format_html(
                '<a href="{}" target="_blank">📎 Ссылка на клиента</a>',
                obj.client_link
            )
        return "-"
    client_link_display.short_description = 'Ссылка клиента'

    # Метод для отображения отзыва с ограничением длины
    def feedback_preview(self, obj):
        if obj.client_feedback:
            preview = obj.client_feedback[:100] + '...' if len(obj.client_feedback) > 100 else obj.client_feedback
            return format_html(
                '<div title="{}">{}</div>',
                obj.client_feedback,
                preview
            )
        return "-"
    feedback_preview.short_description = 'Отзыв клиента'

    # Метод для отображения даты создания
    def get_created_at(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M") if obj.created_at else "-"
    get_created_at.short_description = 'Дата создания'
    get_created_at.admin_order_field = 'created_at'

    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'confirmed': 'blue',
            'paid': 'green',
            'assigned': 'orange',
            'delivered': 'purple',
            'completed': 'green',
            'cancelled': 'red'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 6px; border-radius: 4px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def user_link(self, obj):
        if obj.user_id:
            return format_html(
                '<a href="tg://user?id={}">👤 Клиент {}</a>',
                obj.user_id,
                obj.user_id
            )
        return "-"
    user_link.short_description = 'Клиент'

    def courier_link(self, obj):
        if obj.courier_link:
            return format_html(
                '<a href="{}" target="_blank">🛵 Курьер</a>',
                obj.courier_link
            )
        return "-"
    courier_link.short_description = 'Курьер'

    def from_address_short(self, obj):
        return obj.from_address[:30] + '...' if len(obj.from_address) > 30 else obj.from_address
    from_address_short.short_description = 'Откуда'

    def to_address_short(self, obj):
        return obj.to_address[:30] + '...' if len(obj.to_address) > 30 else obj.to_address
    to_address_short.short_description = 'Куда'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.photo.url
            )
        return "-"
    photo_preview.short_description = 'Фото посылки'

    def client_score_display(self, obj):
        if obj.client_score:
            return format_html(
                '{} ⭐',
                obj.client_score
            )
        return "-"
    client_score_display.short_description = 'Оценка'

    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')
    mark_as_delivered.short_description = "Отметить как доставленные"

    def mark_as_paid(self, request, queryset):
        queryset.update(status='paid')
    mark_as_paid.short_description = "Отметить как оплаченные"