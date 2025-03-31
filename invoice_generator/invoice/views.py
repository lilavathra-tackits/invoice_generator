from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout 
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from .forms import ProductForm, InvoiceForm, InvoiceItemFormSet, InvoiceItemForm, CustomerForm
from .models import CustomUser, ShopDetails, Product, Invoice, InvoiceItem, InvoiceSequence, Customer
import django.forms as forms
from django.contrib import messages
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML
from django.db import models
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDay, TruncMonth
from django.utils import timezone
import bleach
import csv
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError
from django.http import Http404
from django.db import transaction
from django.urls import reverse
from django.contrib.auth.password_validation import validate_password
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from decimal import Decimal



# Function to signup (Admin only)
def signup(request):
    """Handle user registration with email and username validation for admins."""
    if request.method == 'POST':
        try:
            email = bleach.clean(request.POST['email'])
            username = bleach.clean(request.POST['username'])
            password = request.POST['password']
            
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, "This email is already registered.")
                return redirect('signup')
            
            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, "This username is already registered.")
                return redirect('signup')
            
            # validate_password(password)   ! password validator
            user = CustomUser.objects.create_user(
                email=email,
                username=username,
                password=password,
                role='admin'  # Only admins can sign up
            )
            user.backend = 'invoice.backends.EmailOrUsernameBackend'
            messages.success(request, "Successfully Signed Up")
            return redirect('login')
        except ValidationError as e:
            messages.error(request, f"Invalid Input: {str(e)}")
            return render(request, 'registration/signup.html')
        except DatabaseError as e:
            messages.error(request, f"Database Error: {str(e)}")
            return render(request, 'registration/signup.html')
    return render(request, 'registration/signup.html')

