from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from .models import MenuItem, Order, OrderItem, UserProfile
from .forms import MenuItemForm, OrderStatusForm
import json
from django.db.models import Count, Sum, Q,Avg
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views
from .models import User
from decimal import Decimal
# Add this view to your views.py

from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages

def contact(request):
    """Contact page with form handling"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            email = request.POST.get('email')
            phone = request.POST.get('phone', '')
            subject = request.POST.get('subject')
            message = request.POST.get('message')
            
            # Validate required fields
            if not all([name, email, subject, message]):
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'shop/contact.html')
            
            # Create email content
            email_subject = f"Contact Form: {subject}"
            email_message = f"""
            New contact form submission from Coffee Haven website:
            
            Name: {name}
            Email: {email}
            Phone: {phone if phone else 'Not provided'}
            Subject: {subject}
            
            Message:
            {message}
            
            ---
            This message was sent from the Coffee Haven contact form.
            """
            
            # Send email (configure your email settings in settings.py)
            try:
                send_mail(
                    email_subject,
                    email_message,
                    email,  # From email
                    ['your-email@example.com'],  # Replace with your email
                    fail_silently=False,
                )
                messages.success(request, 'Thank you for your message! We\'ll get back to you soon.')
            except Exception as e:
                # If email fails, still show success to user but log the error
                print(f"Email sending failed: {e}")
                messages.success(request, 'Thank you for your message! We\'ll get back to you soon.')
                
        except Exception as e:
            messages.error(request, 'Something went wrong. Please try again.')
            print(f"Contact form error: {e}")
    
    context = {
        'page_title': 'Contact Us',
        'meta_description': 'Get in touch with Coffee Haven. Visit us in Brgy. Calipayan, Roxas City, Capiz or contact us online.',
    }
    return render(request, 'shop/contact.html', context)
class CustomLoginView(auth_views.LoginView):
    
    """Custom login view that redirects admin users to dashboard"""
    template_name = 'registration/login.html'
    
    def get_success_url(self):
        """Redirect based on user permissions"""
        user = self.request.user
        
        # Check if user is admin/staff
        if user.is_staff or user.is_superuser:
            return reverse_lazy('admin_dashboard')
        else:
            # Regular users go to menu or home
            return reverse_lazy('home')
    
    def form_valid(self, form):
        """Add success message and login user"""
        user = form.get_user()
        login(self.request, user)
        
        if user.is_staff or user.is_superuser:
            messages.success(self.request, f'Welcome back, {user.username}! Redirecting to admin dashboard.')
        else:
            messages.success(self.request, f'Welcome back, {user.username}!')
        
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        """Handle invalid login attempts"""
        messages.error(self.request, 'Invalid username or password. Please try again.')
        return super().form_invalid(form)
@login_required
def about(request):
    """About page view"""
    context = {
        'page_title': 'About Us',
        'meta_description': 'Learn about Coffee Haven - our story, mission, and the passionate team behind your perfect cup of coffee.',
    }
    return render(request, 'shop/about.html', context)
def is_admin(user):
    return user.is_authenticated and hasattr(user, 'userprofile') and user.userprofile.is_admin
def admin_required(view_func):
    """Decorator to ensure user is admin"""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'userprofile') or not request.user.userprofile.is_admin:
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper
@admin_required
def admin_dashboard(request):
    """Admin dashboard with overview statistics"""
    # Get today's stats
    today = timezone.now().date()
    
    # Order statistics
    total_orders = Order.objects.count()
    today_orders = Order.objects.filter(created_at__date=today).count()
    pending_orders = Order.objects.filter(status='pending').count()
    preparing_orders = Order.objects.filter(status='preparing').count()
    
    # Revenue statistics
    total_revenue = Order.objects.filter(status__in=['ready', 'completed']).aggregate(
        total=Sum('total_amount'))['total'] or 0
    today_revenue = Order.objects.filter(
        created_at__date=today, 
        status__in=['ready', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Popular items (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    popular_items = OrderItem.objects.filter(
        order__created_at__date__gte=thirty_days_ago
    ).values('menu_item__name').annotate(
        total_ordered=Sum('quantity')
    ).order_by('-total_ordered')[:5]
    
    # Recent orders
    recent_orders = Order.objects.select_related('customer').prefetch_related('items__menu_item')[:10]
    
    context = {
        'page_title': 'Admin Dashboard',
        'total_orders': total_orders,
        'today_orders': today_orders,
        'pending_orders': pending_orders,
        'preparing_orders': preparing_orders,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'popular_items': popular_items,
        'recent_orders': recent_orders,
    }
    return render(request, 'admin/dashboard.html', context)
@login_required
def home(request):
    """
    Home page view for the coffee shop
    """
    # Get featured items from database - selecting variety from different categories
    featured_items = []
    
    # Get one item from each category that's available
    categories = ['coffee', 'tea', 'pastry', 'sandwich', 'dessert']
    for category in categories:
        item = MenuItem.objects.filter(
            category=category, 
            is_available=True
        ).first()
        if item:
            featured_items.append(item)
        
        # Limit to 6 featured items max
        if len(featured_items) >= 6:
            break
    
    # If we don't have enough items, fill with any available items
    if len(featured_items) < 3:
        additional_items = MenuItem.objects.filter(
            is_available=True
        ).exclude(
            id__in=[item.id for item in featured_items]
        )[:6-len(featured_items)]
        featured_items.extend(additional_items)
    
    context = {
        'page_title': 'Welcome to Coffee Haven',
        'featured_items': featured_items,
    }
    return render(request, 'home.html', context)


@login_required
def order_now(request):
    """
    Order now page view - could redirect to menu or be a separate ordering page
    """
    context = {
        'page_title': 'Order Online',
    }
    return render(request, 'order_now.html', context)
@login_required
def pending_orders(request):
    """Show active/pending orders (pending, preparing, ready)"""
    orders = Order.objects.filter(
        customer=request.user,
        status__in=['pending', 'preparing', 'ready']
    ).order_by('-created_at')
    
    context = {
        'orders': orders,
        'page_title': 'Active Orders'
    }
    return render(request, 'shop/pending_orders.html', context)

@login_required
def order_history(request):
    """Show completed order history (completed, cancelled)"""
    orders = Order.objects.filter(
        customer=request.user,
        status__in=['completed', 'cancelled']
    ).order_by('-created_at')
    
    context = {
        'orders': orders,
        'page_title': 'Order History'
    }
    return render(request, 'shop/order_history.html', context)

@login_required
def reorder(request, order_id):
    """Create a new order based on a previous order"""
    if request.method == 'POST':
        try:
          
            original_order = get_object_or_404(Order, id=order_id, customer=request.user)
            
       
            unavailable_items = []
            for item in original_order.items.all():
                if not item.menu_item.is_available:
                    unavailable_items.append(item.menu_item.name)
            
            if unavailable_items:
                messages.warning(request, f"Some items are no longer available: {', '.join(unavailable_items)}. Please check your cart.")
            
       
            cart = request.session.get('cart', {})
            items_added = 0
            
            for item in original_order.items.all():
                if item.menu_item.is_available:
                    menu_item_id = str(item.menu_item.id)
                    if menu_item_id in cart:
                        cart[menu_item_id] += item.quantity
                    else:
                        cart[menu_item_id] = item.quantity
                    items_added += item.quantity
            
            request.session['cart'] = cart
            
            if items_added > 0:
                messages.success(request, f"Added {items_added} items to your cart from order #{order_id}!")
                return redirect('cart')
            else:
                messages.error(request, "No items could be added to cart as they are all unavailable.")
                return redirect('order_history')
                
        except Exception as e:
            messages.error(request, "Error processing reorder. Please try again.")
            return redirect('order_history')
    
    return redirect('order_history')

@login_required
def category_view(request, category):

    category_name = dict(MenuItem.CATEGORY_CHOICES).get(category, category)
    
    menu_items = MenuItem.objects.filter(
        is_available=True,
        category=category
    ).order_by('name')
    
    categories = MenuItem.CATEGORY_CHOICES
    
    context = {
        'menu_items': menu_items,
        'categories': categories,
        'current_category': category,
        'category_name': category_name
    }
    
    return render(request, 'shop/menu_category.html', context)
@login_required
def menu_view(request):
    menu_items = MenuItem.objects.filter(is_available=True)
    categories = MenuItem.CATEGORY_CHOICES
    

    category_filter = request.GET.get('category')
    if category_filter:
        menu_items = menu_items.filter(category=category_filter)
    
    return render(request, 'shop/menu.html', {
        'menu_items': menu_items,
        'categories': categories
    })
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user, is_admin=False)
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('menu')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def place_order(request):
    if request.method == 'POST':
       
        cart_items = []
        for key, value in request.POST.items():
            if key.startswith('item_') and int(value) > 0:
                item_id = key.replace('item_', '')
                cart_items.append({
                    'id': int(item_id),
                    'quantity': int(value)
                })
        
        if not cart_items:
            messages.error(request, 'Your cart is empty!')
            return redirect('menu')
        
        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                notes=request.POST.get('notes', '')
            )
            
            total = 0
            for item in cart_items:
                menu_item = MenuItem.objects.get(id=item['id'])
                quantity = item['quantity']
                
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    price=menu_item.price
                )
                total += menu_item.price * quantity
            
            order.total_amount = total
            order.save()
            
        messages.success(request, f'Order #{order.id} placed successfully!')
        return redirect('order_history')
    
    return redirect('menu')
def menu_item_detail(request, item_id):
    item = get_object_or_404(MenuItem, id=item_id, is_available=True)
    
    if request.method == 'POST' and request.user.is_authenticated and not request.user.userprofile.is_admin:
        quantity = int(request.POST.get('quantity', 0))
        
        if quantity > 0:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user,
                    notes=request.POST.get('notes', '')
                )
                
                OrderItem.objects.create(
                    order=order,
                    menu_item=item,
                    quantity=quantity,
                    price=item.price
                )
                
                order.total_amount = item.price * quantity
                order.save()
                
            messages.success(request, f'Order for {quantity}x {item.name} placed successfully!')
            return redirect('order_history')
        else:
            messages.error(request, 'Please select a quantity.')

    related_items = MenuItem.objects.filter(
        category=item.category, 
        is_available=True
    ).exclude(id=item.id)[:3]
    
    return render(request, 'shop/menu_item_detail.html', {
        'item': item,
        'related_items': related_items
    })
@login_required
def order_history(request):
    orders = Order.objects.filter(customer=request.user)
    return render(request, 'shop/order_history.html', {'orders': orders})

@admin_required
def admin_menu(request):
    """Modern admin menu management with enhanced functionality"""
    from django.db.models import Avg
    
    # Get all menu items
    menu_items = MenuItem.objects.all().order_by('category', 'name')
    
    # Calculate statistics
    total_items = menu_items.count()
    available_items = menu_items.filter(is_available=True).count()
    unavailable_items = menu_items.filter(is_available=False).count()
    category_count = len(MenuItem.CATEGORY_CHOICES)
    average_price = menu_items.aggregate(avg_price=Avg('price'))['avg_price'] or 0
    
    categories = MenuItem.CATEGORY_CHOICES
    
    context = {
        'page_title': 'Menu Management',
        'menu_items': menu_items,
        'categories': categories,
        'total_items': total_items,
        'available_items': available_items,
        'unavailable_items': unavailable_items,
        'category_count': category_count,
        'average_price': average_price,
    }
    return render(request, 'shop/admin_menu.html', context)



from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json

def admin_required(view_func):
    """Decorator to ensure user is admin"""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'userprofile') or not request.user.userprofile.is_admin:
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper

@admin_required
def admin_dashboard(request):
    """Admin dashboard with overview statistics"""
    # Get today's stats
    today = timezone.now().date()
    
    # Order statistics
    total_orders = Order.objects.count()
    today_orders = Order.objects.filter(created_at__date=today).count()
    pending_orders = Order.objects.filter(status='pending').count()
    preparing_orders = Order.objects.filter(status='preparing').count()
    
    # Revenue statistics
    total_revenue = Order.objects.filter(status__in=['ready', 'completed']).aggregate(
        total=Sum('total_amount'))['total'] or 0
    today_revenue = Order.objects.filter(
        created_at__date=today, 
        status__in=['ready', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Popular items (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    popular_items = OrderItem.objects.filter(
        order__created_at__date__gte=thirty_days_ago
    ).values('menu_item__name').annotate(
        total_ordered=Sum('quantity')
    ).order_by('-total_ordered')[:5]
    
    # Recent orders
    recent_orders = Order.objects.select_related('customer').prefetch_related('items__menu_item')[:10]
    
    context = {
        'page_title': 'Admin Dashboard',
        'total_orders': total_orders,
        'today_orders': today_orders,
        'pending_orders': pending_orders,
        'preparing_orders': preparing_orders,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'popular_items': popular_items,
        'recent_orders': recent_orders,
    }
    return render(request, 'admin/dashboard.html', context)



@admin_required
def admin_orders(request):
    """Modern admin order management with enhanced functionality"""
    from django.http import JsonResponse
    from django.utils import timezone
    
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'today')
    
    if request.method == 'POST':
        # Handle order status updates
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        
        try:
            order = Order.objects.get(id=order_id)
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}.')
        except Order.DoesNotExist:
            messages.error(request, 'Order not found.')
        
        return redirect('admin_orders')
    
    # Date filtering
    today = timezone.now().date()
    if date_filter == 'today':
        date_start = today
    elif date_filter == 'yesterday':
        date_start = today - timedelta(days=1)
    elif date_filter == 'week':
        date_start = today - timedelta(days=7)
    elif date_filter == 'month':
        date_start = today - timedelta(days=30)
    else:
        date_start = None
    
    # Filter orders
    orders = Order.objects.select_related('customer__userprofile').prefetch_related('items__menu_item')
    
    if date_start:
        orders = orders.filter(created_at__date__gte=date_start)
    
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    orders = orders.order_by('-created_at')
    
    # Calculate status counts
    pending_count = orders.filter(status='pending').count()
    preparing_count = orders.filter(status='preparing').count()
    ready_count = orders.filter(status='ready').count()
    
    # Calculate today's revenue
    today_revenue = Order.objects.filter(
        created_at__date=today,
        status__in=['ready', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'page_title': 'Order Management',
        'orders': orders,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'status_choices': Order.STATUS_CHOICES,
        'pending_count': pending_count,
        'preparing_count': preparing_count,
        'ready_count': ready_count,
        'today_revenue': today_revenue,
    }
    return render(request, 'shop/admin_orders.html', context)

@admin_required
def admin_order_update_status(request, order_id):
    """Update order status via POST request"""
    if request.method == 'POST':
        try:
            order = Order.objects.get(id=order_id)
            new_status = request.POST.get('status')
            
            # Validate status
            valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
            if new_status not in valid_statuses:
                messages.error(request, 'Invalid status selected.')
                return redirect('admin_orders')
            
            old_status = order.get_status_display()
            order.status = new_status
            order.save()
            
            new_status_display = order.get_status_display()
            messages.success(request, f'Order #{order.id} status updated from "{old_status}" to "{new_status_display}".')
            
        except Order.DoesNotExist:
            messages.error(request, f'Order #{order_id} not found.')
        except Exception as e:
            messages.error(request, f'Error updating order status: {str(e)}')
    
    return redirect('admin_orders')

@admin_required  
def admin_order_detail(request, order_id):
    """API endpoint for order detail modal"""
    from django.http import JsonResponse
    
    try:
        order = Order.objects.select_related('customer').prefetch_related('items__menu_item').get(id=order_id)
        
        # Get customer phone if available
        customer_phone = ''
        if hasattr(order.customer, 'userprofile') and hasattr(order.customer.userprofile, 'phone'):
            customer_phone = order.customer.userprofile.phone or ''
        
        order_data = {
            'id': order.id,
            'customer_name': order.customer.username,
            'customer_phone': customer_phone,
            'status': order.status,
            'total': str(order.total_amount),
            'created_at': order.created_at.strftime('%B %d, %Y at %I:%M %p'),
            'notes': order.notes or '',
            'items': [
                {
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': str(item.price),
                    'total': str(item.total_price)
                }
                for item in order.items.all()
            ]
        }
        
        return JsonResponse(order_data)
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@admin_required
def admin_analytics(request):
    """Analytics dashboard with comprehensive business metrics"""
    
    # Get date range from request (default to this week)
    date_range = request.GET.get('range', 'week')
    
    # Calculate date ranges
    now = timezone.now()
    today = now.date()
    
    if date_range == 'today':
        start_date = today
        previous_start = today - timedelta(days=1)
        previous_end = today - timedelta(days=1)
    elif date_range == 'week':
        start_date = today - timedelta(days=7)
        previous_start = today - timedelta(days=14)
        previous_end = today - timedelta(days=7)
    elif date_range == 'month':
        start_date = today - timedelta(days=30)
        previous_start = today - timedelta(days=60)
        previous_end = today - timedelta(days=30)
    elif date_range == 'quarter':
        start_date = today - timedelta(days=90)
        previous_start = today - timedelta(days=180)
        previous_end = today - timedelta(days=90)
    else:  # year
        start_date = today - timedelta(days=365)
        previous_start = today - timedelta(days=730)
        previous_end = today - timedelta(days=365)
    
    # Current period orders
    current_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        status__in=['completed', 'ready']
    )
    
    # Previous period orders for comparison
    previous_orders = Order.objects.filter(
        created_at__date__gte=previous_start,
        created_at__date__lt=previous_end,
        status__in=['completed', 'ready']
    )
    
    # Key Metrics
    total_revenue = current_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    previous_revenue = previous_orders.aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    total_orders = current_orders.count()
    previous_order_count = previous_orders.count()
    
    avg_order_value = current_orders.aggregate(
        avg=Avg('total_amount')
    )['avg'] or Decimal('0')
    
    previous_aov = previous_orders.aggregate(
        avg=Avg('total_amount')
    )['avg'] or Decimal('0')
    
    # Calculate growth percentages
    def calculate_growth(current, previous):
        if previous > 0:
            return ((current - previous) / previous) * 100
        return 0 if current == 0 else 100
    
    revenue_growth = calculate_growth(float(total_revenue), float(previous_revenue))
    order_growth = calculate_growth(total_orders, previous_order_count)
    aov_growth = calculate_growth(float(avg_order_value), float(previous_aov))
    
    # Customer metrics
    total_customers = User.objects.filter(
        order__created_at__date__gte=start_date
    ).distinct().count()
    
    previous_customers = User.objects.filter(
        order__created_at__date__gte=previous_start,
        order__created_at__date__lt=previous_end
    ).distinct().count()
    
    customer_growth = calculate_growth(total_customers, previous_customers)
    
    # Revenue chart data (daily for week, weekly for month, etc.)
    revenue_chart_data = []
    if date_range == 'week':
        # Daily data for the week
        for i in range(7):
            day = today - timedelta(days=6-i)
            day_revenue = Order.objects.filter(
                created_at__date=day,
                status__in=['completed', 'ready']
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            prev_day_revenue = Order.objects.filter(
                created_at__date=day - timedelta(days=7),
                status__in=['completed', 'ready']
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            max_revenue = max(float(day_revenue), float(prev_day_revenue), 1)
            
            revenue_chart_data.append({
                'label': day.strftime('%a'),
                'amount': float(day_revenue),
                'current_width': (float(day_revenue) / max_revenue) * 100,
                'previous_width': (float(prev_day_revenue) / max_revenue) * 80,
            })
    
    # Order status distribution
    all_orders = Order.objects.filter(created_at__date__gte=start_date)
    total_all_orders = all_orders.count()
    
    order_status_data = []
    status_colors = {
        'pending': '#F59E0B',    # amber
        'preparing': '#3B82F6',  # blue
        'ready': '#10B981',      # emerald
        'completed': '#6B7280',  # gray
        'cancelled': '#EF4444',  # red
    }
    
    for status_code, status_name in Order.STATUS_CHOICES:
        count = all_orders.filter(status=status_code).count()
        percentage = (count / total_all_orders * 100) if total_all_orders > 0 else 0
        
        order_status_data.append({
            'label': status_name,
            'count': count,
            'percentage': percentage,
            'color': status_colors.get(status_code, '#6B7280')
        })
    
    # Top selling items
    top_selling_items = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__status__in=['completed', 'ready']
    ).values(
        'menu_item__name',
        'menu_item__category'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_sold')[:10]
    
    # Add item details to top selling items
    for item in top_selling_items:
        item['name'] = item['menu_item__name']
        item['category'] = item['menu_item__category']
    
    # Category performance
    category_performance = []
    category_icons = {
        'coffee': '☕',
        'tea': '🍵',
        'pastry': '🥐',
        'sandwich': '🥪',
        'dessert': '🍰',
    }
    
    max_category_revenue = 0
    categories_data = []
    
    for category_code, category_name in MenuItem.CATEGORY_CHOICES:
        category_revenue = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__status__in=['completed', 'ready'],
            menu_item__category=category_code
        ).aggregate(total=Sum('price'))['total'] or Decimal('0')
        
        category_orders = OrderItem.objects.filter(
            order__created_at__date__gte=start_date,
            order__status__in=['completed', 'ready'],
            menu_item__category=category_code
        ).values('order').distinct().count()
        
        item_count = MenuItem.objects.filter(category=category_code).count()
        
        categories_data.append({
            'name': category_name,
            'code': category_code,
            'revenue': float(category_revenue),
            'orders': category_orders,
            'item_count': item_count,
            'icon': category_icons.get(category_code, '☕')
        })
        
        max_category_revenue = max(max_category_revenue, float(category_revenue))
    
    # Calculate percentages for category performance
    for category in categories_data:
        category['percentage'] = (category['revenue'] / max_category_revenue * 100) if max_category_revenue > 0 else 0
    
    category_performance = sorted(categories_data, key=lambda x: x['revenue'], reverse=True)
    
    # Recent activities (last 10 activities)
    recent_activities = []
    recent_orders = Order.objects.filter(
        created_at__gte=now - timedelta(hours=24)
    ).order_by('-created_at')[:10]
    
    for order in recent_orders:
        if order.status == 'completed':
            activity = {
                'description': f'Order #{order.id} completed by {order.customer.username}',
                'time': order.created_at.strftime('%H:%M'),
                'icon_bg': 'bg-green-100',
                'icon_color': 'text-green-600',
                'icon_path': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>'
            }
        elif order.status == 'cancelled':
            activity = {
                'description': f'Order #{order.id} was cancelled',
                'time': order.created_at.strftime('%H:%M'),
                'icon_bg': 'bg-red-100',
                'icon_color': 'text-red-600',
                'icon_path': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>'
            }
        else:
            activity = {
                'description': f'New order #{order.id} placed by {order.customer.username}',
                'time': order.created_at.strftime('%H:%M'),
                'icon_bg': 'bg-blue-100',
                'icon_color': 'text-blue-600',
                'icon_path': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"></path>'
            }
        recent_activities.append(activity)
    
    # Generate insights
    insights = generate_insights(
        total_revenue, revenue_growth, total_orders, order_growth,
        avg_order_value, aov_growth, top_selling_items, category_performance
    )
    
    context = {
        'page_title': 'Analytics Dashboard',
        'date_range': date_range,
        
        # Key metrics
        'total_revenue': total_revenue,
        'revenue_growth': revenue_growth,
        'total_orders': total_orders,
        'order_growth': order_growth,
        'avg_order_value': avg_order_value,
        'aov_growth': aov_growth,
        'total_customers': total_customers,
        'customer_growth': customer_growth,
        
        # Chart data
        'revenue_chart_data': revenue_chart_data,
        'order_status_data': order_status_data,
        
        # Tables
        'top_selling_items': top_selling_items,
        'category_performance': category_performance,
        
        # Activity and insights
        'recent_activities': recent_activities,
        'insights': insights,
    }
    
    return render(request, 'admin/analytics.html', context)

def generate_insights(total_revenue, revenue_growth, total_orders, order_growth, 
                     avg_order_value, aov_growth, top_selling_items, category_performance):
    """Generate business insights based on analytics data"""
    
    insights = {
        'positive_insight': '',
        'opportunity_insight': '',
        'recommendation': ''
    }
    
    # Positive insights
    if revenue_growth > 10:
        insights['positive_insight'] = f"Revenue is up {revenue_growth:.1f}%! Your business is showing strong growth momentum."
    elif order_growth > 15:
        insights['positive_insight'] = f"Customer orders increased by {order_growth:.1f}%, indicating growing customer base."
    elif aov_growth > 5:
        insights['positive_insight'] = f"Average order value rose by {aov_growth:.1f}%, showing customers are spending more."
    else:
        insights['positive_insight'] = "Your business is maintaining steady performance across key metrics."
    
    # Opportunity insights
    if top_selling_items:
        top_item = top_selling_items[0]
        insights['opportunity_insight'] = f"{top_item['name']} is your bestseller with {top_item['total_sold']} units sold. Consider promoting similar items."
    
    if len(category_performance) > 1:
        best_category = category_performance[0]
        worst_category = category_performance[-1]
        if best_category['revenue'] > worst_category['revenue'] * 3:
            insights['opportunity_insight'] = f"{worst_category['name']} category is underperforming compared to {best_category['name']}. Consider menu optimization."
    
    # Recommendations
    if aov_growth < 0:
        insights['recommendation'] = "Consider bundling products or introducing premium options to increase average order value."
    elif order_growth < 5:
        insights['recommendation'] = "Focus on customer acquisition through marketing campaigns and loyalty programs."
    else:
        insights['recommendation'] = "Maintain current successful strategies while exploring new menu items based on popular categories."
    
    return insights
@admin_required
def add_menu_item(request):
    """Traditional page-based add menu item"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            price = request.POST.get('price')
            category = request.POST.get('category')
            is_available = request.POST.get('is_available') == 'True'
            image = request.FILES.get('image')
            action = request.POST.get('action', 'save_close')
            
            # Validate required fields
            if not all([name, price, category]):
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'admin/add_menu_item.html', {'categories': MenuItem.CATEGORY_CHOICES})
            
            # Create menu item
            menu_item = MenuItem.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                is_available=is_available,
                image=image
            )
            
            messages.success(request, f'Menu item "{name}" added successfully!')
            
            # Redirect based on action
            if action == 'save_add_another':
                return redirect('add_menu_item')
            else:
                return redirect('admin_menu')
                
        except Exception as e:
            messages.error(request, f'Error adding menu item: {str(e)}')
    
    context = {
        'page_title': 'Add Menu Item',
        'categories': MenuItem.CATEGORY_CHOICES,
    }
    return render(request, 'shop/add_menu_item.html', context)


