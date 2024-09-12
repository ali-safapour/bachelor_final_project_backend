import traceback
import uuid
import os
import time
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import redirect, render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection, transaction
import jwt
import phonenumbers
from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type
import hashlib
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import json
import requests
from .custom_modules.Haversin import haversine
from django.http import FileResponse
from .custom_modules.EncodeDecode import encrypt, decrypt
from .custom_modules.EpochToJalali import epoch_to_jalali

key = "xkjKL!442vrEzE97b@T%1IP*4Bl5FB74HevPSbR6qao4NHE="

map_service_addr = 'map' if os.environ.get(
    'AM_I_IN_A_DOCKER_CONTAINER', False) else 'localhost'
map_service_port = 8080 if os.environ.get(
    'AM_I_IN_A_DOCKER_CONTAINER', False) else 8190
map_complete_addr = f'http://{map_service_addr}:{map_service_port}'

group_size = 10

invalid_fields_response = {
    'server_message': 'فیلدها را به درستی پر نکرده‌اید'
}


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict.
    Assume the column names are unique.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@api_view(['GET'])
def get_swagger_template(request):
    file_location = 'static/openapi.yaml'

    with open(file_location, 'r') as f:
        file_data = f.read()

    response = HttpResponse(file_data, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="openapi.yaml"'

    return response


@api_view(['GET'])
def api_documentation(request):
    return redirect("http://127.0.0.1:7171")


@api_view(['POST'])
def check_phone(request):
    try:
        phone = str(int(request.POST.get('phone')))
        if not carrier._is_mobile(number_type(phonenumbers.parse(phone, "IR"))):
            raise Exception
    except:
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT * FROM person
                    WHERE phone = '{}'
                """.format(phone)
            )
            row = dictfetchall(cursor)
            if len(row):
                return Response({
                    'server_message': 'شماره تلفن از قبل وجود دارد'
                }, status=409)
            return Response(
                {
                    "server_message": "می‌توانید ثبت نام کنید"
                }, status=200
            )


@api_view(['POST'])
def sign_up_buyer(request):
    try:
        phone = str(int(request.POST.get('phone')))
        password = request.POST.get('password')
        password = str(request.POST.get('password'))
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        latitude = str(request.POST.get('latitude'))
        longitude = str(request.POST.get('longitude'))
        if not carrier._is_mobile(number_type(phonenumbers.parse(phone, "IR"))):
            raise Exception
    except:
        return Response(invalid_fields_response, status=400)
    try:
        location_data = requests.get(url=f'{map_complete_addr}/reverse', params={
                                     'lat': latitude, 'lon': longitude, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except Exception as e:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )
        location_data = location_data['address']
    if ('city' not in location_data or 'suburb' not in location_data) and ('neighbourhood' not in location_data):
        return Response(
            {
                'server_message': 'مکان انتخابی دارای جزئیات کافی نمی‌باشد. مکان دیگری را انتخاب کنید'
            }, status=400
        )
    profile_picture = request.FILES.get('profile_picture')
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT * FROM person
                    WHERE phone = '{}'
                """.format(phone)
            )
            row = dictfetchall(cursor)
            if len(row):
                return Response({
                    'server_message': 'شماره تلفن از قبل وجود دارد'
                }, status=409)
            cursor.execute(
                """
                    INSERT INTO person (name, lastname, phone, password_hash)
                    VALUES (%s, %s, %s, %s)
                    RETURNING person_id
                """, [first_name, last_name, phone, hashlib.sha256(bytes(password, 'utf-8')).hexdigest()]
            )
            person_id = dictfetchall(cursor)[0]['person_id']

            cursor.execute(
                f"""
                    INSERT INTO buyer (person_id, current_location)
                    VALUES (%s, %s)
                    RETURNING buyer_id
                """, [person_id, f'{latitude}-{longitude}']
            )
            buyer_id = dictfetchall(cursor)[0]['buyer_id']
            cursor.execute(
                f"""
                    INSERT INTO buyer_favorite_location (buyer_id, location,
                    city, neighborhood)
                    VALUES (%s, %s, %s, %s)
                """, [buyer_id, f'{latitude}-{longitude}', location_data.get('suburb') if location_data.get('suburb') else location_data.get('city'), location_data['neighbourhood']]
            )
            cursor.execute(
                f"""
                    INSERT INTO wallet (person_id)
                    VALUES (%s)
                """, [person_id]
            )

    if profile_picture:
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'person')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        fs = FileSystemStorage(location=upload_dir)
        file_name = str(person_id) + os.path.splitext(profile_picture.name)[1]
        file_path = fs.path(file_name)
        if fs.exists(file_name):
            os.remove(file_path)
        filename = fs.save(file_name, profile_picture)
        # file_url = fs.url(filename)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE person
                    SET profile_picture = %s
                    WHERE person_id = %s
                """, [file_name, person_id]
            )
    return Response(
        {
            "server_message": "ثبت نام با موفقیت انجام شد",
            "user_role": 'buyer',
            "jwt": jwt.encode({"user_role": 'buyer', "person_id": person_id, "role_id": buyer_id}, "uxrfcygvuh@b48651fdsa6s@#", algorithm="HS256")
        }, status=200)


@api_view(['POST'])
def store_registration(request):
    invalid_fields_response = dict()
    invalid_fields_response.update(
        {
            'server_message': 'فیلدها را به درستی پر نکرده‌اید'
        }
    )
    try:
        phone = str(int(request.POST.get('phone')))
        password = request.POST.get('password')
        owner_first_name = request.POST.get('owner_first_name')
        owner_last_name = request.POST.get('owner_last_name')
        owner_profile_picture = request.FILES.get('owner_profile_picture')
        store_profile_picture = request.FILES.get('store_profile_picture')
        store_name = request.POST.get('store_name')
        store_latitude = request.POST.get('store_latitude')
        store_longitude = request.POST.get('store_longitude')
        if not carrier._is_mobile(number_type(phonenumbers.parse(phone, "IR"))):
            raise Exception
    except:
        return Response(invalid_fields_response, status=400)

    try:
        location_data = requests.get(url=f'{map_complete_addr}/reverse', params={
                                     'lat': store_latitude, 'lon': store_longitude, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )
        location_data = location_data['address']
    if ('city' not in location_data or 'suburb' not in location_data) and ('neighbourhood' not in location_data):
        return Response(
            {
                'server_message': 'مکان انتخابی دارای جزئیات کافی نمی‌باشد. مکان دیگری را انتخاب کنید'
            }, status=400
        )
    store_profile_picture = request.FILES.get('store_profile_picture')
    working_times = request.POST.get('working_times')
    invalid_fields = False
    try:
        working_times = json.loads(working_times)
    except:
        invalid_fields = True
    else:
        for day_details in working_times:
            if not ('day_sequence_id' in day_details and
                    str(day_details['day_sequence_id']).isnumeric() and
                    int(day_details['day_sequence_id']) in range(1, 8) and
                    'is_holiday_binary' in day_details and
                    str(day_details['is_holiday_binary']).isnumeric() and
                    int(day_details['is_holiday_binary']) in range(2) and
                    'times' in day_details and
                    'start' in day_details['times'] and 'end'
                    in day_details['times']):
                invalid_fields = True
                break
    if invalid_fields:
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT * FROM person
                    WHERE phone = '{}'
                """.format(phone)
            )
            row = dictfetchall(cursor)
            if len(row):
                return Response({
                    'server_message': 'شماره تلفن از قبل وجود دارد'
                }, status=409)
            cursor.execute(
                """
                    INSERT INTO person (name, lastname, phone, password_hash)
                    VALUES (%s, %s, %s, %s)
                    RETURNING person_id
                """, [owner_first_name, owner_last_name, phone, hashlib.sha256(bytes(password, 'utf-8')).hexdigest()]
            )
            person_id = dictfetchall(cursor)[0]['person_id']
            cursor.execute(
                f"""
                    INSERT INTO seller (person_id)
                    VALUES (%s)
                    RETURNING seller_id
                """, [person_id]
            )
            seller_id = dictfetchall(cursor)[0]['seller_id']

            cursor.execute(
                """
                    INSERT INTO store (name, seller_id)
                    VALUES (%s, %s)
                    RETURNING store_id
                """, [store_name, seller_id]
            )
            store_id = dictfetchall(cursor)[0]['store_id']

            cursor.execute(
                """
                    INSERT INTO store_location (store_id, location, city, neighborhood)
                    VALUES (%s, %s, %s, %s)
                """, [store_id, f'{store_latitude}-{store_longitude}', location_data.get('suburb') if location_data.get('suburb') else location_data.get('city'), location_data['neighbourhood']]
            )

            for day_details in working_times:
                days = ['saturday', 'sunday', 'monday',
                        'tuesday', 'wednesday', 'thursday', 'friday']
                day = days[day_details['day_sequence_id'] - 1]
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                            INSERT INTO working_time ({day}_holiday_status,
                            {day}_start_working_time, {day}_end_working_time, store_id)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (store_id) DO UPDATE SET
                                {day}_holiday_status = EXCLUDED.{day}_holiday_status,
                                {day}_start_working_time = EXCLUDED.{day}_start_working_time,
                                {day}_end_working_time = EXCLUDED.{day}_end_working_time
                        """, [day_details['is_holiday_binary'], day_details['times']['start'], day_details['times']['end'], store_id]
                    )
    if owner_profile_picture:
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'person')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        fs = FileSystemStorage(location=upload_dir)
        file_name = str(person_id) + \
            os.path.splitext(owner_profile_picture.name)[1]
        file_path = fs.path(file_name)
        if fs.exists(file_name):
            os.remove(file_path)
        filename = fs.save(file_name, owner_profile_picture)
        # file_url = fs.url(filename)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE person
                    SET profile_picture = %s
                    WHERE person_id = %s
                """, [file_name, person_id]
            )
    if store_profile_picture:
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'store')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        fs = FileSystemStorage(location=upload_dir)
        file_name = str(store_id) + \
            os.path.splitext(store_profile_picture.name)[1]
        file_path = fs.path(file_name)
        if fs.exists(file_name):
            os.remove(file_path)
        filename = fs.save(file_name, store_profile_picture)
        # file_url = fs.url(filename)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE store
                    SET profile_picture = %s
                    WHERE store_id = %s
                """, [file_name, store_id]
            )
    return Response(
        {
            "server_message": "ثبت نام با موفقیت انجام شد",
            "user_role": 'seller',
            "jwt": jwt.encode({"user_role": 'seller', "person_id": person_id, "role_id": seller_id}, "uxrfcygvuh@b48651fdsa6s@#", algorithm="HS256")
        }, status=200)


@api_view(['POST'])
def login(request):
    try:
        phone = str(int(request.POST.get('phone')))
        password = request.POST.get('password')
        if not carrier._is_mobile(number_type(phonenumbers.parse(phone, "IR"))):
            raise Exception
    except:
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT p.person_id, b.buyer_id, s.seller_id
                    FROM person p
                    LEFT JOIN buyer b ON p.person_id = b.person_id
                    LEFT JOIN seller s ON p.person_id = s.person_id
                    WHERE p.phone = %s AND p.password_hash = %s
                """, [phone, hashlib.sha256(bytes(password, 'utf-8')).hexdigest()]
            )
            res = dictfetchall(cursor)

            if not len(res):
                return Response({
                    'server_message': 'شماره تلفن یا رمز عبور وارد شده صحیح نیست'
                }, status=400)

            user_role = 'buyer' if res[0]['buyer_id'] != None else 'seller'
            person_id = res[0]['person_id']
            role_id = res[0]['buyer_id'] if res[0]['buyer_id'] != None else res[0]['seller_id']

    return Response({
        "server_message": "ورود با موفقیت انجام شد",
        "user_role": user_role,
        "jwt": jwt.encode({"user_role": user_role, "person_id": person_id, "role_id": role_id}, "uxrfcygvuh@b48651fdsa6s@#", algorithm="HS256")
    }, status=200)