# User login (Both admin and employee)
def custom_login(request):
    """Authenticate users via email or username and handle login."""
    try:
        if request.method == 'POST':
            identifier = bleach.clean(request.POST['identifier'])
            password = request.POST['password']
            user = authenticate(request, username=identifier, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Successfully Logged In")
                return redirect('dashboard')
            else:
                return render(request, 'registration/login.html', {'error': 'Invalid credentials'})
    except ValidationError as e:
        messages.error(request, f"Invalid input: {str(e)}")
        return render(request, 'registration/login.html')
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return render(request, 'registration/login.html')
    return render(request, 'registration/login.html')

# Logout function
def logout_view(request):
    """Handle user logout and redirect to login page."""
    try:
        logout(request)
        return redirect('login')
    except Exception as e:
        messages.error(request, f"Error Occurred: {str(e)}")
        return redirect('dashboard')


# Show account page (Admin only)
@login_required
def shop_details(request):
    """Allow admin to set up shop details."""
    if request.user.role != 'admin':
        messages.error(request, "Only shop owners can modify shop details.")
        return redirect('dashboard')
    
    try:
        if request.method == 'POST':
            print("POST data:", request.POST)
            shop_details, created = ShopDetails.objects.get_or_create(user=request.user)
            
            email = request.POST.get('email', '').strip()
            if not email:
                raise ValidationError("Email is required")
            if '@' not in email or '.' not in email:
                raise ValidationError("Please enter a valid email address")
            
            shop_details.shop_name = request.POST.get('shop_name', '').strip()
            shop_details.address = request.POST.get('address', '').strip()
            shop_details.email = email
            shop_details.smtp_password = request.POST.get('smtp_password', '').strip()
            shop_details.pdf_theme = request.POST.get('pdf_theme', 'theme1')
            
            if request.FILES.get('logo'):
                shop_details.logo = request.FILES.get('logo')
                
            shop_details.save()
            messages.success(request, "Shop Details Saved Successfully")
            return redirect('shop_details')
            
        shop_details = ShopDetails.objects.filter(user=request.user).first()
        return render(request, 'invoice/shop_details.html', {'shop_details': shop_details})
        
    except ValidationError as e:
        messages.error(request, f"Invalid input: {str(e)}")
        return redirect('shop_details')
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('shop_details')

# Products view (Admin only)
@login_required
def products_view(request):
    """Handle CRUD operations for products with search and bulk import functionality (Admin only)."""
    if request.user.role != 'admin':
        messages.error(request, "Only shop owners can manage products.")
        return redirect('dashboard')

    try:
        search_query = bleach.clean(request.GET.get('search', ''))
        products = Product.objects.filter(user=request.user)

        if search_query:
            products = products.filter(
                models.Q(name__icontains=search_query) |
                models.Q(description__icontains=search_query)
            )

        shop_details = ShopDetails.objects.filter(user=request.user).first()

        if request.method == 'POST':
            if 'delete_product' in request.POST:
                product_id = request.POST.get('product_id')
                product = get_object_or_404(Product, id=product_id, user=request.user)
                product.delete()
                messages.success(request, "Product deleted successfully.")
                return redirect('products')

            elif 'add_stock' in request.POST:
                product_id = request.POST.get('product_id')
                stock_to_add = request.POST.get('stock_quantity', 0)
                try:
                    stock_to_add = Decimal(stock_to_add)
                    if stock_to_add <= 0:
                        raise ValueError("Stock quantity must be positive.")
                    product = get_object_or_404(Product, id=product_id, user=request.user)
                    product.add_stock(stock_to_add)
                    messages.success(request, f"Added {stock_to_add} to {product.name}'s stock.")
                except (ValueError, ValidationError) as e:
                    messages.error(request, f"Error adding stock: {str(e)}")
                return redirect('products')
            
            elif 'bulk_import' in request.POST:
                # Handle bulk import
                if 'file' not in request.FILES:
                    messages.error(request, "No file uploaded.")
                    return redirect('products')
                
                csv_file = request.FILES['file']
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, "Please upload a CSV file.")
                    return redirect('products')

                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                required_fields = {'name', 'rate'}

                if not all(field in reader.fieldnames for field in required_fields):
                    messages.error(request, f"CSV must contain {', '.join(required_fields)} columns.")
                    return redirect('products')

                success_count = 0
                errors = []
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header row
                    try:
                        name = bleach.clean(row['name'].strip())
                        rate = float(row['rate'].strip())  # Convert to float for validation
                        description = bleach.clean(row.get('description', '').strip()) or None

                        if not name:
                            errors.append(f"Row {row_num}: Name is required.")
                            continue
                        if Product.objects.filter(name=name, user=request.user).exists():
                            errors.append(f"Row {row_num}: Product '{name}' already exists.")
                            continue

                        Product.objects.create(
                            user=request.user,
                            name=name,
                            rate=rate,
                            description=description
                        )
                        success_count += 1
                    except ValueError as e:
                        errors.append(f"Row {row_num}: Invalid rate value - {str(e)}")
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")

                if success_count > 0:
                    messages.success(request, f"Successfully imported {success_count} products.")
                if errors:
                    messages.error(request, "Some products failed to import:\n" + "\n".join(errors))
                return redirect('products')

            # Single product form handling
            product_id = request.POST.get('product_id', None)
            if product_id:
                product = get_object_or_404(Product, id=product_id, user=request.user)
                form = ProductForm(request.POST, instance=product)
            else:
                form = ProductForm(request.POST)
            if form.is_valid():
                product = form.save(commit=False)
                product.user = request.user
                product.save()
                messages.success(request, "Product saved successfully.")
                return redirect('products')
            else:
                messages.error(request, "Error saving product: " + str(form.errors))
        else:
            form = ProductForm()

        low_stock_products = products.filter(stock_quantity__lte=models.F('minimum_stock_level'))
        if low_stock_products.exists():
            messages.warning(request, "Some products are below minimum stock levels.")

        return render(request, 'invoice/products.html', {
            'products': products,
            'form': form,
            'shop_details': shop_details,
            'search_query': search_query,
            'low_stock_products': low_stock_products,
        })
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('products')