@admin_required
def edit_menu_item(request, item_id):
    """Traditional page-based edit menu item"""
    try:
        menu_item = MenuItem.objects.get(id=item_id)
    except MenuItem.DoesNotExist:
        messages.error(request, 'Menu item not found.')
        return redirect('admin_menu')
    
    if request.method == 'POST':
        try:
            # Handle image removal
            if request.POST.get('remove_image') == 'true':
                menu_item.image.delete(save=False)
                menu_item.image = None
            
            # Update fields
            menu_item.name = request.POST.get('name', menu_item.name)
            menu_item.description = request.POST.get('description', menu_item.description)
            menu_item.price = request.POST.get('price', menu_item.price)
            menu_item.category = request.POST.get('category', menu_item.category)
            menu_item.is_available = request.POST.get('is_available') == 'True'
            
            # Handle new image upload
            if 'image' in request.FILES:
                menu_item.image = request.FILES['image']
            
            menu_item.save()
            
            action = request.POST.get('action', 'save_close')
            messages.success(request, f'Menu item "{menu_item.name}" updated successfully!')
            
            # Redirect based on action
            if action == 'save_continue':
                return redirect('edit_menu_item', item_id=menu_item.id)
            else:
                return redirect('admin_menu')
                
        except Exception as e:
            messages.error(request, f'Error updating menu item: {str(e)}')
    
    # Calculate item statistics
    from django.db.models import Sum, Count
    order_stats = OrderItem.objects.filter(menu_item=menu_item).aggregate(
        order_count=Count('id'),
        total_revenue=Sum('price')
    )
    
    context = {
        'page_title': 'Edit Menu Item',
        'menu_item': menu_item,
        'categories': MenuItem.CATEGORY_CHOICES,
        'order_count': order_stats['order_count'] or 0,
        'total_revenue': order_stats['total_revenue'] or 0,
    }
    return render(request, 'shop/edit_menu_item.html', context)


