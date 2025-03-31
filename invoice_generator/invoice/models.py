from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, ObjectDoesNotExist


class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The Username field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLES = (
        ('admin', 'Admin'),
        ('employee', 'Employee')
    )
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now=True)
    role = models.CharField(max_length=10, choices=ROLES, default='admin')
    shop_owner = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='employees',
        limit_choices_to={'role': 'admin'}
    )
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.username

class ShopDetails(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'})
    logo = models.ImageField(upload_to='logo/', blank=True, null=True)
    email = models.EmailField(help_text="Enter a valid email address")
    shop_name = models.CharField(max_length=150)
    smtp_password = models.CharField(help_text="App Password for email", max_length=150)
    address = models.TextField()
    updated_at = models.DateField(auto_now=True)
    
    PDF_THEMES = (
        ('theme1', 'Classic (Theme 1)'),
        ('theme2', 'Modern Minimalist (Theme 2)'),
        ('theme3', 'Bold Corporate (Theme 3)'),
    )
    pdf_theme = models.CharField(max_length=20, choices=PDF_THEMES, default='theme1')
    
    def __str__(self):
        return self.shop_name

class Product(models.Model):
    user = models.ForeignKey('invoice.CustomUser', on_delete=models.CASCADE, limit_choices_to={'role': 'admin'})
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Current stock level")
    minimum_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum stock level for alerts")

    def __str__(self):
        return self.name

    def has_sufficient_stock(self, quantity):
        """Check if there’s enough stock for a given quantity."""
        return self.stock_quantity >= quantity

    def reduce_stock(self, quantity):
        """Reduce stock by the specified quantity."""
        if self.has_sufficient_stock(quantity):
            self.stock_quantity -= quantity
            self.save()
            return True
        return False

    def add_stock(self, quantity):
        """Add stock to the product."""
        self.stock_quantity += quantity
        self.save()
        
class Customer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'})
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_customers')
    name = models.CharField(max_length=150)
    address = models.TextField()
    emailid = models.EmailField(unique=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name

class Invoice(models.Model):
    TRANSPORT_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'admin'},
        help_text="The admin user who owns this invoice"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices',
        help_text="The user (admin or employee) who created this invoice"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        help_text="The customer associated with this invoice"
    )
    customer_name = models.CharField(max_length=150, blank=True, null=True)
    customer_address = models.TextField(blank=True, null=True)
    bill_no = models.CharField(max_length=50, unique=True, editable=False)
    date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)  # New field for due date
    transport = models.CharField(max_length=100, choices=TRANSPORT_CHOICES, default='no')
    total_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=7, choices=STATUS_CHOICES, default='pending')

    def save(self, *args, **kwargs):
        # Update customer_name and customer_address if customer exists
        try:
            if self.customer:
                self.customer_name = self.customer.name
                self.customer_address = self.customer.address
            else:
                self.customer_name = None
                self.customer_address = None
        except Customer.DoesNotExist:
            self.customer_name = None
            self.customer_address = None

        # Set default due_date if not provided (e.g., 30 days from date)
        if not self.due_date:
            self.due_date = self.date + timezone.timedelta(days=30)

        # Generate bill_no if not set
        if not self.bill_no:
            with transaction.atomic():
                sequence, created = InvoiceSequence.objects.get_or_create(
                    user=self.user,
                    defaults={'last_used_bill_no': 0}
                )
                shop_details = ShopDetails.objects.filter(user=self.user).first()
                shop_name = shop_details.shop_name if shop_details else self.user.username
                shop_name = ''.join(e for e in shop_name if e.isalnum())
                next_bill_no = sequence.get_next_bill_number()
                self.bill_no = f"INV-{shop_name}-{next_bill_no:04d}"

        # Update status to 'overdue' if due_date is exceeded
        today = timezone.now().date()
        if self.status == 'pending' and self.due_date and self.due_date < today:
            self.status = 'overdue'

        super().save(*args, **kwargs)
        
    def delete(self, *args, **kwargs):
        # Restore stock for all items before deleting
        for item in self.items.all():
            item.product.add_stock(item.quantity)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.bill_no} for {self.customer_name or self.customer.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, choices=[('kg', 'Kilogram'), ('ltr', 'Liter'), ('unit', 'Unit'), ('g', 'Gram')], default='unit')
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # def save(self, *args, **kwargs):
    #     self.rate = self.product.rate
    #     self.amount = self.quantity * self.rate * (1 - self.discount / 100)
    #     super().save(*args, **kwargs)
    def save(self, *args, **kwargs):
        # Set rate from product if not provided
        if not self.rate:
            self.rate = self.product.rate

        # Calculate amount
        self.amount = self.quantity * self.rate * (1 - self.discount / 100)

        # Check and reduce stock only on creation or if quantity changes
        if not self.pk:  # New item
            if not self.product.reduce_stock(self.quantity):
                raise ValidationError(f"Insufficient stock for {self.product.name}. Available: {self.product.stock_quantity}")
        else:  # Existing item, update stock if quantity changed
            original = InvoiceItem.objects.get(pk=self.pk)
            quantity_diff = self.quantity - original.quantity
            if quantity_diff > 0:
                if not self.product.reduce_stock(quantity_diff):
                    raise ValidationError(f"Insufficient stock for {self.product.name}. Available: {self.product.stock_quantity}")
            elif quantity_diff < 0:
                self.product.add_stock(-quantity_diff)  # Add back the difference

        super().save(*args, **kwargs)

class InvoiceSequence(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'})
    last_used_bill_no = models.IntegerField(default=0)  # Global sequence starting at 0

    def get_next_bill_number(self):
        with transaction.atomic():
            self.last_used_bill_no += 1
            self.save()
            return self.last_used_bill_no

    def __str__(self):
        return f"Global invoice sequence: {self.last_used_bill_no}"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='unique_sequence_per_user'
            )
        ]