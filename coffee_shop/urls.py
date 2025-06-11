from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from shop.views import CustomLoginView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
    path('login/', CustomLoginView.as_view(), name='login'),  # Use custom login view
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
]
