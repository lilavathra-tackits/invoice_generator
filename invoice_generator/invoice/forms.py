from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceItem, Product, Customer


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'rate']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_rate(self):
        rate = self.cleaned_data['rate']
        if rate < 0:
            raise forms.ValidationError("Rate cannot be negative.")
        return rate


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'quantity', 'unit', 'rate', 'discount', 'amount']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'unit': forms.Select(choices=InvoiceItem._meta.get_field('unit').choices, attrs={'class': 'form-select'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super(InvoiceItemForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['rate'].initial = self.instance.product.rate
            self.fields['amount'].initial = self.instance.quantity * self.instance.rate * (1 - self.instance.discount / 100)

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)
        instance.rate = self.instance.product.rate
        instance.amount = instance.quantity * instance.rate * (1 - instance.discount / 100)
        return super().save(*args, **kwargs)


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'date', 'due_date', 'transport', 'status']  # Added 'due_date'

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(InvoiceForm, self).__init__(*args, **kwargs)

        # Filter customer queryset based on user role
        if self.request:
            if self.request.user.role == 'employee':
                self.fields['customer'].queryset = Customer.objects.filter(user=self.request.user.shop_owner)
            else:
                self.fields['customer'].queryset = Customer.objects.filter(user=self.request.user)

        # Ensure customer field is a select dropdown
        self.fields['customer'].widget = forms.Select(attrs={'class': 'form-select'})

        # Date and due_date fields with date picker
        self.fields['date'].widget = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        self.fields['due_date'].widget = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})

        # Transport choices
        TRANSPORT_CHOICES = [
            ('yes', 'Yes'),
            ('no', 'No'),
        ]
        self.fields['transport'].widget = forms.Select(attrs={'class': 'form-select'}, choices=TRANSPORT_CHOICES)

        # Status choices
        self.fields['status'].widget = forms.Select(attrs={'class': 'form-select'}, choices=Invoice.STATUS_CHOICES)

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        due_date = cleaned_data.get('due_date')

        # Validate that due_date is not before date
        if date and due_date and due_date < date:
            raise forms.ValidationError("Due date cannot be earlier than the invoice date.")

        return cleaned_data

    def save(self, commit=True):
        invoice = super().save(commit=False)

        # Ensure that customer is assigned to the invoice
        if not invoice.customer:
            raise forms.ValidationError("An invoice must have a customer.")

        # Set the user based on request
        if self.request:
            if self.request.user.role == 'employee':
                invoice.user = self.request.user.shop_owner
                invoice.created_by = self.request.user
            else:
                invoice.user = self.request.user
                invoice.created_by = self.request.user

        if commit:
            invoice.save()
        return invoice

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'address', 'emailid']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'emailid': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CustomerForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        customer = super().save(commit=False)
        if self.request:
            customer.user = self.request.user
        if commit:
            customer.save()
        return customer

InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        'unit': forms.Select(choices=InvoiceItem._meta.get_field('unit').choices, attrs={'class': 'form-select'}),
        'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
        'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
        'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
    }
)