from django.core.management.base import BaseCommand
from faker import Faker
from invoice.models import Product
from django.contrib.auth import get_user_model
import random

class Command(BaseCommand):
    help = 'Generate 20 fake mobile and laptop entries with Indian prices'
    
    def handle(self, *args, **kwargs):
        fake = Faker('en_IN')  # Use Indian locale for Faker
        user = get_user_model().objects.get(username='virat')
        
        if not user:
            self.stdout.write(self.style.WARNING('No users found. Please create a user first.'))
            return
        
        # Define product categories and their price ranges (in INR)
        product_categories = {
            'mobile': {
                'prefix': ['Redmi', 'Samsung', 'OPPO', 'Vivo', 'iPhone', 'OnePlus', 'Realme', 'Poco'],
                'suffix': ['Pro', 'Ultra', 'Max', 'Note', 'Plus', 'Lite', '5G'],
                'min_price': 8000,
                'max_price': 150000,
            },
            'laptop': {
                'prefix': ['Dell', 'HP', 'Lenovo', 'Asus', 'Acer', 'Apple MacBook', 'MSI', 'Microsoft Surface'],
                'suffix': ['Pro', 'Air', 'Gaming', 'Ultrabook', 'Book', 'Notebook', 'Slim'],
                'min_price': 30000,
                'max_price': 200000,
            }
        }
        
        # Generate 10 mobiles and 10 laptops
        for _ in range(10):
            # Generate mobile
            self._create_product(fake, user, product_categories['mobile'], 'Mobile')
            
            # Generate laptop
            self._create_product(fake, user, product_categories['laptop'], 'Laptop')
    
    def _create_product(self, fake, user, category_info, product_type):
        # Generate a realistic product name
        prefix = random.choice(category_info['prefix'])
        suffix = random.choice(category_info['suffix'])
        model_number = str(random.randint(1, 20))
        name = f"{prefix} {model_number} {suffix}"
        
        # Generate product description
        if product_type == 'Mobile':
            description = f"A feature-rich {product_type.lower()} with {random.choice(['4GB', '6GB', '8GB', '12GB'])} RAM, {random.choice(['64GB', '128GB', '256GB', '512GB'])} storage, and a {random.choice(['48MP', '64MP', '108MP'])} camera."
        else:  # Laptop
            description = f"A powerful {product_type.lower()} with {random.choice(['4GB', '8GB', '16GB', '32GB'])} RAM, {random.choice(['256GB SSD', '512GB SSD', '1TB HDD', '1TB SSD'])} storage, and {random.choice(['Intel i5', 'Intel i7', 'AMD Ryzen 5', 'AMD Ryzen 7', 'Apple M1', 'Apple M2'])} processor."
        
        # Generate price in Indian Rupees
        rate = round(random.uniform(category_info['min_price'], category_info['max_price']), -2)  # Round to nearest 100
        
        # Create a new product with fake data
        product = Product.objects.create(
            user=user,
            name=name,
            description=description,
            rate=rate
        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {product_type}: {product.name} at {rate}'))