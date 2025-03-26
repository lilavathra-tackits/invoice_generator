from django.urls import path
from . import views


# urlpatterns = [
#     path('', views.home, name='dashboard'),
#     path('reports/', views.reports, name='reports'),
#     path('signup/', views.signup, name='signup'),
#     path('login/', views.custom_login, name='login'),
#     path('logout/', views.logout_view, name='logout'),
#     path('shop-details/', views.shop_details, name='shop_details'),
#     path('products/', views.products_view, name='products'),
#     path('all-invoices/', views.all_invoices, name='all_invoices'),
#     path('create_invoice/', views.invoice_view, name='invoice_create'),
#     path('edit_invoice/<int:invoice_id>/', views.invoice_view, name='invoice_edit'),
#     path('get-product-rate/<int:product_id>/', views.get_product_rate, name='get_product_rate'),
#     path('delete_invoice/<int:id>/', views.delete_invoice, name='delete_invoice'),
#     path('invoice/<int:invoice_id>/pdf/', views.generate_pdf, name='generate_pdf'),
#     path('invoices/mark_paid/<int:invoice_id>/', views.mark_invoice_paid, name='mark_invoice_paid'),

# ]


urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('shop-details/', views.shop_details, name='shop_details'),
    path('', views.home, name='dashboard'),
    path('invoices/', views.all_invoices, name='all_invoices'),
    path('invoice/<int:invoice_id>/', views.invoice_view, name='invoice_edit'),
    path('create/', views.invoice_view, name='invoice_create'),
    path('customers/', views.customers_view, name='customers'),
    path('products/', views.products_view, name='products'),
    # path('mark-invoice-paid/<int:invoice_id>/', views.mark_invoice_paid, name='mark_invoice_paid'),
    path('delete-invoice/<int:id>/', views.delete_invoice, name='delete_invoice'),
    path('generate-pdf/<int:invoice_id>/', views.generate_pdf, name='generate_pdf'),
    path('reports/', views.reports, name='reports'),
    path('get-product-rate/<int:product_id>/', views.get_product_rate, name='get_product_rate'),
    path('get-customer-details/<int:customer_id>/', views.get_customer_details, name='get_customer_details'),
    path('add-employee/', views.add_employee, name='add_employee'),
    path('send-overdue-email/', views.send_overdue_email, name='send_overdue_email'),
]