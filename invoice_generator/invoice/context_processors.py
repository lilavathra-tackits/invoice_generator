from django.utils import timezone
from datetime import timedelta
from .models import Invoice

def overdue_invoices(request):
    if request.user.is_authenticated:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if shop_owner:
                invoices = Invoice.objects.filter(user=shop_owner)
            else:
                invoices = Invoice.objects.none()
        else:
            invoices = Invoice.objects.filter(user=request.user)
        yesterday_overdue = invoices.filter(status='overdue', due_date=yesterday)
        return {'yesterday_overdue': yesterday_overdue}
    return {'yesterday_overdue': None}