@api_view(['GET'])
def favorite_locations(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                    SELECT *
                    FROM buyer_favorite_location
                    WHERE buyer_id IN (
                        SELECT buyer_id
                        FROM buyer
                        WHERE person_id = %s
                    )
                """, [request.person_id]
        )
        res = dictfetchall(cursor)
        res_list = list()
        for item in res:
            res_list.append(
                {
                    'id': int(item['buyer_favorite_location_id']),
                    'title': '، '.join([item['neighborhood'], item['city']]),
                    'latitude': float(item['location'].split('-')[0]),
                    'longitude': float(item['location'].split('-')[1])
                }
            )
        return Response(res_list, status=200)


@api_view(['POST'])
def add_favorite_location(request):
    try:
        latitude = float(request.POST.get('latitude'))
        longitude = float(request.POST.get('longitude'))
    except Exception as e:
        print(e)
        return Response(invalid_fields_response, status=400)
    try:
        location_data = requests.get(url=f'{map_complete_addr}/reverse', params={
                                     'lat': latitude, 'lon': longitude, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except Exception as e:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )
        location_data = location_data['address']
    if ('city' not in location_data or 'suburb' not in location_data) and ('neighbourhood' not in location_data):
        return Response(
            {
                'server_message': 'مکان انتخابی دارای جزئیات کافی نمی‌باشد. مکان دیگری را انتخاب کنید'
            }, status=400
        )
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM buyer_favorite_location
                WHERE buyer_id = %s
            """, [request.role_id]
        )
        favorite_locations = dictfetchall(cursor)
        if len(favorite_locations):
            for saved_location in favorite_locations:
                if saved_location['city'] == (location_data.get('suburb') if location_data.get('suburb') else location_data.get('city')) and saved_location['neighborhood'] == location_data['neighbourhood']:
                    return Response(
                        {
                            'server_message': 'مکان انتخاب شده نزدیک به یکی از مکان‌های قبلی است'
                        }, status=400
                    )
        cursor.execute(
            """
                INSERT INTO buyer_favorite_location(location, city,
                neighborhood, buyer_id)
                VALUES (%s, %s, %s, %s)
                RETURNING buyer_favorite_location_id, city, neighborhood, city,
                location
            """, [f'{latitude}-{longitude}', location_data.get('suburb') if location_data.get('suburb') else location_data.get('city'), location_data['neighbourhood'], request.role_id]
        )
        inserted_row = dictfetchall(cursor)[0]
        return Response(
            {
                'server_message': 'مکان جدید اضافه شد',
                'id': inserted_row['buyer_favorite_location_id'],
                'title': inserted_row['city']+'، '+inserted_row['neighborhood'],
                'latitude': latitude,
                'longitude': longitude
            }, status=200
        )


@api_view(['POST'])
def edit_favorite_location(request):
    try:
        favorite_location_id = int(request.POST.get('favorite_location_id'))
        latitude = float(request.POST.get('latitude'))
        longitude = float(request.POST.get('longitude'))
    except:
        return Response(invalid_fields_response, status=400)
    try:
        location_data = requests.get(url=f'{map_complete_addr}/reverse', params={
                                     'lat': latitude, 'lon': longitude, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except Exception as e:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )
        location_data = location_data['address']
    if ('city' not in location_data or 'suburb' not in location_data) and ('neighbourhood' not in location_data):
        return Response(
            {
                'server_message': 'مکان انتخابی دارای جزئیات کافی نمی‌باشد. مکان دیگری را انتخاب کنید'
            }, status=400
        )
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM buyer_favorite_location
                WHERE buyer_id = %s
            """, [request.role_id]
        )
        favorite_locations = dictfetchall(cursor)
        if len(favorite_locations):
            for saved_location in favorite_locations:
                if saved_location['buyer_favorite_location_id'] == favorite_location_id:
                    continue
                if saved_location['city'] == location_data.get('suburb') if location_data.get('suburb') else location_data.get('city') and saved_location['neighborhood'] == location_data['neighbourhood']:
                    return Response(
                        {
                            'server_message': 'مکان انتخاب شده نزدیک به یکی از مکان‌های قبلی است'
                        }, status=400
                    )
        cursor.execute(
            """
                SELECT *
                FROM buyer_favorite_location
                WHERE buyer_id = %s and buyer_favorite_location_id = %s
            """, [request.role_id, favorite_location_id]
        )
        res = dictfetchall(cursor)
        if not len(res):
            return Response(
                {
                    'server_message': 'چنین مکانی برای شما ثبت نشده'
                }, status=400
            )
        cursor.execute(
            """
                UPDATE buyer_favorite_location
                SET location = %s, city = %s, neighborhood = %s
                WHERE buyer_favorite_location_id = %s AND buyer_id = %s
                RETURNING buyer_favorite_location_id, city, neighborhood
            """, [f'{latitude}-{longitude}', location_data.get('suburb') if location_data.get('suburb') else location_data.get('city'), location_data['neighbourhood'], favorite_location_id, request.role_id]
        )
        edited_row = dictfetchall(cursor)
        if len(res):
            edited_row = edited_row[0]
            return Response(
                {
                    'server_message': 'مکان انتخابی ویرایش شد',
                    'id': favorite_location_id,
                    'title': edited_row['city']+'، '+edited_row['neighborhood'],
                    'latitude': latitude,
                    'longitude': longitude
                }, status=200
            )


@api_view(['POST'])
def remove_favorite_location(request):
    try:
        favorite_location_id = int(request.POST.get('favorite_location_id'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM buyer_favorite_location
                WHERE buyer_id = %s
            """, [request.role_id]
        )
        res = dictfetchall(cursor)
        if len(res) < 2:
            return Response(
                {
                    'server_message': 'حداقل یک مکان منتخب باید باقی‌بماند'
                }, status=400
            )
        cursor.execute(
            """
                DELETE FROM buyer_favorite_location
                WHERE buyer_favorite_location_id = %s AND buyer_id = %s
                RETURNING buyer_id
            """, [favorite_location_id, request.role_id]
        )
        res = dictfetchall(cursor)
        if len(res):
            return Response(
                {
                    'server_message': 'مکان موردنظر حذف شد'
                }, status=200
            )
        else:
            return Response(
                {
                    'server_message': 'چنین مکانی برای شما ثبت نشده'
                }, status=400
            )


