from django import forms
from .models import MenuItem, Order

class MenuItemForm(forms.ModelForm):
    class Meta:
            model = MenuItem
            fields = ['name', 'description', 'price', 'category', 'is_available', 'image']
            widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-coffee-300 rounded-md focus:ring-coffee-500 focus:border-coffee-500',
                'placeholder': 'Enter item name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-coffee-300 rounded-md focus:ring-coffee-500 focus:border-coffee-500',
                'rows': 3,
                'placeholder': 'Describe your menu item...'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full pl-8 pr-3 py-2 border border-coffee-300 rounded-md focus:ring-coffee-500 focus:border-coffee-500',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-coffee-300 rounded-md focus:ring-coffee-500 focus:border-coffee-500'
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-coffee-600 focus:ring-coffee-500 border-coffee-300 rounded'
            }),
            'image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*'
            })
        }

class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'p-2 border border-gray-300 rounded'})
        }
        
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(image, 'content_type') and image.content_type not in allowed_types:
                raise forms.ValidationError('Please upload a valid image file (JPEG, PNG, GIF, or WebP)')
            
            # Validate file size (5MB)
            if hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image file size must be less than 5MB')
        
        return image

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise forms.ValidationError('Price must be greater than 0')
        return price

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 2:
                raise forms.ValidationError('Item name must be at least 2 characters long')
        return name

        
        
