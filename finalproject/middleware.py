from django.utils.deprecation import MiddlewareMixin
import jwt
from django.db import connection, transaction
from django.http import JsonResponse
from .field_checker import error_generator
# from rest_framework.response import Response

class RemoveCurrentVersionFromPath(MiddlewareMixin):
    def process_request(self, request):
        request.path = request.path.replace('/v1', '').strip('/')
    
class AllowOrigin(MiddlewareMixin):
    def process_request(self, request):
        # This method is called before the view
        # You can modify the request here
        return None

    def process_response(self, request, response):
        # This method is called after the view
        # You can modify the response here
        response['Access-Control-Allow-Origin'] = '*'
        return response

class CheckToken(MiddlewareMixin):
    def process_request(self, request):
        exempt_urls = [
            'get_swagger_template',
            'api_documentation',
            'check_phone',
            'sign_up_buyer',
            'store_registration',
            'login',
            'place_recommender',
            'admin_login'
        ]
        
        if any(request.path == url for url in exempt_urls):
            return None
        
        auth_header = request.headers.get('Authorization')
        jwt_token = None
        
        if auth_header and auth_header.startswith('Bearer '):
            jwt_token = auth_header.split(' ')[1]  
        
        invalid_token = False
        if jwt_token is None:
            invalid_token = True
        else:
            try:
                payload = jwt.decode(jwt_token, 'uxrfcygvuh@b48651fdsa6s@#', algorithms=["HS256"])
            except Exception as e:
                invalid_token = True
            else:
                if payload.get('user_role'):
                    if payload.get('user_role') in ['buyer', 'seller']:
                        if not ('person_id' in payload and 'role_id' in payload):
                            invalid_token = True
                    elif payload.get('user_role') != 'admin':
                        invalid_token = True
                else:
                    invalid_token = True
                if not invalid_token:
                    if payload.get('user_role') in ['buyer', 'seller']:
                        request.person_id = payload['person_id']
                        request.role_id = payload['role_id']
                    request.user_role = payload['user_role']
        if invalid_token:
            return JsonResponse(
                {
                    "server_message": "توکن ارسالی به سرور معتبر نیست. دوباره وارد شوید"
                }, status=401
            )


    def process_response(self, request, response):
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    
class CheckRequiredFields(MiddlewareMixin):
    def process_request(self, request):
        path_fields = {
            'check_phone': ['phone'],
            'sign_up_buyer': ['phone', 'password', 'first_name', 'last_name', ['profile_picture'], 'latitude', 'longitude'],
            'store_registration': ['phone', 'password', 'owner_first_name', 'owner_last_name', 'store_latitude', 'store_longitude', 'store_name', 'working_times', ['store_profile_picture', 'owner_profile_picture']],
            'login': ['phone', 'password'],
            'nearby_products': ['favorite_location_id', 'group_number'],
            'place_recommender': ['query'],
            'product_details': ['product_id'],
            'add_to_cart': ['product_id', 'amount'],
            'remove_from_cart': ['product_id', 'amount'],
            'category_products': ['favorite_location_id', 'group_number', 'category_id'],
            'order_products': ['order_id'],
            'increase_wallet': ['amount'],
            'add_comment': ['product_id', 'title', 'description', 'user_score'],
            'edit_comment': ['comment_id', 'title', 'description', 'user_score'],
            'remove_comment': ['comment_id'],
            'remove_product': ['product_id'],
            'admin_login': ['username', 'password']
        }
        if any(request.path == url for url in path_fields):
            for url_path in path_fields:
                if url_path in request.path:
                    selected_path = url_path
            if error_generator(path_fields[selected_path], request):
                return JsonResponse(
                    {
                        'server_message': 'اطلاعات وارد شده ساختار معتبری ندارند'
                    }, status=400
                )

    def process_response(self, request, response):
        # This method is called after the view
        # You can modify the response here
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
class AllowMethodBasedOnRole(MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, 'user_role'):
            return None
        # if 'user_role' not in request:
        #     return None
        print('this is the user role ', request.user_role)
        buyer_methods = [
            'favorite_locations',
            'add_favorite_location',
            'edit_favorite_location',
            'remove_favorite_location',
            'nearby_products',
            'cart_items',
            'add_to_cart',
            'remove_from_cart',
            'finalize_cart',
            'orders_list',
            'category_products',
            'get_stores',
            'store_details',
            'get_profile',
            'update_profile',
            'increase_wallet_credit',
            'get_my_comments',
            'get_product_comments',
            'add_comment',
            'edit_comment',
            'remove_comment'
        ]
        seller_methods = [
            'get_seller_products',
            'remove_product',
            'get_product_unit_types',
            'get_product_general_properties',
            'get_product_exclusive_properties',
            'add_product',
            'edit_product',
            'get_seller_profile',
            'edit_seller_profile',
            'get_seller_orders',
            'complete_order'
        ]
        seller_and_buyer_methods = [
            'order_products',
            'product_details',
            'get_product_categories',
            'get_product_sub_categories',
            'get_picture',
            'place_recommender'
        ]
        invalid_access = False
        if request.user_role in ['seller', 'buyer']:
            if ((request.user_role == 'seller') and (request.path not in seller_methods)) or ((request.user_role == 'buyer') and (request.path not in buyer_methods)):
               invalid_access = True
            if invalid_access:
                if request.path in seller_and_buyer_methods:
                    invalid_access = False
        if request.user_role == 'admin':
            if request.path not in [
                'admin_login',
                'admin_top_bar',
                'admin_orders_list'
            ]:
                invalid_access = True
        if invalid_access:
            return JsonResponse(
                {
                    'server_message': 'اجازه دسترسی به منبع خواسته شده را ندارید'
                }, status=400
            )  


    def process_response(self, request, response):
        response['Access-Control-Allow-Origin'] = '*'
        return response