@api_view(['POST'])
def nearby_products(request):
    try:
        favorite_location_id = int(request.POST.get('favorite_location_id'))
        group_number = int(request.POST.get('group_number'))
    except:
        return Response(invalid_fields_response, status=400)
    empty_product_list = {
        "group_number": group_number,
        "products_per_group": group_size,
        "products": list()
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT buyer_id FROM
                person p
                LEFT JOIN buyer b on (p.person_id = b.person_id)
                WHERE p.person_id = %s
            """, [request.person_id]
        )
        buyer_id = dictfetchall(cursor)[0]['buyer_id']
        cursor.execute(
            """
                SELECT * FROM buyer_favorite_location
                WHERE buyer_favorite_location_id = %s and buyer_id = %s
            """, [favorite_location_id, buyer_id]
        )
        # TODO: What if there is not such a place
        try:
            res = dictfetchall(cursor)[0]
        except:
            return Response(empty_product_list, status=200)
        buyer_latitude = float(res['location'].split('-')[0])
        buyer_longitude = float(res['location'].split('-')[1])
        buyer_city = res['city']
        cursor.execute(
            """
                SELECT * FROM store_location
                WHERE city = %s
            """, [buyer_city]
        )
        stores = dictfetchall(cursor)
        nearby_stores = list()
        for store in stores:
            store_latitude = float(store['location'].split('-')[0])
            store_longitude = float(store['location'].split('-')[1])

            if (distance := haversine(buyer_latitude, buyer_longitude, store_latitude, store_longitude)) <= 5000:
                nearby_stores.append(
                    {
                        'store_id': store['store_id'],
                        'distance': distance
                    }
                )
        # cursor.execute(
        #     """
        #         SELECT COUNT(*) as total_products
        #         FROM PRODUCT p
        #         WHERE p.store_id IN ({}) AND p.available_amount > 0;
        #     """.format(", ".join([store['store_id'] for store in nearby_stores]))
        # )
        # total_products = dictfetchall(cursor)[0]['total_products']
        # TODO: sql syntax error
        stores_products = list()
        if len(nearby_stores):
            cursor.execute(
                """
                    SELECT p.product_id, p.seller_title, p.price_per_unit,
                    u.unit_type, p.price_per_unit, p.available_amount, p.store_id,
                    p.epoch_expire_time, p.picture, u.unit_type
                    FROM product p
                    LEFT JOIN unit_type u ON (p.unit_type_id = u.unit_type_id)
                    WHERE p.store_id IN ({}) AND p.available_amount > 0
                    ORDER BY p.product_id
                    LIMIT {} OFFSET %s
                """.format(", ".join([str(store['store_id']) for store in nearby_stores]), group_size), [(0 if group_number in [0, 1] else (group_number - 1) * group_size)]
            )
            stores_products = dictfetchall(cursor)
    nearby_products_list = list()
    for product in stores_products:
        for store in nearby_stores:
            if store['store_id'] == product['store_id']:
                product_distance = store['distance']
                break
        nearby_products_list.append(
            {
                "product_id": product['product_id'],
                "picture_id": encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                "title": product['seller_title'],
                "price_per_unit": product["price_per_unit"],
                "unit": product['unit_type'],
                "distance": product_distance,
                "expire_time": product['epoch_expire_time']
            }
        )
    if len(stores_products):
        return Response(
            {
                "group_number": group_number,
                "products_per_group": group_size,
                "products": nearby_products_list

            }, status=200
        )
    else:
        return Response(
            empty_product_list, status=200
        )


@api_view(['GET'])
def get_picture(request):
    try:
        picture_id = request.GET.get('picture_id')
        # print('this is the picture id ', picture_id)
        decoded_picture_id = decrypt(picture_id, key)
        # print(decoded_picture_id)
        folder = decoded_picture_id.split('_')[0]
        file_name = decoded_picture_id.split('_')[1]
    except Exception as e:
        print(e)
        return Response(
            {
                'server_message': 'فیلدها را به درستی پر نکرده‌اید'
            }, status=400
        )
    file_path = os.path.join(settings.MEDIA_ROOT, folder, file_name)
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'))
        response['Cache-Control'] = 'public, max-age=86400'
        return response
    else:
        print('File Not found')
        return HttpResponseNotFound('File not found')


@api_view(['POST'])
def place_recommender(request):
    query = request.POST.get('query')
    try:
        location_data = requests.get(url=f'{map_complete_addr}/search', params={
                                     'q': query, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )

    return Response(location_data, status=200)


@api_view(['GET'])
def cart_items(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                    SELECT 
                        c.*,
                        pr.*,
                        u.*,
                        s.name AS store_name, s.store_id,
                        sl.*
                    FROM cart_item c
                    LEFT JOIN product pr ON (c.product_id = pr.product_id)
                    LEFT JOIN unit_type u ON (u.unit_type_id = pr.unit_type_id)
                    LEFT JOIN store s ON (s.store_id = pr.store_id)
                    LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                    WHERE c.buyer_id = %s
                    ORDER BY pr.product_id DESC
                """, [request.role_id]
        )
        cart_items_db_obj = dictfetchall(cursor)
        cart_items = list()

        for item in cart_items_db_obj:
            cart_items.append(
                {
                    'product_id': item['product_id'],
                    'title': item['seller_title'],
                    'cart_item_id': item['cart_item_id'],
                    'picture_id': encrypt('product_'+item['picture'], key) if item['picture'] else '',
                    'price_per_unit': item['price_per_unit'],
                    'cart_item_amount': item['amount'],
                    'available_amount': item['available_amount'],
                    'unit': item['unit_type'],
                    'expire_time_epoch': item['epoch_expire_time'],
                    'store': {
                        'id': item['store_id'],
                        'name': item['store_name'],
                        'latitude': float(item['location'].split('-')[0]),
                        'longitude': float(item['location'].split('-')[1]),
                    }
                }
            )
        return Response(
            {
                "products": cart_items
            }, status=200)


@api_view(['POST'])
def add_to_cart(request):
    try:
        product_id = int(request.POST.get('product_id'))
        amount = float(request.POST.get('amount'))
    except:
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT *
                    FROM product p
                    WHERE p.product_id = %s
                """, [product_id]
            )
            product_db_obj = dictfetchall(cursor)
            if not len(product_db_obj):
                return Response(
                    {
                        'server_message': 'کالا یافت نشد'
                    }, status=400
                )
            product = product_db_obj[0]
            if product['available_amount'] < amount:
                return Response(
                    {
                        'server_message': 'مقدار انتخابی بیشتر از موجودی کالا است'
                    }, status=400
                )

            cursor.execute(
                """
                    SELECT *
                    FROM person p
                    LEFT JOIN buyer b ON (b.person_id = p.person_id)
                    WHERE p.person_id = %s
                """, [request.person_id]
            )
            person = dictfetchall(cursor)[0]
            cursor.execute(
                """
                    SELECT *
                    FROM cart_item
                    WHERE buyer_id = %s and product_id = %s
                """, [person['buyer_id'], product_id]
            )
            res = dictfetchall(cursor)
            if len(res):
                old_amount = res[0]['amount']
            else:
                old_amount = 0

            cursor.execute(
                """
                    INSERT INTO cart_item (buyer_id, product_id, amount)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (buyer_id, product_id)
                    DO UPDATE SET
                        amount = CASE
                                    WHEN EXCLUDED.amount + cart_item.amount > %s THEN cart_item.amount
                                    ELSE EXCLUDED.amount + cart_item.amount
                                 END
                    RETURNING amount
                """, [person['buyer_id'], product['product_id'], amount, product['available_amount']]
            )
            new_amount = dictfetchall(cursor)[0]['amount']
            if old_amount == new_amount:
                print('more than 2', old_amount, new_amount)
                return Response({
                    'server_message': 'مقدار انتخاب شده بیشتر از مقدار موجودی کالا است',
                }, status=400)
            cursor.execute(
                """
                    SELECT 
                        c.*,
                        pr.*,
                        u.*,
                        s.name AS store_name, s.store_id,
                        sl.*
                    FROM cart_item c
                    LEFT JOIN product pr ON (c.product_id = pr.product_id)
                    LEFT JOIN unit_type u ON (u.unit_type_id = pr.unit_type_id)
                    LEFT JOIN store s ON (s.store_id = pr.store_id)
                    LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                    WHERE c.buyer_id = %s
                    ORDER BY pr.product_id DESC
                """, [request.role_id]
            )
            cart_items_db_obj = dictfetchall(cursor)
            cart_items = list()

            for item in cart_items_db_obj:
                cart_items.append(
                    {
                        'product_id': item['product_id'],
                        'title': item['seller_title'],
                        'cart_item_id': item['cart_item_id'],
                        'picture_id': encrypt('product_'+item['picture'], key) if item['picture'] else '',
                        'price_per_unit': item['price_per_unit'],
                        'cart_item_amount': item['amount'],
                        'available_amount': item['available_amount'],
                        'expire_time_epoch': item['epoch_expire_time'],
                        'unit': item['unit_type'],
                        'store': {
                            'id': item['store_id'],
                            'name': item['store_name'],
                            'latitude': float(item['location'].split('-')[0]),
                            'longitude': float(item['location'].split('-')[1]),
                        }
                    }
                )
            return Response(
                {
                    "products": cart_items
                }, status=200)


@api_view(['POST'])
def remove_from_cart(request):
    try:
        product_id = int(request.POST.get('product_id'))
        amount = float(request.POST.get('amount'))
    except:
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT *
                    FROM product p
                    WHERE p.product_id = %s
                """, [product_id]
            )
            product_db_obj = dictfetchall(cursor)
            if not len(product_db_obj):
                return Response(
                    {
                        'server_message': 'کالا یافت نشد'
                    }, status=400
                )

            cursor.execute(
                """
                    SELECT *
                    FROM person p
                    LEFT JOIN buyer b ON (b.person_id = p.person_id)
                    WHERE p.person_id = %s
                """, [request.person_id]
            )
            person = dictfetchall(cursor)[0]

            cursor.execute(
                """
                    UPDATE cart_item 
                    SET amount = amount - %s
                    WHERE buyer_id = %s AND product_id = %s;
                    DELETE FROM cart_item
                    WHERE amount <= 0
                    RETURNING amount
                """, [amount, person['buyer_id'], product_id]
            )
            cursor.execute(
                """
                    SELECT 
                        c.*,
                        pr.*,
                        u.*,
                        s.name AS store_name, s.store_id,
                        sl.*
                    FROM cart_item c
                    LEFT JOIN product pr ON (c.product_id = pr.product_id)
                    LEFT JOIN unit_type u ON (u.unit_type_id = pr.unit_type_id)
                    LEFT JOIN store s ON (s.store_id = pr.store_id)
                    LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                    WHERE c.buyer_id = %s
                    ORDER BY pr.product_id DESC
                """, [request.role_id]
            )
            cart_items_db_obj = dictfetchall(cursor)
            cart_items = list()

            for item in cart_items_db_obj:
                cart_items.append(
                    {
                        'product_id': item['product_id'],
                        'title': item['seller_title'],
                        'cart_item_id': item['cart_item_id'],
                        'picture_id': encrypt('product_'+item['picture'], key) if item['picture'] else '',
                        'price_per_unit': item['price_per_unit'],
                        'cart_item_amount': item['amount'],
                        'available_amount': item['available_amount'],
                        'unit': item['unit_type'],
                        'expire_time_epoch': item['epoch_expire_time'],
                        'store': {
                            'id': item['store_id'],
                            'name': item['store_name'],
                            'latitude': float(item['location'].split('-')[0]),
                            'longitude': float(item['location'].split('-')[1]),
                        }
                    }
                )
            return Response(
                {
                    "products": cart_items
                }, status=200)


@api_view(['POST'])
def finalize_cart(request):
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT 
                        c.*,
                        pr.*,
                        u.*,
                        s.name AS store_name, s.store_id,
                        sl.*
                    FROM cart_item c
                    LEFT JOIN product pr ON (c.product_id = pr.product_id)
                    LEFT JOIN unit_type u ON (u.unit_type_id = pr.unit_type_id)
                    LEFT JOIN store s ON (s.store_id = pr.store_id)
                    LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                    WHERE c.buyer_id = %s
                    ORDER BY pr.product_id DESC
                """, [request.role_id]
            )
            cart_items_db_obj = dictfetchall(cursor)
            cart_items = list()
            grouped_items = list()
            failure = False
            previous_store_id = int()
            temp_list = list()
            total_price = 0
            for index, item in enumerate(cart_items_db_obj):
                if index == 0:
                    previous_store_id = item['store_id']
                if item['amount'] > item['available_amount']:
                    failure = True
                current_item = {
                    'product_id': item['product_id'],
                    'title': item['seller_title'],
                    'cart_item_id': item['cart_item_id'],
                    'picture_id': encrypt('product_'+item['picture'], key) if item['picture'] else '',
                    'price_per_unit': item['price_per_unit'],
                    'cart_item_amount': item['amount'],
                    'available_amount': item['available_amount'],
                    'unit': item['unit_type'],
                    'store': {
                        'id': item['store_id'],
                        'name': item['store_name'],
                        'latitude': float(item['location'].split('-')[0]),
                        'longitude': float(item['location'].split('-')[1]),
                    }
                }
                cart_items.append(current_item)
                temp_list.append(current_item)
                if item['store_id'] != previous_store_id or index == len(cart_items_db_obj) - 1:
                    grouped_items.append(temp_list)
                    temp_list = list()
                    previous_store_id = item['store_id']
                total_price += item['price_per_unit'] * item['amount']

            cursor.execute(
                """
                    SELECT credit
                    FROM wallet
                    WHERE person_id = %s
                """, [request.person_id]
            )
            credit = dictfetchall(cursor)[0]['credit']

            if total_price > credit:
                return Response(
                    {
                        "server_message": "موجودی شما کافی نیست. حساب خود را شارژ کنید",
                        "products": cart_items
                    }, status=200
                )

            if failure:
                return Response(
                    {
                        "server_message": "تعداد کالاهای انتخابی بیشتر از تعداد کالاهای موجود است",
                        "products": cart_items
                    }, status=200
                )

            cursor.execute(
                """
                    UPDATE wallet
                    SET credit = credit - %s
                    WHERE person_id = %s
                """, [total_price, request.person_id]
            )

            for group in grouped_items:
                if not len(group):
                    continue
                cursor.execute(
                    """
                        INSERT INTO "order" (buyer_id, submission_time,
                        secret_phrase, order_status_id, store_id)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING order_id
                    """, [request.role_id, int(time.time()), str(uuid.uuid4()).split('-')[-1], 1, group[0]['store']['id']]
                )
                order_id = dictfetchall(cursor)[0]['order_id']
                for product in group:
                    cursor.execute(
                        """
                            INSERT INTO "order_item" (product_id,
                            price_per_unit, amount, order_id)
                            VALUES (%s, %s, %s, %s);
                            DELETE FROM cart_item
                            WHERE cart_item_id = %s;
                            UPDATE product
                            SET available_amount = available_amount - %s
                            WHERE product_id = %s;
                        """, [
                            product['product_id'],
                            product['price_per_unit'],
                            product['cart_item_amount'],
                            order_id, product['cart_item_id'],
                            product['cart_item_amount'],
                            product['product_id']
                        ]
                    )
            if cart_items_db_obj:
                return Response(
                    {
                        "server_message": "خرید با موفقیت انجام شد",
                        "products": []
                    }, status=200
                )
            else:
                return Response(
                    {
                        "server_message": "کالایی در سبد خرید وجود ندارد",
                    }, status=400
                )


@api_view(['GET'])
def orders_list(request):
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT 
                        o.*,
                        os.name as status,
                        s.name AS store_name
                    FROM "order" o
                    LEFT JOIN order_status os ON (os.order_status_id =
                    o.order_status_id)
                    LEFT JOIN store s ON (s.store_id = o.store_id)
                    WHERE o.buyer_id = %s
                    ORDER BY o.secret_phrase, o.submission_time DESC
                """, [request.role_id]
            )
            order_items_db_obj = dictfetchall(cursor)
            order_items = list()

            for item in order_items_db_obj:
                cursor.execute(
                    """
                        SELECT SUM(price_per_unit * amount) as sum
                        FROM order_item
                        WHERE order_id = %s
                        GROUP BY order_id
                    """, [item['order_id']]
                )
                order_items.append(
                    {
                        'order_id': item['order_id'],
                        'store_name': item['store_name'],
                        'secret_phrase': item['secret_phrase'] if item['order_status_id'] == 1 else "-1",
                        'total_purchase_price': dictfetchall(cursor)[0]['sum'],
                        'minutes_left': ((item['submission_time'] + 7200 - int(time.time())) // 60) if item['order_status_id'] == 1 else -1,
                        'order_date': epoch_to_jalali(item['submission_time']),
                        'status': item['status']
                    }
                )
            cursor.execute(
                """
                    SELECT name
                    FROM order_status
                """
            )
            possible_order_status = [x[0] for x in list(cursor.fetchall())]
            return Response(
                {
                    "possible_order_status": possible_order_status,
                    "orders": order_items
                }, status=200
            )


@api_view(['POST'])
def category_products(request):
    try:
        favorite_location_id = int(request.POST.get('favorite_location_id'))
        group_number = int(request.POST.get('group_number'))
        category_id = int(request.POST.get('category_id'))
    except:
        return Response(invalid_fields_response, status=400)
    if group_number < 1:
        return Response(invalid_fields_response, status=400)
    offset = 0 if group_number in [0, 1] else ((group_number - 1) * group_size)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                DELETE FROM category_products_cache
                WHERE %s - time > %s
            """, [int(time.time()), 3600]
        )
        cursor.execute(
            """
                SELECT * 
                FROM category
                WHERE category_id = %s
            """, [category_id]
        )
        try:
            category_db_obj = dictfetchall(cursor)[0]
        except:
            return Response(invalid_fields_response, status=400)
        cursor.execute(
            """
                SELECT * 
                FROM category_products_cache
                WHERE category_id = %s and favorite_location_id = %s
            """, [category_id, favorite_location_id]
        )

        cache_products = dictfetchall(cursor)
        re_calculate = False
        if group_number == 1:
            re_calculate = True
        else:
            if len(cache_products):
                cursor.execute(
                    f"""
                        SELECT * 
                        FROM category_products_cache cpc
                        left join product p on (cpc.product_id = p.product_id)
                        left join unit_type u on (p.unit_type_id =
                        u.unit_type_id)
                        WHERE p.category_id = %s and favorite_location_id = %s
                        ORDER BY distance
                        LIMIT {group_size} OFFSET %s
                    """, [category_id, favorite_location_id, offset]
                )
                res = dictfetchall(cursor)
                products_list = []
                for product in res:
                    products_list.append(
                        {
                            "product_id": product['product_id'],
                            "picture_id": encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                            "title": product['seller_title'],
                            "price_per_unit": product["price_per_unit"],
                            "unit": product['unit_type'],
                            "distance": product['distance'],
                            "expire_time": product['epoch_expire_time']
                        }
                    )
                return Response(
                    {
                        "group_number": group_number,
                        "products_per_group": group_size,
                        "category": {
                            'id': category_db_obj['category_id'],
                            'name': category_db_obj['name']
                        },
                        "products": products_list
                    }
                )
            else:
                re_calculate = True

        empty_product_list = {
            "group_number": group_number,
            "products_per_group": group_size,
            "category": {
                'id': category_db_obj['category_id'],
                'name': category_db_obj['name']
            },
            "products": list()
        }

        if re_calculate:
            cursor.execute(
                """
                    SELECT *
                    FROM buyer_favorite_location
                    WHERE buyer_favorite_location_id = %s AND buyer_id = %s
                """, [favorite_location_id, request.role_id]
            )
            try:
                res = dictfetchall(cursor)[0]
            except:
                return Response(invalid_fields_response, status=400)
            buyer_latitude = float(res['location'].split('-')[0])
            buyer_longitude = float(res['location'].split('-')[1])
            buyer_city = res['city']
            cursor.execute(
                """
                    SELECT p.product_id, p.seller_title, p.price_per_unit,
                    u.unit_type, p.price_per_unit, p.available_amount, p.store_id,
                    p.epoch_expire_time, p.picture, u.unit_type, sl.location
                    FROM product p
                    LEFT JOIN unit_type u ON (p.unit_type_id = u.unit_type_id)
                    LEFT JOIN store s ON (p.store_id = s.store_id)
                    LEFT JOIN store_location sl ON (s.store_id = sl.store_id)
                    WHERE p.available_amount > 0 AND
                    p.category_id = %s
                """, [category_id]
            )
            res = dictfetchall(cursor)
            products_list = list()
            if res:
                for product in res:
                    products_list.append(
                        {
                            "product_id": product['product_id'],
                            "picture_id": encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                            "title": product['seller_title'],
                            "price_per_unit": product["price_per_unit"],
                            "unit": product['unit_type'],
                            "distance": haversine(buyer_latitude, buyer_longitude, float(product['location'].split('-')[0]), float(product['location'].split('-')[1])),
                            "expire_time": product['epoch_expire_time']
                        }
                    )
                products_list = sorted(
                    products_list, key=lambda x: x['distance'])
                cursor.execute(
                    """
                            DELETE FROM category_products_cache
                            WHERE favorite_location_id = %s AND category_id = %s
                        """, [favorite_location_id, category_id]
                )
                for product in products_list:
                    cursor.execute(
                        """
                            INSERT INTO category_products_cache (time,
                            favorite_location_id, distance, product_id, category_id)
                            VALUES (%s, %s, %s, %s, %s)
                        """, [int(time.time()), favorite_location_id, product['distance'], product['product_id'], category_db_obj['category_id']]
                    )
                return Response(
                    {
                        "group_number": group_number,
                        "products_per_group": group_size,
                        "products": products_list[offset:offset+group_size]

                    }, status=200
                )
            else:
                return Response(
                    empty_product_list, status=200
                )