# All invoices view (Both admin and employee)
def all_invoices(request):
    """Display all invoices with filtering and pagination."""
    shop_details = ShopDetails.objects.filter(user=request.user).first()
    
    try:
        user = request.user

        if user.role == 'admin':
        # If user is an admin (shop owner), show all invoices for their shop
            invoices = Invoice.objects.filter(created_by__shop_owner_id=user.id) | Invoice.objects.filter(created_by=user)
        else:
        # If user is an employee, show only their own invoices
            invoices = Invoice.objects.filter(created_by__shop_owner_id=user.id) | Invoice.objects.filter(created_by=user)

        # Update statuses for pending invoices past due date
        today = timezone.now().date()
        pending_invoices = invoices.filter(status='pending', due_date__lt=today)
        for invoice in pending_invoices:
            invoice.status = 'overdue'
            invoice.save()
            
        
        search_query = bleach.clean(request.GET.get('search', ''))
        start_date = bleach.clean(request.GET.get('start_date', ''))
        end_date = bleach.clean(request.GET.get('end_date', ''))
        page_number = bleach.clean(request.GET.get('page', '1'))

        if search_query:
            invoices = invoices.filter(
                Q(customer_name__icontains=search_query) | Q(bill_no__icontains=search_query)
            )

        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                invoices = invoices.filter(date__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                invoices = invoices.filter(date__lte=end_date)
            except ValueError:
                pass

        invoices = invoices.order_by('-created_at')
        paginator = Paginator(invoices, 10)
        page_obj = paginator.get_page(page_number)

        return render(request, 'invoice/invoices.html', {
            'invoices': page_obj,
            'page_obj': page_obj,
            'search_query': search_query,
            'start_date': start_date,
            'end_date': end_date,
            'shop_details': shop_details,
        })
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return redirect('all_invoices')


# Create and Edit invoice (Both admin and employee)
@login_required
def invoice_view(request, invoice_id=None):
    """Handle creation and editing of invoices with item formsets."""
    try:
        # Determine the shop owner
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                messages.error(request, "No shop owner assigned. Contact support.")
                return redirect('dashboard')
            shop_details = ShopDetails.objects.filter(user=shop_owner).first()
        else:
            shop_owner = request.user
            shop_details = ShopDetails.objects.filter(user=request.user).first()

        if not shop_details:
            messages.error(request, "Shop details must be set up by the owner first.")
            return redirect('shop_details')

        products = Product.objects.filter(user=shop_owner)
        unit_choices = InvoiceItem._meta.get_field('unit').choices
        customers = Customer.objects.filter(user=shop_owner)

        # Get filter parameters from the request to preserve them
        search_query = bleach.clean(request.GET.get('search', ''))
        start_date = bleach.clean(request.GET.get('start_date', ''))
        end_date = bleach.clean(request.GET.get('end_date', ''))

        if invoice_id:
            invoice = get_object_or_404(Invoice, id=invoice_id, user__in=[shop_owner, request.user])
            invoice_form = InvoiceForm(instance=invoice, request=request)
            formset = InvoiceItemFormSet(instance=invoice)
            mode = 'edit'
            if not invoice.items.exists():
                formset.extra = 1
        else:
            invoice_form = InvoiceForm(request=request)
            invoice = Invoice(user=shop_owner)
            formset = InvoiceItemFormSet(instance=invoice, queryset=InvoiceItem.objects.none())
            mode = 'create'
            sequence, _ = InvoiceSequence.objects.get_or_create(user=shop_owner, defaults={'last_used_bill_no': 0})
            shop_name = shop_details.shop_name if shop_details else shop_owner.username
            shop_name = ''.join(e for e in shop_name if e.isalnum())
            next_bill_no = f"INV-{shop_name}-{(sequence.last_used_bill_no + 1):04d}"

        for form in formset:
            form.fields['product'].queryset = products

        if request.method == 'POST':
            action = request.POST.get('action')

            if invoice_id:
                invoice_form = InvoiceForm(request.POST, instance=invoice, request=request)
                formset = InvoiceItemFormSet(request.POST, instance=invoice)
                mode = 'edit'
            else:
                invoice_form = InvoiceForm(request.POST, request=request)
                invoice = Invoice(user=shop_owner, created_by=request.user)
                formset = InvoiceItemFormSet(request.POST, instance=invoice)
                mode = 'create'

            for form in formset:
                form.fields['product'].queryset = products

            if action == 'exit':
                params = {}
                if search_query:
                    params['search'] = search_query
                if start_date:
                    params['start_date'] = start_date
                if end_date:
                    params['end_date'] = end_date
                return redirect('all_invoices' + ('?' + '&'.join(f"{k}={v}" for k, v in params.items()) if params else ''))

            if invoice_form.is_valid() and formset.is_valid():
                if mode == 'create':
                    invoice = invoice_form.save(commit=False)
                    invoice.user = shop_owner
                    invoice.created_by = request.user
                    invoice.save()
                    formset.instance = invoice
                else:
                    invoice = invoice_form.save(commit=False)
                    invoice.save()

                formset.save()
                invoice.total_quantity = invoice.items.aggregate(Sum('quantity'))['quantity__sum'] or 0
                invoice.total_price = invoice.items.aggregate(Sum('amount'))['amount__sum'] or 0
                invoice.save()

                messages.success(request, f"Invoice {'created' if mode == 'create' else 'updated'} successfully.")
                return redirect('all_invoices')
            else:
                messages.error(request, f"Error saving invoice: {invoice_form.errors}")

        return render(request, 'invoice/create_invoice.html', {
            'invoice_form': invoice_form,
            'formset': formset,
            'invoice': invoice if invoice_id else None,
            'mode': mode,
            'shop_details': shop_details,
            'next_bill_no': next_bill_no if mode == 'create' else invoice.bill_no,
            'products': products,
            'unit_choices': unit_choices,
            'customers': customers,
            'search_query': search_query,
            'start_date': start_date,
            'end_date': end_date,
        })

    except ValidationError as e:
        messages.error(request, f"Invalid input: {str(e)}")
        return redirect('all_invoices')
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return redirect('all_invoices')


# Get product rate (Both admin and employee)
@login_required
def get_product_rate(request, product_id):
    try:
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                return JsonResponse({'error': 'No shop owner assigned'}, status=404)
            product = Product.objects.get(id=product_id, user=shop_owner)
        else:
            product = Product.objects.get(id=product_id, user=request.user)
        return JsonResponse({
            'rate': float(product.rate),
            'stock_quantity': float(product.stock_quantity)
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': f"Invalid product ID: {str(e)}"}, status=400)

# Customers addition (Both admin and employee)
@login_required
def customers_view(request):
    """Handle CRUD operations for customers."""
    try:
        # Determine the shop owner
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                messages.error(request, "No shop owner assigned. Contact support.")
                return redirect('dashboard')
            shop_details = ShopDetails.objects.filter(user=shop_owner).first()
        else:
            shop_owner = request.user
            shop_details = ShopDetails.objects.filter(user=request.user).first()

        if not shop_details:
            messages.error(request, "Shop details must be set up by the owner first.")
            return redirect('shop_details')

        # Handle delete request
        if 'delete' in request.GET:
            customer_id = bleach.clean(request.GET['delete'])
            customer = get_object_or_404(Customer, id=customer_id, user=shop_owner)
            customer.delete()
            messages.success(request, "Customer deleted successfully.")
            return redirect('customers')

        # Determine if we're editing
        editing_customer = None
        if 'edit' in request.GET:
            customer_id = bleach.clean(request.GET['edit'])
            editing_customer = get_object_or_404(Customer, id=customer_id, user=shop_owner)

        if request.method == 'POST':
            # Check if we're updating an existing customer
            if 'customer_id' in request.POST:
                customer_id = bleach.clean(request.POST['customer_id'])
                customer = get_object_or_404(Customer, id=customer_id, user=shop_owner)
                form = CustomerForm(request.POST, instance=customer, request=request)
                if form.is_valid():
                    new_email = form.cleaned_data['emailid'] 
                    if Customer.objects.filter(emailid=new_email).exclude(id=customer.id).exists():
                        messages.error(request, "This email is already in use by another customer.")
                        return render(request, 'invoice/customers.html', {
                            'form': form,
                            'customers': Customer.objects.filter(user=shop_owner),
                            'shop_details': shop_details,
                            'editing_customer': customer
                        })
                    customer = form.save()
                    messages.success(request, "Customer updated successfully.")
                    return redirect('customers')
            else:
                # Adding new customer
                form = CustomerForm(request.POST, request=request)
                if form.is_valid():
                    customer = form.save(commit=False)
                    customer.user = shop_owner  # Set user to the admin
                    customer.created_by = request.user  # Track who created the customer
                    customer.save()
                    messages.success(request, "Customer added successfully.")
                    return redirect('customers')
            messages.error(request, "Error processing customer. Please check the form.")
        else:
            if editing_customer:
                form = CustomerForm(instance=editing_customer, request=request)
            else:
                form = CustomerForm(request=request)
        
        customers = Customer.objects.filter(user=shop_owner)
        return render(request, 'invoice/customers.html', {
            'form': form,
            'customers': customers,
            'shop_details': shop_details,
            'editing_customer': editing_customer
        })
    except ValidationError as e:
        messages.error(request, f"Invalid input: {str(e)}")
        return redirect('customers')
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return redirect('customers')

# Get customer details (Both admin and employee)
@login_required
def get_customer_details(request, customer_id):
    """Fetch customer details via AJAX."""
    try:
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                return JsonResponse({'error': 'No shop owner assigned'}, status=404)
            customer = Customer.objects.get(id=customer_id, user=shop_owner)
        else:
            customer = Customer.objects.get(id=customer_id, user=request.user)
        return JsonResponse({'address': customer.address})
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': f"Invalid customer ID: {str(e)}"}, status=400)

# Delete invoice (Both admin and employee)
@login_required
def delete_invoice(request, id):
    """Delete a specific invoice."""
    try:
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                messages.error(request, "No shop owner assigned. Contact support.")
                return redirect('dashboard')
            invoice = get_object_or_404(Invoice, id=id, user=shop_owner)
        else:
            invoice = get_object_or_404(Invoice, id=id, user=request.user)
        
        invoice.delete()
        messages.success(request, "Invoice deleted successfully.")
        return redirect('all_invoices')
    except ObjectDoesNotExist:
        messages.error(request, "Invoice not found.")
        return redirect('all_invoices')
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return redirect('all_invoices')

# Reports view (Both admin and employee)
@login_required
def reports(request):
    """Generate advanced invoice reports with filtering and export options."""
    if request.user.role == 'employee':
        shop_owner = request.user.shop_owner
        if not shop_owner:
            messages.error(request, "No shop owner assigned. Contact support.")
            return redirect('dashboard')
        invoices = Invoice.objects.filter(user=shop_owner)
    else:
        invoices = Invoice.objects.filter(user=request.user)

    shop_details = ShopDetails.objects.filter(user=request.user).first()

    # Filters
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    report_type = request.GET.get('report_type', 'revenue_by_customer')
    export_format = request.GET.get('export', None)

    if search_query:
        invoices = invoices.filter(
            Q(customer_name__icontains=search_query) |
            Q(bill_no__icontains=search_query)
        )
    if start_date:
        invoices = invoices.filter(date__gte=start_date)
    if end_date:
        invoices = invoices.filter(date__lte=end_date)

    # Report Data
    context = {'shop_details': shop_details, 'report_type': report_type}

    if report_type == 'revenue_by_customer':
        context['report_title'] = 'Revenue by Customer'
        context['data'] = (
            invoices.values('customer__name')
            .annotate(total_revenue=Sum('total_price'), invoice_count=Count('id'))
            .order_by('-total_revenue')
        )

    elif report_type == 'top_products':
        context['report_title'] = 'Top-Selling Products'
        context['data'] = (
            InvoiceItem.objects.filter(invoice__user=shop_owner if request.user.role == 'employee' else request.user)
            .values('product__name')
            .annotate(total_sold=Sum('quantity'), total_revenue=Sum('amount'))
            .order_by('-total_revenue')
        )

    # Export Options
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
        writer = csv.writer(response)

        if report_type == 'revenue_by_customer':
            writer.writerow(['Customer', 'Total Revenue', 'Invoice Count'])
            for item in context['data']:
                writer.writerow([item['customer__name'], f"{item ['total_revenue']}", item['invoice_count']])

        elif report_type == 'top_products':
            writer.writerow(['Product', 'Total Sold', 'Total Revenue'])
            for item in context['data']:
                writer.writerow([item['product__name'], item ['total_sold'], f"{item ['total_revenue']}"])

        return response

    elif export_format == 'pdf':
        try:
            html_content = render_to_string('invoice/advanced_report_pdf.html', context)
            pdf = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
            return response
        except Exception as e:
            messages.error(request, f"PDF generation failed: {str(e)}")
            return redirect('reports')

    # Add filter values to context
    context.update({
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
        'shop_details': shop_details,
    })
    return render(request, 'invoice/reports.html', context)

# Dashboard (Both admin and employee)
@login_required
def home(request):
    """Render the homepage and update overdue invoice statuses."""
    # Determine shop owner and filter invoices based on user role
    if request.user.role == 'employee':
        shop_owner = request.user.shop_owner
        if not shop_owner:
            messages.error(request, "No shop owner assigned. Contact support.")
            return redirect('dashboard')
        shop_details = ShopDetails.objects.filter(user=shop_owner).first()
        invoices = Invoice.objects.filter(user=shop_owner)
    else:
        shop_owner = request.user
        shop_details = ShopDetails.objects.filter(user=request.user).first()
        invoices = Invoice.objects.filter(user=request.user)

    # Get filter parameters from request
    search_query = request.GET.get('search', '')
    date_filter = request.GET.get('date_filter', 'week')
    custom_start_date = request.GET.get('start_date', '')
    custom_end_date = request.GET.get('end_date', '')
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Apply search filter
    if search_query:
        invoices = invoices.filter(
            Q(customer_name__icontains=search_query) |
            Q(bill_no__icontains=search_query) |
            Q(customer__emailid__icontains=search_query)
        )

    # Date filter labels
    date_labels = {
        'day': 'Today',
        'week': 'Last 7 Days',
        'month': 'Last 30 Days',
        'all': 'All Time',
        'custom': 'Custom Range'
    }
    applied_filter_label = date_labels.get(date_filter, 'Last 7 Days')

    # Apply date filter
    if custom_start_date and custom_end_date:
        try:
            start_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(custom_end_date, '%Y-%m-%d').date()
            if start_date > end_date:
                start_date, end_date = end_date, start_date
                messages.warning(request, "Start date was after end date; dates swapped for clarity.")
            invoices = invoices.filter(date__range=[start_date, end_date])
            applied_filter_label = f"Custom: {start_date} to {end_date}"
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
    elif date_filter == 'day':
        invoices = invoices.filter(date=today)
    elif date_filter == 'week':
        invoices = invoices.filter(date__gte=today - timedelta(days=7))
    elif date_filter == 'month':
        invoices = invoices.filter(date__gte=today - timedelta(days=30))

    # Update statuses for pending invoices past due date
    pending_invoices_due = invoices.filter(status='pending', due_date__lt=today)
    if pending_invoices_due.exists():
        pending_invoices_due.update(status='overdue')

    # Yesterday’s overdue invoices (due_date was yesterday and now overdue)
    yesterday_overdue = invoices.filter(status='overdue', due_date=yesterday)

    # Invoice summaries
    total_invoices = invoices.count()
    paid_invoices = invoices.filter(status='paid').count()
    pending_invoices = invoices.filter(status='pending').count()
    overdue_invoices = invoices.filter(status='overdue').count()

    # Payment summaries
    total_payments = invoices.filter(status='paid').aggregate(Sum('total_price'))['total_price__sum'] or 0
    pending_payments = invoices.filter(status='pending').aggregate(Sum('total_price'))['total_price__sum'] or 0
    outstanding_balance = pending_payments
    total_estimate = invoices.aggregate(Sum('total_price'))['total_price__sum'] or 0
    total_revenue = total_payments  # Revenue as paid amounts

    # Summaries dictionary
    summaries = {
        'invoices': {
            'total': total_invoices,
            'paid': paid_invoices,
            'pending': pending_invoices,
            'overdue': overdue_invoices
        },
        'payments': {
            'total': total_payments,
            'pending': pending_payments,
            'outstanding': outstanding_balance,
            'estimate': total_estimate
        },
        'revenue': total_revenue,
        'tooltips': {
            'total_invoices': 'Total number of invoices created.',
            'paid_invoices': 'Invoices marked as paid.',
            'pending_invoices': 'Invoices awaiting payment.',
            'overdue_invoices': 'Invoices past due date.',
            'total_payments': 'Sum of all paid invoice amounts.',
            'pending_payments': 'Sum of amounts for pending invoices.',
            'outstanding_balance': 'Total amount still owed.',
            'total_estimate': 'Total estimated value of all invoices issued.'
        }
    }

    # Trend data for chart
    trend_period = invoices
    trend = (
        trend_period.annotate(day=TruncDay('date'))
        .values('day')
        .annotate(pending_count=Count('id', filter=Q(status='pending')))
        .annotate(paid_count=Count('id', filter=Q(status='paid')))
        .annotate(overdue_count=Count('id', filter=Q(status='overdue')))
        .order_by('day')
    )
    trend_labels = [item['day'].strftime('%b %d') for item in trend]
    trend_data = {'pending': [], 'paid': [], 'overdue': []}
    for item in trend:
        trend_data['pending'].append(item['pending_count'])
        trend_data['paid'].append(item['paid_count'])
        trend_data['overdue'].append(item['overdue_count'])

    # Revenue data for chart
    revenue_period = invoices.filter(status='paid')
    weekly_revenue = (
        revenue_period.annotate(day=TruncDay('date'))
        .values('day')
        .annotate(total=Sum('total_price'))
        .order_by('day')
    )
    revenue_labels = [item['day'].strftime('%b %d') for item in weekly_revenue]
    revenue_data = [float(item['total'] or 0) for item in weekly_revenue]

    # Recent invoices
    recent_invoices = invoices.order_by('-created_at')[:5]

    # Context for template
    context = {
        'shop_details': shop_details,
        'summaries': summaries,
        'search_query': search_query,
        'date_filter': date_filter,
        'start_date': custom_start_date,
        'end_date': custom_end_date,
        'trend_labels': trend_labels,
        'trend_data': trend_data,
        'revenue_labels': revenue_labels,
        'revenue_data': revenue_data,
        'recent_invoices': recent_invoices,
        'applied_filter_label': applied_filter_label,
        'yesterday_overdue': yesterday_overdue,
    }
    return render(request, 'invoice/dashboard.html', context)

# Send overdue email (Both admin and employee)
@login_required
def send_overdue_email(request):
    """Send overdue reminder emails to all customers with invoices due yesterday."""
    try:
        if request.method == 'POST':
            if request.user.role == 'employee':
                shop_owner = request.user.shop_owner
                if not shop_owner:
                    messages.error(request, "No shop owner assigned. Contact support.")
                    return redirect('dashboard')
                shop = ShopDetails.objects.filter(user=shop_owner).first()
                invoices = Invoice.objects.filter(user=shop_owner)
            else:
                shop = ShopDetails.objects.filter(user=request.user).first()
                invoices = Invoice.objects.filter(user=request.user)

            if not shop:
                messages.error(request, "Please set up shop details first.")
                return redirect('dashboard')

            if not shop.email or not shop.smtp_password:
                messages.error(request, "Email settings not configured in Shop Details.")
                return redirect('dashboard')

            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            yesterday_overdue = invoices.filter(status='overdue', due_date=yesterday)

            if not yesterday_overdue.exists():
                messages.info(request, "No overdue invoices from yesterday to send emails for.")
                return redirect('dashboard')

            email_backend = EmailBackend(
                host=settings.EMAIL_HOST,
                port=settings.EMAIL_PORT,
                username=shop.email,
                password=shop.smtp_password,
                use_tls=settings.EMAIL_USE_TLS
            )

            sent_count = 0
            failed_count = 0
            for invoice in yesterday_overdue:
                customer_email = invoice.customer.emailid
                if not customer_email:
                    failed_count += 1
                    continue

                # Generate PDF for attachment
                context = {
                    'invoice': invoice,
                    'items': invoice.items.all().select_related('product'),
                    'shop': shop,
                    'logo_url': request.build_absolute_uri(f"{settings.MEDIA_URL}{shop.logo.name}") if shop.logo else None,
                }
                html_content = render_to_string('invoice_pdf.html', context)
                pdf = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()

                subject = f"Overdue Invoice Reminder: {invoice.bill_no} from {shop.shop_name}"
                body = (
                    f"Dear {invoice.customer.name},\n\n"
                    f"This is a reminder that your invoice {invoice.bill_no} was due yesterday, {invoice.due_date}.\n"
                    f"Total Amount: ₹{invoice.total_price}\n\n"
                    f"Please settle the payment at your earliest convenience.\n"
                    f"A PDF copy of the invoice is attached for your reference.\n\n"
                    f"Thank you,\n"
                    f"{shop.shop_name}"
                )
                filename = f"invoice-{invoice.bill_no}-{invoice.customer.name}.pdf"

                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=shop.email,
                    to=[customer_email],
                    connection=email_backend
                )
                email.attach(filename, pdf, 'application/pdf')
                try:
                    email.send(fail_silently=False)
                    sent_count += 1
                except Exception as e:
                    failed_count += 1

            if sent_count > 0:
                messages.success(request, f"Sent overdue reminders to {sent_count} customer(s) successfully.")
            if failed_count > 0:
                messages.warning(request, f"Failed to send emails to {failed_count} customer(s) due to missing emails or errors.")
        else:
            messages.error(request, "Invalid request method.")
    except Exception as e:
        messages.error(request, f"Failed to send emails: {str(e)}")
    return redirect('dashboard')

# Generate PDF (Both admin and employee)
@login_required
def generate_pdf(request, invoice_id):
    """Generate PDF version of an invoice and email it to the customer using shop email."""
    try:
        if request.user.role == 'employee':
            shop_owner = request.user.shop_owner
            if not shop_owner:
                messages.error(request, "No shop owner assigned. Contact support.")
                return redirect('dashboard')
            shop = ShopDetails.objects.filter(user=shop_owner).first()
        else:
            shop = ShopDetails.objects.filter(user=request.user).first()

        invoice = get_object_or_404(Invoice, id=invoice_id, user=shop.user)
        items = invoice.items.all().select_related('product')
        customers = Customer.objects.filter(user=shop.user)

        if not shop:
            messages.error(request, "Please set up shop details first.")
            return redirect('shop_details')

        logo_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{shop.logo.name}") if shop.logo else None

        context = {
            'invoice': invoice,
            'items': items,
            'shop': shop,
            'logo_url': logo_url,
            'customer': customers,
        }

        # Pdf themes 
        theme_map = {
            'theme1': 'invoice/themes/invoice_pdf_theme1.html',
            'theme2': 'invoice/themes/invoice_pdf_theme2.html',
            'theme3': 'invoice/themes/invoice_pdf_theme3.html',
        }
        template_name = theme_map.get(shop.pdf_theme, 'invoice/invoice_pdf_theme1.html')  # default 1

        html_content = render_to_string(template_name, context)
        pdf = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()

        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"invoice-{invoice.bill_no}-{invoice.customer.name}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        try:
            customer_email = invoice.customer.emailid
            if not customer_email:
                messages.warning(request, "PDF generated but could not send email: Customer email not found.")
            else:
                if not shop.email or not shop.smtp_password:
                    messages.warning(request, "PDF generated but email not sent: Please configure email settings in Shop Details")
                else:
                    email_backend = EmailBackend(
                        host=settings.EMAIL_HOST,
                        port=settings.EMAIL_PORT,
                        username=shop.email,
                        password=shop.smtp_password,
                        use_tls=settings.EMAIL_USE_TLS
                    )

                    subject = f"Invoice {invoice.bill_no} from {shop.shop_name}"
                    body = (
                        f"Dear {invoice.customer.name},\n\n"
                        f"Please find attached your invoice {invoice.bill_no}.\n"
                        f"Total Amount: {invoice.total_price}\n"
                        f"Date: {invoice.date}\n\n"
                        f"Thank you for your business!\n"
                        f"{shop.shop_name}"
                    )
                    
                    email = EmailMessage(
                        subject=subject,
                        body=body,
                        from_email=shop.email,
                        to=[customer_email],
                        connection=email_backend
                    )
                    email.attach(filename, pdf, 'application/pdf')
                    email.send(fail_silently=False)

                    messages.success(request, f"PDF generated and emailed to {customer_email} successfully.")

        except ValidationError as e:
            messages.error(request, f"PDF generated but email failed: Invalid email data - {str(e)}")
        except Exception as e:
            messages.error(request, f"PDF generated but email failed: {str(e)}")

        return response

    except Http404:
        messages.error(request, "Invoice not found.")
        return redirect('all_invoices')
    except DatabaseError as e:
        messages.error(request, f"Database error: {str(e)}")
        return redirect('all_invoices')
    except Exception as e:
        messages.error(request, f"PDF generation failed: {str(e)}")
        return redirect('all_invoices')


#  Add employee (Admin only)
@login_required
def add_employee(request):
    """Allow admin to create, edit, and delete employee accounts."""
    shop_details = ShopDetails.objects.filter(user=request.user).first()  # Get shop details for logo display

    if request.user.role != 'admin':
        messages.error(request, "Only shop owners can manage employees.")
        return redirect('dashboard')

    if request.method == 'POST':
        if 'delete_employee' in request.POST:  # Handle delete request
            employee_id = request.POST.get('employee_id')
            employee = get_object_or_404(CustomUser, id=employee_id, shop_owner=request.user)
            try:
                employee.delete()
                messages.success(request, "Employee deleted successfully.")
            except DatabaseError:
                messages.error(request, "Error deleting the employee. Please try again.")
            return redirect('add_employee')

        username = bleach.clean(request.POST.get('username', '').strip())
        email = bleach.clean(request.POST.get('email', '').strip())
        password = request.POST.get('password', '')
        employee_id = request.POST.get('employee_id', None)

        if not username or not email or (not password and not employee_id):
            messages.error(request, "All fields are required.")
            return redirect('add_employee')

        # Check for existing username/email
        if CustomUser.objects.filter(username=username).exclude(id=employee_id).exists():
            messages.error(request, "This username is already taken.")
            return redirect('add_employee')
        if CustomUser.objects.filter(email=email).exclude(id=employee_id).exists():
            messages.error(request, "This email is already registered.")
            return redirect('add_employee')

        try:
            if employee_id:  # Editing an existing employee
                employee = get_object_or_404(CustomUser, id=employee_id, shop_owner=request.user)
                employee.username = username
                employee.email = email
                if password:  # Update password only if provided
                    employee.set_password(password)
                employee.save()
                messages.success(request, f"Employee {username} updated successfully.")
            else:  # Adding a new employee
                CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role='employee',
                    shop_owner=request.user
                )
                messages.success(request, f"Employee {username} created successfully.")
        except DatabaseError:
            messages.error(request, "Database error occurred. Please try again.")

        return redirect('add_employee')

    employees = CustomUser.objects.filter(role='employee', shop_owner=request.user)

    return render(request, 'invoice/add_employee.html', {
        'employees': employees,
        'shop_details': shop_details
    })