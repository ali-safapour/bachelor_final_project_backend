from django.urls import path
from .views import *

urlpatterns = [
    path('get_swagger_template', get_swagger_template),
    path('api_documentation', api_documentation),
    path('check_phone', check_phone),
    path('sign_up_buyer', sign_up_buyer),
    path('store_registration', store_registration),
    path('login', login),
    
    
    path('favorite_locations', favorite_locations),
    path('add_favorite_location', add_favorite_location),
    path('edit_favorite_location', edit_favorite_location),
    path('remove_favorite_location', remove_favorite_location),
    path('nearby_products', nearby_products),
    path('get_picture', get_picture),
    path('place_recommender', place_recommender),
    path('cart_items', cart_items),
    path('add_to_cart', add_to_cart),
    path('remove_from_cart', remove_from_cart),
    path('finalize_cart', finalize_cart),
    path('orders_list', orders_list),
    path('order_products', order_products),
    path('category_products', category_products),
    path('get_stores', get_stores),
    path('store_details', store_details),
    path('get_profile', get_profile),
    path('update_profile', update_profile),
    path('increase_wallet_credit', increase_wallet_credit),
    path('get_my_comments', get_my_comments),
    path('get_product_comments', get_product_comments),
    path('add_comment', add_comment),
    path('edit_comment', edit_comment),
    path('remove_comment', remove_comment),
    
    path('get_seller_products', get_seller_products),
    path('remove_product', remove_product),
    path('get_product_unit_types', get_product_unit_types),
    path('get_product_general_properties', get_product_general_properties),
    path('get_product_exclusive_properties', get_product_exclusive_properties),
    path('add_product', add_product),
    path('edit_product', edit_product),
    path('edit_product', get_seller_profile),
    path('get_seller_profile', get_seller_profile),
    path('edit_seller_profile', edit_seller_profile),
    path('get_seller_orders', get_seller_orders),
    path('complete_order', complete_order),
    
    path('product_details', product_details),
    path('get_product_categories', get_product_categories),
    path('get_product_sub_categories', get_product_sub_categories),
    
    path('admin_login', admin_login),
    path('admin_orders_list', admin_orders_list),
    path('admin_top_bar', admin_top_bar),
]