@api_view(['GET'])
def get_stores(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM store s
                LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
            """
        )
        stores_db = dictfetchall(cursor)
        stores = list()
        for store in stores_db:
            stores.append(
                {
                    'id': store['store_id'],
                    'name': store['name'],
                    'latitude': store['location'].split('-')[0],
                    'longitude': store['location'].split('-')[1],
                    'picture_id': encrypt(f'store_{store["profile_picture"]}', key) if store["profile_picture"] else '',
                }
            )
        return Response(
            {
                'stores': stores
            }, status=200
        )


@api_view(['POST'])
def store_details(request):
    with connection.cursor() as cursor:
        try:
            store_id = request.POST.get('store_id')
            favorite_location_id = request.POST.get('favorite_location_id')
            print(favorite_location_id, request.role_id)
            cursor.execute(
                """
                    SELECT *
                    FROM buyer_favorite_location
                    WHERE buyer_favorite_location_id = %s AND buyer_id = %s
                """, [favorite_location_id, request.role_id]
            )
            favorite_location_db = dictfetchall(cursor)[0]
            print(favorite_location_db)
        except Exception as e:
            print(e)
            traceback.print_exc()
            return Response(
                invalid_fields_response, status=400
            )
        response = dict()
        buyer_latitude = float(favorite_location_db['location'].split('-')[0])
        buyer_longitude = float(favorite_location_db['location'].split('-')[1])
        cursor.execute(
            """
                SELECT
                    s.*,
                    pe.name as seller_name, pe.lastname as seller_lastname,
                    pe.phone as seller_phone,
                    sl.*
                FROM store s
                LEFT JOIN seller se ON (s.seller_id = se.seller_id)
                LEFT JOIN person pe on (pe.person_id = se.person_id)
                LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                WHERE s.store_id = %s
            """, [store_id]
        )
        store_db = dictfetchall(cursor)
        if not len(store_db):
            return Response(
                invalid_fields_response, status=400
            )
        store_db = store_db[0]
        response['seller'] = {
            'name': store_db['seller_name']+' '+store_db['seller_lastname'],
            'phone': store_db['seller_phone']
        }
        response['store'] = {
            'id': store_db['store_id'],
            'name': store_db['name'],
            'latitude': float(store_db['location'].split('-')[0]),
            'longitude': float(store_db['location'].split('-')[1]),
            'picture_id': encrypt(f'store_{store_db["profile_picture"]}', key) if store_db['profile_picture'] else ''
        }
        cursor.execute(
            """
                SELECT *
                FROM product p
                LEFT JOIN unit_type ut ON (ut.unit_type_id = p.unit_type_id)
                WHERE seller_id = %s and available_amount > 0 and
                epoch_expire_time > %s
                ORDER BY product_id
            """, [store_db['seller_id'], int(time.time())*1000]
        )
        products_db = dictfetchall(cursor)
        products = list()
        for product in products_db:
            products.append(
                {
                    'product_id': product['product_id'],
                    'picture_id': encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                    'title': product['seller_title'],
                    'unit': product['unit_type'],
                    'price_per_unit': product['price_per_unit'],
                    'expire_time': product['epoch_expire_time'],
                    'available_amount': product['available_amount']
                }
            )
        response['products'] = products
        cursor.execute(
            """
                SELECT *
                FROM working_time
                WHERE store_id = %s
            """, [store_id]
        )
        working_times_db = dictfetchall(cursor)[0]
        working_times = list()
        days = ['saturday', 'sunday', 'monday',
                'tuesday', 'wednesday', 'thursday', 'friday']
        for index, day in enumerate(days):
            working_times.append(
                {
                    'day_sequence_id': index + 1,
                    'is_holiday_binary': working_times_db[day+'_holiday_status'],
                    'times': {
                        'start': working_times_db[day+'_start_working_time'],
                        'end': working_times_db[day+'_end_working_time']
                    }
                }
            )
        response['working_times'] = working_times
        response['distance'] = haversine(
            buyer_latitude, buyer_longitude, response['store']['latitude'], response['store']['longitude'])
        return Response(
            response, status=200
        )


@api_view(['GET'])
def get_profile(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM person p
                LEFT JOIN wallet w ON (w.person_id = p.person_id)
                WHERE p.person_id = %s 
            """, [request.person_id]
        )
        person_information = dictfetchall(cursor)[0]
        return Response(
            {
                'first_name': person_information['name'],
                'last_name': person_information['lastname'],
                'phone': person_information['phone'],
                'email': person_information['email'],
                'wallet_credit': person_information['credit']
            }, status=200
        )


@api_view(['POST'])
def update_profile(request):
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    password = request.POST.get('password')
    email = request.POST.get('email')
    with connection.cursor() as cursor:
        if first_name:
            cursor.execute(
                """
                    UPDATE person
                    SET name = %s
                    WHERE person_id = %s
                """, [first_name, request.person_id]
            )
        if last_name:
            cursor.execute(
                """
                    UPDATE person
                    SET lastname = %s
                    WHERE person_id = %s
                """, [last_name, request.person_id]
            )
        if password:
            cursor.execute(
                """
                    UPDATE person
                    SET password_hash = %s
                    WHERE person_id = %s
                """, [hashlib.sha256(bytes(password, 'utf-8')).hexdigest(), request.person_id]
            )
        if email:
            cursor.execute(
                """
                    UPDATE person
                    SET email = %s
                    WHERE person_id = %s
                """, [email, request.person_id]
            )

        cursor.execute(
            """
                SELECT *
                FROM person p
                LEFT JOIN wallet w ON (w.person_id = p.person_id)
                WHERE p.person_id = %s 
            """, [request.person_id]
        )
        person_information = dictfetchall(cursor)[0]
        return Response(
            {
                'first_name': person_information['name'],
                'last_name': person_information['lastname'],
                'phone': person_information['phone'],
                'email': person_information['email'],
                'wallet_credit': person_information['credit']
            }, status=200
        )


