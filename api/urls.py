from django.urls import path
from .views import *

urlpatterns = [
    path('sign_up', sign_up),
    path('login', login),
    path('update_customer_information', update_customer_information),
    path('add_product_to_buyer_reserved_list', add_product_to_buyer_reserved_list),
    path('get_buyer_information', get_buyer_information)
]