@admin_required
def admin_menu_update(request, item_id):
    """Update menu item"""
    from django.http import JsonResponse
    
    if request.method == 'POST':
        try:
            item = MenuItem.objects.get(id=item_id)
            
            # Update fields
            item.name = request.POST.get('name', item.name)
            item.description = request.POST.get('description', item.description)
            item.price = request.POST.get('price', item.price)
            item.category = request.POST.get('category', item.category)
            item.is_available = request.POST.get('is_available') == 'on'
            
            # Handle image upload
            if 'image' in request.FILES:
                item.image = request.FILES['image']
            
            item.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Menu item "{item.name}" updated successfully!'
            })
            
        except MenuItem.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Menu item not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@admin_required
def admin_menu_delete(request, item_id):
    """Delete menu item (No JavaScript version)"""
    if request.method == 'POST':
        try:
            item = get_object_or_404(MenuItem, id=item_id)
            item_name = item.name
            
            # Check if item is in any pending orders
            from django.db.models import Q
            pending_orders = OrderItem.objects.filter(
                menu_item=item,
                order__status__in=['pending', 'preparing']
            ).exists()
            
            if pending_orders:
                messages.error(request, f'Cannot delete "{item_name}". Item has pending orders. Mark as unavailable instead.')
                return redirect('admin_menu')
            
            item.delete()
            messages.success(request, f'Menu item "{item_name}" deleted successfully!')
            
        except Exception as e:
            messages.error(request, f'Error deleting menu item: {str(e)}')
    
    return redirect('admin_menu')


