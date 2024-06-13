from django.urls import path

from . import views
from .views import clean_database, product_detail, update_products
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("", views.index, name="index"),
    path('update-products/', update_products, name='update_products'),
    path('cleandb/', clean_database, name='clean_db'),
    path('product/<int:product_id>/', product_detail, name='product_detail'),
]
 