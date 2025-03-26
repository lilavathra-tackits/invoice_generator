from django.core.management.base import BaseCommand
from faker import Faker
from invoice.models import Customer
from django.contrib.auth import get_user_model
import random

class Command(BaseCommand):
    
    def handle(self, *args, **kwargs):
        fake = Faker('en_IN')
        user = get_user_model().objects.get(username='virat')
        
        if not user:
            self.stdout.write(self.style.WARNING('No users found. Please create a user first.'))
            return
        
        # Number of customers to create
        num_customers = 20
        
        # Generate customers
        for i in range(num_customers):
            email = f"{fake.user_name()}@{fake.free_email_domain()}"
            
            name = fake.name()
            
            address = f"{fake.building_number()}, {fake.street_name()}\n{fake.city()}, {fake.state()}\n{fake.postcode()}"
            
            try:
                # Create a new customer with fake data
                customer = Customer.objects.create(
                    user=user,
                    name=name,
                    address=address,
                    emailid=email
                )
                self.stdout.write(self.style.SUCCESS(f'Successfully created customer: {customer.name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to create customer: {str(e)}'))