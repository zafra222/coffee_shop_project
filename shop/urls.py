# Updated shop/urls.py - Add/Update these order management URLs

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu_view, name='menu'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('order-now/', views.order_now, name='order_now'),
    path('orders/active/', views.pending_orders, name='pending_orders'),
    path('orders/history/', views.order_history, name='order_history'), 
    path('orders/reorder/<int:order_id>/', views.reorder, name='reorder'),
    path('register/', views.register_view, name='register'),
    path('place-order/', views.place_order, name='place_order'),
    path('menu/category/<str:category>/', views.category_view, name='menu_category'),
    path('menu/item/<int:item_id>/', views.menu_item_detail, name='menu_item_detail'),
    
    # Admin URLs (using 'manage/' prefix)
    path('manage/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage/menu/', views.admin_menu, name='admin_menu'),
    path('manage/menu/add/', views.add_menu_item, name='add_menu_item'),
    path('manage/menu/<int:item_id>/edit/', views.edit_menu_item, name='edit_menu_item'),
    path('manage/menu/<int:item_id>/update/', views.admin_menu_update, name='admin_menu_update'),
    path('manage/menu/delete/<int:item_id>/', views.admin_menu_delete, name='admin_menu_delete'),
    path('manage/menu/<int:item_id>/toggle-availability/', views.admin_menu_toggle_availability, name='admin_menu_toggle_availability'),
    
    # Order Management URLs
    path('manage/orders/', views.admin_orders, name='admin_orders'),
    path('manage/orders/<int:order_id>/detail/', views.admin_order_detail, name='admin_order_detail'),
    path('manage/orders/<int:order_id>/update-status/', views.admin_order_update_status, name='admin_order_update_status'),
    
    # Analytics
    path('manage/analytics/', views.admin_analytics, name='admin_analytics'),
]