@admin_required
def admin_menu_toggle_availability(request, item_id):
    """Toggle menu item availability (No JavaScript version)"""
    if request.method == 'POST':
        try:
            item = get_object_or_404(MenuItem, id=item_id)
            item.is_available = not item.is_available
            item.save()
            
            status = "enabled" if item.is_available else "disabled"
            messages.success(request, f'"{item.name}" has been {status} successfully!')
            
        except Exception as e:
            messages.error(request, f'Error updating availability: {str(e)}')
    
    return redirect('admin_menu')

@user_passes_test(is_admin)
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}')
    return redirect('admin_orders')
def upload_menu_image(request):
    """AJAX endpoint for image upload"""
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
        # Validate file
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid file type. Please upload JPEG, PNG, GIF, or WebP files only.'
            })
        
        if image_file.size > 5 * 1024 * 1024:  # 5MB
            return JsonResponse({
                'success': False,
                'error': 'File size too large. Please upload files smaller than 5MB.'
            })
        
        try:
            # Save the file
            file_name = default_storage.save(
                f'temp/{image_file.name}',
                ContentFile(image_file.read())
            )
            file_url = default_storage.url(file_name)
            
            return JsonResponse({
                'success': True,
                'file_url': file_url,
                'file_name': file_name
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Upload failed: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'error': 'No file provided'})