@api_view(['POST'])
def increase_wallet_credit(request):
    try:
        amount = int(request.POST.get('amount'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                UPDATE wallet
                SET credit = credit + %s
                WHERE person_id = %s
                RETURNING credit
            """, [amount, request.person_id]
        )
        return Response(
            {
                'credit': dictfetchall(cursor)[0]['credit']
            }, status=200
        )


@api_view(['POST'])
def get_my_comments(request):
    with connection.cursor() as cursor:
        try:
            group_number = int(request.POST.get('group_number'))
        except Exception as e:
            return Response(
                invalid_fields_response, status=400
            )
        cursor.execute(
            f"""
                SELECT *
                FROM comment c
                LEFT JOIN product pr ON (pr.product_id = c.product_id)
                LEFT JOIN buyer b ON (b.buyer_id = c.buyer_id)
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE c.buyer_id = %s
                ORDER BY c.submission_time_epoch DESC
                LIMIT {group_size} OFFSET %s
            """, [request.role_id, (0 if group_number in [0, 1] else (group_number - 1) * group_size)]
        )
        comments_db = dictfetchall(cursor)
        comments = list()
        for comment in comments_db:
            comments.append(
                {
                    'comment_id': comment['comment_id'],
                    'writer': comment['name'],
                    'submission_time_epoch': comment['submission_time_epoch'],
                    'title': comment['title'],
                    'description': comment['description'],
                    'user_score': comment['score'],
                    'product': {
                        'id': comment['product_id'],
                        'title': comment['seller_title']
                    }
                }
            )
        return Response(
            {
                "group_number": group_number,
                "products_per_group": group_size,
                "comments": comments
            }, status=200
        )


@api_view(['POST'])
def get_product_comments(request):
    with connection.cursor() as cursor:
        try:
            product_id = int(request.POST.get('product_id'))
            group_number = int(request.POST.get('group_number'))
        except Exception as e:
            return Response(
                invalid_fields_response, status=400
            )
        cursor.execute(
            f"""
                SELECT *
                FROM comment c
                LEFT JOIN buyer b ON (b.buyer_id = c.buyer_id)
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE c.product_id = %s
                ORDER BY c.submission_time_epoch DESC
                LIMIT {group_size} OFFSET %s
            """, [product_id, (0 if group_number in [0, 1] else (group_number - 1) * group_size)]
        )
        comments_db = dictfetchall(cursor)
        comments = list()
        for comment in comments_db:
            comments.append(
                {
                    'comment_id': comment['comment_id'],
                    'writer': comment['name'],
                    'submission_time_epoch': comment['submission_time_epoch'],
                    'title': comment['title'],
                    'description': comment['description'],
                    'user_score': comment['score']
                }
            )
        return Response(
            {
                "group_number": group_number,
                "products_per_group": group_size,
                "comments": comments
            }, status=200
        )


@api_view(['POST'])
def add_comment(request):
    with connection.cursor() as cursor:
        try:
            product_id = int(request.POST.get('product_id'))
            title = str(request.POST.get('title'))
            description = str(request.POST.get('description'))
            user_score = float(request.POST.get('user_score'))
            if not 0 <= user_score <= 5:
                raise Exception
            cursor.execute(
                """
                    SELECT *
                    FROM product
                    WHERE product_id = %s
                """, [product_id]
            )
            if not len(dictfetchall(cursor)):
                raise Exception
        except Exception as e:
            print(e)
            return Response(
                invalid_fields_response, status=400
            )
        cursor.execute(
            """
                INSERT INTO comment (buyer_id, product_id, title, description,
                score, submission_time_epoch)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING comment_id
            """, [request.role_id, product_id, title, description, user_score, int(time.time())*1000]
        )
        cursor.execute(
            """
                SELECT *
                FROM comment c
                LEFT JOIN buyer b ON (b.buyer_id = c.buyer_id)
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE c.comment_id = %s
            """, [dictfetchall(cursor)[0]['comment_id']]
        )
        comment = dictfetchall(cursor)[0]
        return Response(
            {
                'server_message': 'دیدگاه شما با موفقیت ثبت شد',
                'comment_id': comment['comment_id'],
                'writer': comment['name'],
                'submission_time': comment['submission_time_epoch'],
                'title': comment['title'],
                'description': comment['description'],
                'user_score': comment['score']
            }, status=200
        )


@api_view(['POST'])
def edit_comment(request):
    with connection.cursor() as cursor:
        try:
            comment_id = int(request.POST.get('comment_id'))
            title = str(request.POST.get('title'))
            description = str(request.POST.get('description'))
            user_score = float(request.POST.get('user_score'))
            if not 0 <= user_score <= 5:
                raise Exception
            cursor.execute(
                """
                    SELECT *
                    FROM comment
                    WHERE comment_id = %s
                """, [comment_id]
            )
            if not len(dictfetchall(cursor)):
                raise Exception
        except Exception as e:
            print(e)
            return Response(
                invalid_fields_response, status=400
            )
        cursor.execute(
            """
                UPDATE comment
                SET title = %s, description = %s, score = %s
                WHERE buyer_id = %s AND comment_id = %s
                RETURNING comment_id
            """, [title, description, user_score, request.role_id, comment_id]
        )
        cursor.execute(
            """
                SELECT *
                FROM comment c
                LEFT JOIN product pr ON (pr.product_id = c.product_id)
                LEFT JOIN buyer b ON (b.buyer_id = c.buyer_id)
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE c.comment_id = %s
            """, [dictfetchall(cursor)[0]['comment_id']]
        )
        comment = dictfetchall(cursor)[0]
        return Response(
            {
                'server_message': 'دیدگاه شما با موفقیت ویرایش شد',
                'comment_id': comment['comment_id'],
                'writer': comment['name'],
                'submission_time': comment['submission_time_epoch'],
                'title': comment['title'],
                'description': comment['description'],
                'user_score': comment['score'],
                'product': {
                    'id': comment['product_id'],
                    'title': comment['seller_title']
                }
            }, status=200
        )


@api_view(['POST'])
def remove_comment(request):
    with connection.cursor() as cursor:
        try:
            comment_id = int(request.POST.get('comment_id'))
            cursor.execute(
                """
                    SELECT *
                    FROM comment
                    WHERE comment_id = %s AND buyer_id = %s
                """, [comment_id, request.role_id]
            )
            if not len(dictfetchall(cursor)):
                raise Exception
        except Exception as e:
            return Response(
                invalid_fields_response, status=400
            )
        cursor.execute(
            """
            WITH a as (
                DELETE FROM comment
                WHERE comment_id = %s AND buyer_id = %s
                RETURNING 1
            )
            SELECT count(*) FROM a;
            """, [comment_id, request.role_id]
        )
        count = dictfetchall(cursor)[0]['count']
        if count:
            return Response(
                {
                    'server_message': 'دیدگاه شما حذف شد'
                }, status=200
            )
        else:
            return Response(
                {
                    'server_message': 'عملیات درخواست شده موفقیت آمیز نبود'
                }, status=400
            )
# -------------- Vendor Section --------------


@api_view(['POST'])
def get_seller_products(request):
    try:
        group_number = int(request.POST.get('group_number'))
    except:
        return Response(invalid_fields_response, status=400)
    try:
        if request.user_role != 'seller':
            raise Exception
    except:
        return Response(
            {
                'server_message': 'شما فروشنده نیستید'
            }, status=400
        )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT *
                FROM seller s
                LEFT JOIN product p ON (p.seller_id = s.seller_id)
                LEFT JOIN unit_type u ON (u.unit_type_id = p.unit_type_id)
                WHERE s.seller_id = %s
                ORDER BY p.product_id DESC
                LIMIT {group_size} OFFSET %s         
                """, [request.role_id, 0 if group_number in [0, 1] else (group_number - 1) * group_size]
        )
        products_db = dictfetchall(cursor)
        products = list()
        for product in products_db:
            products.append(
                {
                    'product_id': product['product_id'],
                    'title': product['seller_title'],
                    'picture_id': encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                    'available_amount': product['available_amount'],
                    'unit': product['unit_type'],
                    'price_per_unit': product['price_per_unit']
                }
            )
        return Response(
            {
                "group_number": group_number,
                "products_per_group": group_size,
                'products': products
            }
        )


@api_view(['POST'])
def remove_product(request):
    try:
        product_id = int(request.POST.get('product_id'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                DELETE FROM product 
                WHERE product_id = %s AND seller_id = %s
                RETURNING product_id
            """, [product_id, request.role_id]
        )
        result = dictfetchall(cursor)
        if not len(result):
            return Response(
                {
                    'server_message': 'شما چنین محصولی ندارید'
                }, status=400
            )
        return Response(
            {
                'server_message': 'محصول انتخاب شده با موفق حذف شد'
            }, status=200
        )


@api_view(['GET'])
def get_product_unit_types(request):
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT *
                FROM unit_type
                """
        )
        unit_types_db = dictfetchall(cursor)
        reponse = list()
        for k in unit_types_db:
            reponse.append(
                {
                    'id': k['unit_type_id'],
                    'name': k['unit_type']
                }
            )
        return Response(
            reponse, status=200
        )


@api_view(['POST'])
def get_product_general_properties(request):
    try:
        category_id = int(request.POST.get('category_id'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT *
                FROM general_property
                where category_id = %s 
                """, [category_id]
        )
        general_properties_db = dictfetchall(cursor)
        reponse = list()
        for k in general_properties_db:
            reponse.append(
                {
                    'id': k['general_property_id'],
                    'name': k['name'],
                    'input_type': k['input_type']
                }
            )
        return Response(
            reponse, status=200
        )


@api_view(['POST'])
def get_product_exclusive_properties(request):
    try:
        sub_category_id = int(request.POST.get('sub_category_id'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT *
                FROM exclusive_property
                where sub_category_id = %s 
                """, [sub_category_id]
        )
        exclusive_properties_db = dictfetchall(cursor)
        reponse = list()
        for k in exclusive_properties_db:
            reponse.append(
                {
                    'id': k['exclusive_property_id'],
                    'name': k['name'],
                    'input_type': k['input_type']
                }
            )
        return Response(
            reponse, status=200
        )


@api_view(['POST'])
def add_product(request):
    try:
        title = str(request.POST.get('title'))
        description = str(request.POST.get('description'))
        expire_time_epoch = int(request.POST.get('expire_time_epoch'))
        price_per_unit = int(request.POST.get('price_per_unit'))
        unit_type_id = int(request.POST.get('unit_type_id'))
        available_amount = float(request.POST.get('available_amount'))
        category_id = int(request.POST.get('category_id'))
        sub_category_id = None
        if str(request.POST.get('sub_category_id')) not in ['-1', None, '']:
            sub_category_id = int(request.POST.get('sub_category_id'))
        general_properties = list()
        if str(request.POST.get('general_properties')):
            general_properties = json.loads(
                str(request.POST.get('general_properties')))
        exclusive_properties = list()
        if str(request.POST.get('exclusive_properties')):
            exclusive_properties = json.loads(
                str(request.POST.get('exclusive_properties')))
        picture = request.FILES.get('picture')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT *
                FROM store
                WHERE seller_id = %s
            """, [request.role_id]
        )
        store_id = dictfetchall(cursor)[0]['store_id']
        try:
            for property in general_properties:
                cursor.execute(
                    """
                        SELECT *
                        FROM general_property
                        WHERE category_id = %s AND general_property_id = %s
                    """, [category_id, property['id']]
                )
                db_general_property = dictfetchall(cursor)[0]
                if not len(db_general_property):
                    raise Exception
            for property in exclusive_properties:
                cursor.execute(
                    """
                        SELECT *
                        FROM exclusive_property ep
                        LEFT JOIN sub_category sc ON (sc.sub_category_id =
                        ep.sub_category_id)
                        WHERE sc.category_id = %s AND ep.sub_category_id = %s
                        AND ep.exclusive_property_id = %s
                    """, [category_id, sub_category_id, property['id']]
                )
                db_exclusive_property = dictfetchall(cursor)[0]
                if not len(db_exclusive_property):
                    raise Exception
        except Exception as e:
            print(e)
            traceback.print_exc()
            return Response(invalid_fields_response, status=400)
        cursor.execute(
            """
                INSERT INTO product (
                    seller_id,
                    seller_title,
                    seller_description,
                    epoch_expire_time,
                    price_per_unit,
                    unit_type_id,
                    store_id,
                    sub_category_id,
                    available_amount,
                    category_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING product_id
            """, [
                request.role_id,
                title,
                description,
                expire_time_epoch,
                price_per_unit,
                unit_type_id,
                store_id,
                sub_category_id if sub_category_id else None,
                available_amount,
                category_id
            ]
        )
        product_id = dictfetchall(cursor)[0]['product_id']
        for property in general_properties:
            cursor.execute(
                """
                    INSERT INTO product_property (product_id,
                    general_property_id, property_value)
                    VALUES (%s, %s, %s)
                """, [product_id, property['id'], str(property['value']).replace('date-', '')]
            )
        for property in exclusive_properties:
            cursor.execute(
                """
                    INSERT INTO product_property (product_id,
                    exclusive_property_id, property_value)
                    VALUES (%s, %s, %s)
                """, [product_id, property['id'], str(property['value']).replace('date-', '')]
            )
        if picture:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'product')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            fs = FileSystemStorage(location=upload_dir)
            file_name = str(product_id) + os.path.splitext(picture.name)[1]
            file_path = fs.path(file_name)
            if fs.exists(file_name):
                os.remove(file_path)
            file_name = fs.save(file_name, picture)
            cursor.execute(
                """
                    UPDATE product
                    SET picture = %s
                    WHERE product_id = %s
                """, [file_name, product_id]
            )
        else:
            return Response(
                {
                    'server_message': 'ثبت عکس محصول الزامی است'
                }, status=400
            )
    request._request.product_id = product_id
    return Response(
        product_details(request._request).data, status=200
    )


@api_view(['POST'])
def edit_product(request):
    try:
        product_id = int(request.POST.get('product_id'))
        title = str(request.POST.get('title'))
        description = str(request.POST.get('description'))
        expire_time_epoch = int(request.POST.get('expire_time_epoch'))
        price_per_unit = int(request.POST.get('price_per_unit'))
        unit_type_id = int(request.POST.get('unit_type_id'))
        available_amount = float(request.POST.get('available_amount'))
        category_id = int(request.POST.get('category_id'))
        sub_category_id = None
        general_properties = None
        exclusive_properties = None
        if str(request.POST.get('sub_category_id')) not in ['', '-1']:
            sub_category_id = int(request.POST.get('sub_category_id'))
        if str(request.POST.get('general_properties')):
            general_properties = json.loads(
                str(request.POST.get('general_properties')))
        if str(request.POST.get('exclusive_properties')):
            exclusive_properties = json.loads(
                str(request.POST.get('exclusive_properties')))
        picture = request.FILES.get('picture')
    except:
        traceback.print_exc()
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        # Check data integrity
        cursor.execute(
            """
                SELECT *
                FROM product
                WHERE product_id = %s AND seller_id = %s
            """, [product_id, request.role_id]
        )
        res = dictfetchall(cursor)
        if not len(res):
            return Response(
                {
                    "server_message": "شما چنین محصولی ندارید"
                }, status=400
            )
        res = res[0]
        if not category_id:
            category_id = res['category_id']
        try:
            if not sub_category_id:
                if exclusive_properties:
                    raise Exception
            else:
                cursor.execute(
                    """
                        SELECT *
                        FROM sub_category
                        WHERE category_id = %s AND sub_category_id = %s
                    """, [category_id, sub_category_id]
                )
                res1 = dictfetchall(cursor)
                if not len(res1):
                    raise Exception
        except:
            traceback.print_exc()
            return Response(
                invalid_fields_response, status=400
            )
        if not title:
            title = res['seller_title']
        if not description:
            description = res['seller_description']
        if not expire_time_epoch:
            expire_time_epoch = res['epoch_expire_time']
        if not price_per_unit:
            price_per_unit = res['price_per_unit']
        cursor.execute(
            """
                SELECT *
                FROM unit_type
                WHERE unit_type_id = %s
            """, [unit_type_id]
        )
        res1 = dictfetchall(cursor)
        if not unit_type_id:
            unit_type_id = res['unit_type_id']
        if not available_amount:
            available_amount = res['available_amount']
        try:
            if general_properties:
                for property in general_properties:
                    cursor.execute(
                        """
                            SELECT *
                            FROM general_property
                            WHERE category_id = %s AND general_property_id = %s
                        """, [category_id, property['id']]
                    )
                    db_general_property = dictfetchall(cursor)[0]
                    if not len(db_general_property):
                        raise Exception
            if exclusive_properties:
                for property in exclusive_properties:
                    cursor.execute(
                        """
                            SELECT *
                            FROM exclusive_property ep
                            LEFT JOIN sub_category sc ON (sc.sub_category_id =
                            ep.sub_category_id)
                            WHERE sc.category_id = %s AND ep.sub_category_id = %s
                            AND ep.exclusive_property_id = %s
                        """, [category_id, sub_category_id, property['id']]
                    )
                    db_exclusive_property = dictfetchall(cursor)[0]
                    if not len(db_exclusive_property):
                        raise Exception
        except Exception as e:
            print(e)
            return Response(invalid_fields_response, status=400)
        with transaction.atomic():
            try:
                cursor.execute(
                    """
                        UPDATE product
                        SET
                            seller_title = %s,
                            seller_description = %s,
                            epoch_expire_time = %s,
                            price_per_unit = %s,
                            unit_type_id = %s,
                            available_amount = %s,
                            category_id = %s,
                            sub_category_id = %s
                        WHERE product_id = %s;
                    """, [
                        title,
                        description,
                        expire_time_epoch,
                        price_per_unit,
                        unit_type_id,
                        available_amount,
                        category_id,
                        sub_category_id if sub_category_id else None,
                        product_id
                    ]
                )
                if general_properties:
                    for property in general_properties:
                        cursor.execute(
                            """
                                SELECT *
                                FROM product_property
                                WHERE product_id = %s AND general_property_id = %s
                            """, [product_id, property['id']]
                        )
                        if len(dictfetchall(cursor)):
                            cursor.execute(
                                """
                                    UPDATE product_property
                                    SET property_value = %s
                                    WHERE product_id = %s AND general_property_id = %s
                                """, [str(property['value']).replace('date-', ''), product_id, property['id']]
                            )
                        else:
                            cursor.execute(
                                """
                                    INSERT INTO product_property (product_id,
                                    general_property_id, property_value)
                                    VALUES (%s, %s, %s)
                                """, [product_id, property['id'], str(property['value']).replace('date-', '')]
                            )
                else:
                    cursor.execute(
                        """
                            DELETE FROM product_property
                            WHERE general_property_id IS NOT NULL AND product_id = %s
                        """, [product_id]
                    )
                if exclusive_properties:
                    for property in exclusive_properties:
                        cursor.execute(
                            """
                                select *
                                from product_property
                                where product_id = %s AND exclusive_property_id = %s
                            """, [product_id, property['id']]
                        )
                        if len(dictfetchall(cursor)):
                            cursor.execute(
                                """
                                    UPDATE product_property
                                    SET property_value = %s
                                    WHERE product_id = %s AND exclusive_property_id = %s
                                """, [str(property['value']).replace('date-', ''), product_id, property['id']]
                            )
                        else:
                            cursor.execute(
                                """
                                    INSERT INTO product_property (product_id,
                                    exclusive_property_id, property_value)
                                    VALUES (%s, %s, %s)
                                """, [product_id, property['id'], str(property['value']).replace('date-', '')]
                            )
                else:
                    cursor.execute(
                        """
                            DELETE FROM product_property
                            WHERE exclusive_property_id IS NOT NULL AND product_id = %s
                        """, [product_id]
                    )
                if picture:
                    upload_dir = os.path.join(settings.MEDIA_ROOT, 'product')
                    if not os.path.exists(upload_dir):
                        os.makedirs(upload_dir)
                    fs = FileSystemStorage(location=upload_dir)
                    file_name = str(res['product_id']) + \
                        os.path.splitext(picture.name)[1]
                    file_path = fs.path(file_name)
                    if fs.exists(file_name):
                        os.remove(file_path)
                    file_name = fs.save(file_name, picture)
                    cursor.execute(
                        """
                            UPDATE product
                            SET picture = %s
                            WHERE product_id = %s
                        """, [file_name, product_id]
                    )
            except Exception as e:
                traceback.print_exc()
                return Response(
                    invalid_fields_response, status=400
                )
    return Response(
        product_details(request._request).data, status=200
    )


@api_view(['GET'])
def get_seller_profile(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT
                    p.name as seller_name, p.lastname, p.phone,
                    w.*,
                    st.name as store_name, st.profile_picture as store_picture,
                    s.*,
                    stl.*
                FROM seller s
                LEFT JOIN wallet w ON (w.person_id = s.person_id)
                LEFT JOIN person p ON (p.person_id = s.person_id)
                LEFT JOIN store st ON (st.seller_id = s.seller_id)
                LEFT JOIN store_location stl ON (stl.store_id = st.store_id)
                WHERE s.seller_id = %s
            """, [request.role_id]
        )
        seller_information = dictfetchall(cursor)[0]
        cursor.execute(
            """
                SELECT *
                FROM working_time
                WHERE store_id = %s
            """, [seller_information['store_id']]
        )
        working_times_db = dictfetchall(cursor)[0]
        working_times = list()
        days = ['saturday', 'sunday', 'monday',
                'tuesday', 'wednesday', 'thursday', 'friday']
        for index, day in enumerate(days):
            working_times.append(
                {
                    'day_sequence_id': index + 1,
                    'is_holiday_binary': working_times_db[day+'_holiday_status'],
                    'times': {
                        'start': working_times_db[day+'_start_working_time'],
                        'end': working_times_db[day+'_end_working_time']
                    }
                }
            )

        return Response(
            {
                'store_name': seller_information['store_name'],
                'store_picture': encrypt(f'store_{seller_information["store_picture"]}', key),
                'store_location': {
                    'title': '، '.join([seller_information['neighborhood'], seller_information['city']]),
                    'latitude': float(seller_information['location'].split('-')[0]),
                    'longitude': float(seller_information['location'].split('-')[1])
                },
                'working_times': working_times,
                'seller_name': seller_information['seller_name'],
                'seller_lastname': seller_information['lastname'],
                'phone': seller_information['phone'],
                'wallet_credit': seller_information['credit']
            }, status=200
        )


@api_view(['POST'])
def edit_seller_profile(request):
    password = request.POST.get('password')
    seller_name = request.POST.get('seller_name')
    seller_lastname = request.POST.get('seller_lastname')
    store_picture = request.FILES.get('store_profile_picture')
    store_name = request.POST.get('store_name')
    store_latitude = request.POST.get('store_latitude')
    store_longitude = request.POST.get('store_longitude')
    store_picture = request.FILES.get('store_picture')
    working_times = request.POST.get('working_times')
    if working_times:
        invalid_fields = False
        try:
            working_times = json.loads(working_times)
        except:
            invalid_fields = True
        else:
            for day_details in working_times:
                if not ('day_sequence_id' in day_details and
                        str(day_details['day_sequence_id']).isnumeric() and
                        int(day_details['day_sequence_id']) in range(1, 8) and
                        'is_holiday_binary' in day_details and
                        str(day_details['is_holiday_binary']).isnumeric() and
                        int(day_details['is_holiday_binary']) in range(2) and
                        'times' in day_details and
                        'start' in day_details['times'] and 'end'
                        in day_details['times']):
                    invalid_fields = True
                    break
        if invalid_fields:
            return Response(invalid_fields_response, status=400)

    request._request.method = 'GET'
    current_data = get_seller_profile(request._request).data
    if not seller_name:
        seller_name = current_data['seller_name']
    if not seller_lastname:
        seller_lastname = current_data['seller_lastname']
    if not store_name:
        store_name = current_data['store_name']
    if not store_latitude:
        store_latitude = current_data['store_location']['latitude']
    if not store_longitude:
        store_longitude = current_data['store_location']['longitude']
    if not working_times:
        working_times = current_data['working_times']

    try:
        location_data = requests.get(url=f'{map_complete_addr}/reverse', params={
            'lat': store_latitude, 'lon': store_longitude, 'format': 'json'}, headers={'Accept-Language': 'fa-IR'}).json()
    except:
        return Response({
            'server_message': 'سرویس نقشه در دسترس نیست'
        }, status=503)
    else:
        if 'error' in location_data:
            return Response(
                {
                    'server_message': 'نقطه انتخابی جزو محدوده قابل انتخاب نیست'
                }, status=400
            )
        location_data = location_data['address']
    if ('city' not in location_data or 'suburb' not in location_data) and ('neighbourhood' not in location_data):
        return Response(
            {
                'server_message': 'مکان انتخابی دارای جزئیات کافی نمی‌باشد. مکان دیگری را انتخاب کنید'
            }, status=400
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
                UPDATE person
                SET name = %s, lastname = %s
                WHERE person_id = %s
            """, [seller_name, seller_lastname, request.person_id]
        )
        if password:
            cursor.execute(
                """
                    UPDATE person
                    SET password_hash = %s
                    WHERE person_id = %s
                """, [hashlib.sha256(bytes(password, 'utf-8')).hexdigest(), request.person_id]
            )
        cursor.execute(
            """
                SELECT *
                FROM store
                WHERE seller_id = %s
            """, [request.role_id]
        )
        store_id = dictfetchall(cursor)[0]['store_id']
        cursor.execute(
            """
                UPDATE store_location
                SET location = %s, city = %s, neighborhood = %s
                WHERE store_id = %s 
            """, [f'{store_latitude}-{store_longitude}', location_data.get('suburb') if location_data.get('suburb') else location_data.get('city'), location_data['neighbourhood'], store_id]
        )
        cursor.execute(
            """
                UPDATE store
                SET name = %s
                where store_id = %s
            """, [store_name, store_id]
        )
        for day_details in working_times:
            days = ['saturday', 'sunday', 'monday',
                    'tuesday', 'wednesday', 'thursday', 'friday']
            day = days[day_details['day_sequence_id'] - 1]
            cursor.execute(
                f"""
                    UPDATE working_time 
                    SET {day}_holiday_status = %s, 
                        {day}_start_working_time = %s,
                        {day}_end_working_time = %s
                    WHERE store_id = %s
                """, [day_details['is_holiday_binary'], day_details['times']['start'], day_details['times']['end'], store_id]
            )
        if store_picture:
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'store')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            fs = FileSystemStorage(location=upload_dir)
            file_name = str(store_id) + os.path.splitext(store_picture.name)[1]
            file_path = fs.path(file_name)
            if fs.exists(file_name):
                os.remove(file_path)
            file_name = fs.save(file_name, store_picture)
            cursor.execute(
                """
                    UPDATE store
                    SET profile_picture = %s
                    WHERE store_id = %s
                """, [file_name, store_id]
            )
        return Response(get_seller_profile(request._request).data, status=200)


@api_view(['POST'])
def get_seller_orders(request):
    try:
        in_progress_orders = int(request.POST.get('in_progress_orders'))
        if in_progress_orders not in [0, 1]:
            raise Exception
    except Exception as e:
        print(e)
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
                SELECT 
                    o.*,
                    os.name as order_status,
                    p.name as buyer_name, p.lastname as buyer_lastname,
                    p.phone as buyer_phone
                FROM "order" o
                LEFT JOIN order_status os ON (os.order_status_id = o.order_status_id)
                LEFT JOIN store s ON (s.store_id = o.store_id)
                LEFT JOIN seller se ON (se.seller_id = s.seller_id)
                LEFT JOIN buyer b ON (b.buyer_id = o.buyer_id)
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE o.order_status_id {f'= 1' if in_progress_orders else '!= 1'} and s.seller_id = %s
                ORDER BY o.submission_time
            """, [request.role_id]
        )
        result = dictfetchall(cursor)
        orders = list()
        for order in result:
            cursor.execute(
                """
                    SELECT SUM(price_per_unit * amount) as sum
                    FROM order_item
                    WHERE order_id = %s
                    GROUP BY order_id
                """, [order['order_id']]
            )
            orders.append(
                {
                    'order_id': order['order_id'],
                    'total_purchased_price': dictfetchall(cursor)[0]['sum'],
                    'minutes_left': (order['submission_time'] + 7200 - int(time.time())) // 60 if in_progress_orders else "-1",
                    'order_date': epoch_to_jalali(order['submission_time']),
                    'status': order['order_status'],
                    'customer': {
                        'name': order['buyer_name'] + ' ' + order['buyer_lastname'],
                        'phone': order['buyer_phone']
                    }
                }
            )
        cursor.execute(
            f"""
                SELECT name
                FROM order_status
                where order_status_id in ({'1' if in_progress_orders else '2, 3'})
            """
        )
        possible_order_status = [x[0] for x in list(cursor.fetchall())]
        return Response(
            {
                'possible_order_status': possible_order_status,
                'orders': orders
            }, status=200
        )

# -------------- Common Section --------------


@api_view(['POST'])
def product_details(request):
    try:
        if request.POST.get('product_id'):
            product_id = int(request.POST.get('product_id'))
        elif request.product_id:
            product_id = int(request.product_id)
        else:
            raise Exception
        if request.user_role == 'buyer':
            favorite_location_id = int(
                request.POST.get('favorite_location_id'))
    except Exception as e:
        print(e)
        return Response(invalid_fields_response, status=400)

    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT 
                    p.*,
                    u.*,
                    st.*,
                    stl.*,
                    c.name AS category_name,
                    sc.name AS sub_category_name
                FROM product p
                LEFT JOIN unit_type u ON (p.unit_type_id = u.unit_type_id)
                LEFT JOIN store st ON (p.store_id = st.store_id)
                LEFT JOIN store_location stl ON (st.store_id = stl.store_id)
                LEFT JOIN category c ON (c.category_id = p.category_id)
                LEFT JOIN sub_category sc ON (sc.sub_category_id =
                p.sub_category_id)
                WHERE p.product_id = %s
            """, [product_id]
        )
        product_db_obj = dictfetchall(cursor)
        if not len(product_db_obj):
            return Response(
                {
                    'server_message': 'چنین محصولی وجود ندارد'
                }, status=400
            )
        product_db_obj = product_db_obj[0]
        if request.user_role == 'buyer':
            cursor.execute(
                """
                    SELECT *
                    FROM buyer_favorite_location
                    WHERE buyer_favorite_location_id = %s
                """, [favorite_location_id]
            )
            favorite_location_db_obj = dictfetchall(cursor)
            if not len(favorite_location_db_obj):
                return Response(
                    {
                        'server_message': 'مکان منتخب انتخابی برای شما ثبت نشده است'
                    }, status=400
                )
            favorite_location_db_obj = favorite_location_db_obj[0]
            cursor.execute(
                """
                    SELECT *
                    FROM cart_item
                    WHERE product_id = %s
                """, [product_id]
            )
            cart_items_db_obj = dictfetchall(cursor)
            amount_in_cart = 0
            if len(cart_items_db_obj):
                amount_in_cart = cart_items_db_obj[0]['amount']
        cursor.execute(
            """
                SELECT *
                FROM comment c
                LEFT JOIN buyer b ON (b.buyer_id = c.buyer_id)
                LEFT JOIN person p ON (b.person_id = p.person_id)
                WHERE c.product_id = %s
                LIMIT 5
            """, [product_id]
        )
        comments_db_obj = dictfetchall(cursor)
        comments = list()
        if not len(comments_db_obj):
            product_score = -1
        else:
            product_scores_sum = float()
            for comment in comments_db_obj:
                comments.append(
                    {
                        'comment_id': comment['comment_id'],
                        'writer': comment['name'],
                        'title': comment['title'],
                        'description': comment['description'],
                        'submission_time_epoch': comment['submission_time_epoch'],
                        'user_score': comment['score'] if comment['score'] else -1
                    }
                )
                product_scores_sum += float(comment['score']
                                            ) if comment['score'] else 0
            product_score = round(
                (product_scores_sum) / len(comments_db_obj), 1) if product_scores_sum > 0 else -1
        cursor.execute(
            """
                SELECT g.name as general_property_name, e.name as
                exclusive_property_name, property_value, p.general_property_id, p.exclusive_property_id
                FROM product_property p
                LEFT JOIN general_property g ON (p.general_property_id = g.general_property_id)
                LEFT JOIN exclusive_property e ON (p.exclusive_property_id =
                e.exclusive_property_id)
                WHERE p.product_id = %s
            """, [product_id]
        )
        properties_db_obj = dictfetchall(cursor)
        general_properties = list()
        exclusive_properties = list()
        if len(properties_db_obj):
            for property in properties_db_obj:
                if property['property_value'].isnumeric():
                    for item in ['تاریخ', 'زمان']:
                        if (property['exclusive_property_name'] and item in property['exclusive_property_name'])\
                                or (property['general_property_name'] and item in property['general_property_name']):
                            value = f"date-{int(property['property_value'])}"
                            break
                    else:
                        value = float(property['property_value'])
                else:
                    value = property['property_value']
                if (property_id := property['general_property_id']) != None:
                    general_properties.append(
                        {
                            'id': property_id,
                            'title': property['exclusive_property_name'] if property['exclusive_property_name'] else property['general_property_name'],
                            'value': value
                        }
                    )
                if (property_id := property['exclusive_property_id']) != None:
                    exclusive_properties.append(
                        {
                            'id': property_id,
                            'title': property['exclusive_property_name'] if property['exclusive_property_name'] else property['general_property_name'],
                            'value': value
                        }
                    )
        response = {
            'product_id': product_id,
            'title': product_db_obj['seller_title'],
            'picture_id': encrypt('product_'+product_db_obj['picture'], key) if product_db_obj['picture'] else '',
            'description': product_db_obj['seller_description'],
            'price_per_unit': product_db_obj['price_per_unit'],
            'unit': {
                "id": product_db_obj['unit_type_id'],
                "name": product_db_obj['unit_type']
            },
            'product_score': product_score,
            'available_amount': product_db_obj['available_amount'],
            'expire_time_epoch': product_db_obj['epoch_expire_time'],
            'store': {
                'id': product_db_obj['store_id'],
                'name': product_db_obj['name'],
                'latitude': float(product_db_obj['location'].split('-')[0]),
                'longitude': float(product_db_obj['location'].split('-')[1]),
                'picture_id': encrypt(f'store_{product_db_obj["profile_picture"]}', key) if product_db_obj["profile_picture"] else '',
            },
            'comments': comments,
            'properties': {
                'general': general_properties,
                'exclusive': exclusive_properties
            }
        }
        if product_db_obj['category_id']:
            response['category'] = {
                'id': product_db_obj['category_id'],
                'name': product_db_obj['category_name']
            }
        if product_db_obj['sub_category_id']:
            response['sub_category'] = {
                'id': product_db_obj['sub_category_id'],
                'name': product_db_obj['sub_category_name']
            }
        else:
            response['sub_category'] = None
        if request.user_role == 'buyer':
            response.update(
                {
                    'distance': haversine(float(product_db_obj['location'].split('-')[0]), float(product_db_obj['location'].split('-')[1]), float(favorite_location_db_obj['location'].split('-')[0]), float(favorite_location_db_obj['location'].split('-')[1])),
                    'amount_in_cart': amount_in_cart if amount_in_cart else 0
                }
            )
        for response_key, response_value in response.items():
            if response_value == None and response_key != "sub_category":
                response[response_key] = ''
        return Response(response, status=200)


@api_view(['GET'])
def get_product_categories(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT category_id as id, name, picture as picture_id
                FROM category
            """
        )
        res = dictfetchall(cursor)
        new_list = list()
        for category in res:
            category['picture_id'] = encrypt(
                f'category_{category["picture_id"]}', key)
            new_list.append(category)
        return Response(
            new_list, status=200
        )


@api_view(['POST'])
def get_product_sub_categories(request):
    try:
        category_id = int(request.POST.get('category_id'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT sub_category_id AS id, name
                FROM sub_category
                where category_id = %s
            """, [category_id]
        )
        res = dictfetchall(cursor)
        return Response(
            res, status=200
        )


@api_view(['POST'])
def order_products(request):
    try:
        if request.POST.get('order_id'):
            order_id = int(request.POST.get('order_id'))
        elif request.order_id:
            order_id = int(request.order_id)
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                f"""
                    SELECT 
                        o.*,
                        os.name as order_status_name,
                        s.name as store_name, s.profile_picture AS store_picture,
                        se.*,
                        p.name as seller_name, p.lastname as seller_lastname, p.phone as seller_phone,
                        sl.*,
                        pb.name as buyer_name, pb.lastname as buyer_lastname,
                        pb.phone as buyer_phone
                    FROM "order" o
                    LEFT JOIN order_status os ON (os.order_status_id =
                    o.order_status_id)
                    LEFT JOIN store s ON (s.store_id = o.store_id)
                    LEFT JOIN store_location sl ON (sl.store_id = s.store_id)
                    LEFT JOIN seller se ON (se.seller_id = s.seller_id)
                    LEFT JOIN person p ON (p.person_id = se.person_id)
                    LEFT JOIN buyer b ON (b.buyer_id = o.buyer_id)
                    LEFT JOIN person pb on (pb.person_id = b.person_id)
                    WHERE order_id = %s and {f'o.buyer_id = %s' if
                    request.user_role == 'buyer' else f's.seller_id = %s'}
                """, [order_id, request.role_id]
            )
            try:
                order_details_db_obj = dictfetchall(cursor)[0]
            except:
                return Response(
                    {
                        'server_message': 'چنین سفارشی برای شما وجود ندارد'
                    }, status=400
                )
            cursor.execute(
                """
                    SELECT 
                        oi.amount as purchased_amount, oi.price_per_unit as purchased_price_per_unit,
                        p.*,
                        ut.*
                    FROM order_item oi
                    LEFT JOIN product p ON (p.product_id = oi.product_id)
                    LEFT JOIN unit_type ut ON (ut.unit_type_id = p.unit_type_id)
                    WHERE oi.order_id = %s
                """, [order_id]
            )
            products = dictfetchall(cursor)
            products_list = list()
            total_purchase_price = 0
            for product in products:
                product_to_append = {
                    'product_id': product['product_id'],
                    'title': product['seller_title'],
                    'picture_id': encrypt(f'product_{product["picture"]}', key) if product['picture'] else '',
                    'amount': product['purchased_amount'],
                    'unit': product['unit_type'],
                    'price_per_unit': product['purchased_price_per_unit']
                }
                products_list.append(product_to_append)
                total_purchase_price += product['purchased_price_per_unit'] * \
                    product['purchased_amount']
            response = {
                'order_id': order_details_db_obj['order_id'],
                'total_purchase_price': total_purchase_price,
                'minutes_left': ((order_details_db_obj['submission_time'] + 7200 - int(time.time())) // 60) if order_details_db_obj['order_status_id'] == 1 else -1,
                'order_date': epoch_to_jalali(order_details_db_obj['submission_time']),
                'status': order_details_db_obj['order_status_name'],
                'products': products_list
            }
            if request.user_role == 'buyer':
                response['seller'] = {
                    'id': order_details_db_obj['seller_id'],
                    'name': order_details_db_obj['seller_name']+' '+order_details_db_obj['seller_lastname'],
                    'phone': order_details_db_obj['seller_phone']
                }
                response['store'] = {
                    'id': order_details_db_obj['store_id'],
                    'name': order_details_db_obj['store_name'],
                    'latitude': order_details_db_obj['location'].split('-')[0],
                    'longitude': order_details_db_obj['location'].split('-')[1],
                    'picture_id': encrypt(f'store_{order_details_db_obj["store_picture"]}', key) if order_details_db_obj["store_picture"] else '',
                }
                response['secret_phrase'] = order_details_db_obj['secret_phrase'] if order_details_db_obj['order_status_id'] == 1 else "-1"
            if request.user_role == 'seller':
                response['buyer'] = {
                    'id': order_details_db_obj['buyer_id'],
                    'name': order_details_db_obj['buyer_name']+' '+order_details_db_obj['buyer_lastname'],
                    'phone': order_details_db_obj['buyer_phone']
                }
            return Response(response, status=200)


@api_view(['POST'])
def complete_order(request):
    try:
        secret_phrase = str(request.POST.get('secret_phrase'))
    except:
        return Response(invalid_fields_response, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT order_id, secret_phrase
                FROM "order" o
                LEFT JOIN store s ON (s.store_id = o.store_id)
                WHERE seller_id = %s AND secret_phrase = %s AND order_status_id = 1
            """, [request.role_id, secret_phrase]
        )
        order_secret = dictfetchall(cursor)
        if not len(order_secret):
            return Response(
                {
                    'server_message': 'چنین سفارش فعالی برای شما وجود ندارد'
                }, status=400
            )
        order_secret = order_secret[0]
        order_id = order_secret['order_id']
        request._request.order_id = order_id
        request._request.user_role = 'buyer'
        order_data = order_products(request._request).data
        cursor.execute(
            """
                UPDATE "order" 
                SET order_status_id = 2, secret_phrase = NULL
                WHERE order_id = %s;
                UPDATE wallet
                SET credit = credit + %s
                WHERE person_id = (
                    SELECT person_id
                    FROM seller
                    WHERE seller_id = %s
                );
            """, [order_id, order_data['total_purchase_price'], request.role_id]
        )
        return Response(
            {
                'server_message': f'سفارش با موفیت تکمیل و مبلغ {order_data["total_purchase_price"]} به حساب شما اضافه شد',
                'order_id': order_id
            }, status=200
        )


# -------------- Admin Panel --------------
@api_view(['POST'])
def admin_login(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    if username == 'test' and password == 'test':
        return Response(
            {
                "server_message": "ورود با موفقیت انجام شد",
                "jwt": jwt.encode({"user_role": 'admin'}, "uxrfcygvuh@b48651fdsa6s@#", algorithm="HS256")
            }, status=200)
    else:
        return Response(
            {
                'server_message': 'نام کاربری یا رمز عبور اشتباه است'
            }, status=400
        )


@api_view(['GET'])
def admin_orders_list(request):
    if request.user_role != 'admin':
        return Response(
            {
                'server_message': 'اجازه دسترسی به این قسمت را ندارید'
            }, status=403
        )
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT 
                        o.*,
                        os.name as status,
                        s.name AS store_name
                    FROM "order" o
                    LEFT JOIN order_status os ON (os.order_status_id =
                    o.order_status_id)
                    LEFT JOIN store s ON (s.store_id = o.store_id)
                    ORDER BY o.submission_time DESC
                """,
            )
            order_items_db_obj = dictfetchall(cursor)
            order_items = list()

            for item in order_items_db_obj:
                cursor.execute(
                    """
                        SELECT SUM(price_per_unit * amount) as sum
                        FROM order_item
                        WHERE order_id = %s
                        GROUP BY order_id
                    """, [item['order_id']]
                )
                order_items.append(
                    {
                        'order_id': item['order_id'],
                        'store_name': item['store_name'],
                        'total_purchase_price': dictfetchall(cursor)[0]['sum'],
                        'order_date': epoch_to_jalali(item['submission_time']),
                        'status': item['status']
                    }
                )
            return Response(
                {
                    "orders": order_items
                }, status=200
            )


@api_view(['GET'])
def admin_top_bar(request):
    if request.user_role != 'admin':
        return Response(
            {
                'server_message': 'اجازه دسترسی به این قسمت را ندارید'
            }, status=403
        )
    return Response(
        [
            {
                'id': "0",
                'title': "521",
                'prgress': "0.7",
                'increase': '-30%'
            },
            {
                'id': "1",
                'title': "1521",
                'prgress': "0.7",
                'increase': '-30%'
            },
            {
                'id': "0",
                'title': "2521",
                'prgress': "0.7",
                'increase': '-30%'
            },
            {
                'id': "0",
                'title': "3521",
                'prgress': "1.3",
                'increase': '+30%'
            },

        ], status=200
    )
    # with connection.cursor() as cursor:
    #     with transaction.atomic():
    #         cursor.execute(
    #             """
    #                 SELECT COUNT(*)
    #                 FROM "order"
    #                 WHERE submission_time >= EXTRACT(EPOCH FROM NOW() - INTERVAL '1 week');
    #             """
    #         )
    #         curret_week_orders = dictfetchall(cursor)[0]['count']
    #         cursor.execute(
    #             """
    #                 WITH week_range AS (
    #                     SELECT
    #                         DATE_TRUNC('week', NOW()) - INTERVAL '2 weeks' AS week_start,
    #                         DATE_TRUNC('week', NOW()) - INTERVAL '1 week' - INTERVAL '1 second' AS week_end
    #                 )
    #                 SELECT *
    #                 FROM "order"
    #                 JOIN week_range
    #                 ON "order".submission_time >= EXTRACT(EPOCH FROM week_range.week_start)
    #                 AND "order".submission_time <= EXTRACT(EPOCH FROM week_range.week_end);
    #             """,
    #         )
    #         previous_week_orders = dictfetchall(cursor)[0]['count']

    #         return Response(
    #             {
    #                 "orders": order_items
    #             }, status=200
    #         )
