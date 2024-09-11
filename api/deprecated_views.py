@api_view(['POST'])
def sign_up(request):
    response = dict()
    response.update(
            {
                'status_code': "0",
                'server_message': 'فیلدها را به درستی پر نکرده‌اید'
            }
        )
    
    if not carrier._is_mobile(number_type(phonenumbers.parse(request.POST.get('phone'), "IR"))):
        return Response(response, status=400)
    
    user_role = request.POST.get('user_role')
    phone = request.POST.get('phone')
    password = request.POST.get('password')
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
                        'status_code': "1",
                        'server_message': 'شماره تلفن از قبل وجود دارد'
                    }, status=400)
            cursor.execute(
                """
                    INSERT INTO person (phone, password_hash)
                    VALUES ('{}', '{}')
                    RETURNING person_id
                """.format(phone, hashlib.sha256(bytes(password, 'utf-8')).hexdigest())
            )
            person_id = dictfetchall(cursor)[0]['person_id']
            
            cursor.execute(
                """
                    INSERT INTO {} (person_id)
                    VALUES ('{}');
                """.format(user_role, person_id)
            )
            
    return Response({
            "server_message": "ثبت نام با موفقیت انجام شد",
            "user_role": user_role,
            "jwt": jwt.encode({"user_role": user_role, "person_id": person_id}, "uxrfcygvuh@b48651fdsa6s@#", algorithm="HS256")
        }, status=200)



@api_view(['POST'])
def set_buyer_information(request):
    if request.user_role != 'buyer':
        return Response(
            {  
                "status_code": "0",
                "server_message": "فیلدها را به درستی پر نکرده‌اید"
            }, status=400
        )
    with connection.cursor() as cursor:
        with transaction.atomic():
            cursor.execute(
                """
                    SELECT *
                    FROM buyer 
                    WHERE person_id = %s
                """, [request.person_id]
            )
            buyer_id = dictfetchall(cursor)[0]['buyer_id']
            if request.POST.get('current_location') not in [None, '']:
                cursor.execute(
                    """
                        UPDATE buyer
                        SET current_location = %s
                        WHERE buyer_id = %s
                    """, [request.POST.get('current_location'), buyer_id]
                )
            if request.POST.get('credit') not in [None, '']:
                cursor.execute(
                    """
                        UPDATE buyer
                        SET credit = %s
                        WHERE buyer_id = %s
                    """, [request.POST.get('credit'), buyer_id]
                )
    return Response(

        {
            "server_message": "اطلاعات کاربر با موفقیت به‌روز رسانی شد"
        }, status=200

    )

@api_view(['POST'])
def set_person_information(request):
    with connection.cursor() as cursor:
        with transaction.atomic():
            if request.POST.get('name') not in [None, '']:
                cursor.execute(
                    """
                        UPDATE person
                        SET name = %s
                        WHERE person_id = %s
                    """, [request.POST.get('name'), request.person_id]
                )
            if request.POST.get('last_name') not in [None, '']:
                cursor.execute(
                    """
                        UPDATE person
                        SET lastname = %s
                        WHERE person_id = %s
                    """, [request.POST.get('last_name'), request.person_id]
                )
            if request.POST.get('email') not in [None, '']:
                cursor.execute(
                    """
                        UPDATE person
                        SET email = %s
                        WHERE person_id = %s
                    """, [request.POST.get('email'), request.person_id]
                )
            if request.FILES.get('profile_picture'):
                profile_picture = request.FILES['profile_picture']
                upload_dir = os.path.join(settings.MEDIA_ROOT, 'profile_pictures')
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                fs = FileSystemStorage(location=upload_dir)
                file_name = str(request.person_id) + os.path.splitext(profile_picture.name)[1]
                file_path = fs.path(file_name)
                if fs.exists(file_name):
                    os.remove(file_path)
                filename = fs.save(file_name, profile_picture)
                # file_url = fs.url(filename)
                cursor.execute(
                    """
                        UPDATE person
                        SET profile_picture = %s
                        WHERE person_id = %s
                    """, [file_name, request.person_id]
                )

    return Response(

        {
            "server_message": "اطلاعات کاربر با موفقیت به‌روز رسانی شد"
        }, status=200

    )
            


@api_view(['POST'])
def set_store(request):
    invalid_fields_error = {
        "status_code": "0",
        "server_message": "فیلدها را به درستی پر نکرده‌اید"
    }
    if request.user_role == 'buyer':
        return Response(invalid_fields_error, status=400)
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT seller_id
                FROM seller
                WHERE person_id = %s
            """, [request.person_id]
        )
        seller_id = dictfetchall(cursor)[0]['seller_id']
        cursor.execute(
            """
                SELECT store_id
                FROM store
                WHERE seller_id = %s;
            """, [seller_id]
        )
        store_id = dictfetchall(cursor)
        if not store_id:
            cursor.execute(
                """
                    INSERT INTO STORE (name, seller_id)
                    VALUES (%s, %s)
                    RETURNING store_id
                """, [request.POST.get('store_name'), seller_id]
            )
            store_id = dictfetchall(cursor)[0]['store_id']
        else:
            store_id = store_id[0]['store_id']
    if request.FILES.get('profile_picture'):
        profile_picture = request.FILES['profile_picture']
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'store_profile_pictures')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        fs = FileSystemStorage(location=upload_dir)
        file_name = str(store_id) + os.path.splitext(profile_picture.name)[1]
        file_path = fs.path(file_name)
        if fs.exists(file_name):
            os.remove(file_path)
        filename = fs.save(file_name, profile_picture)
        # file_url = fs.url(filename)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                    UPDATE store
                    SET profile_picture = %s
                    WHERE store_id = %s
                """, [file_name, store_id]
            )
        
    days = ['saturday', 'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    for day in days:
        if (day_data := request.POST.get(day)) not in [None, '']:
            day_data = json.loads(day_data)
            if 'is_holiday' in day_data and 'start_working_time' in day_data and 'end_working_time' in day_data:
                print(day_data, type(day_data))
                if not isinstance(day_data['is_holiday'], int) or int(day_data['is_holiday']) not in [0, 1]:
                    return Response(invalid_fields_error, status=400)
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                            insert into working_time ({day}_holiday_status,
                            {day}_start_working_time, {day}_end_working_time, store_id)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (store_id) DO UPDATE SET
                                {day}_holiday_status = EXCLUDED.{day}_holiday_status,
                                {day}_start_working_time = EXCLUDED.{day}_start_working_time,
                                {day}_end_working_time = EXCLUDED.{day}_end_working_time
                        """, [day_data['is_holiday'], day_data['start_working_time'], day_data['end_working_time'], store_id]
                    )
            else:
                return Response(invalid_fields_error, status=400)
        
    return Response(
        {
            "server_message": "اطلاعات فروشگاه با موفقیت به‌روز رسانی شد"
        }, status=200
    )
    

@api_view(['POST'])
def add_product_to_buyer_reserved_list(request):
    required_fields = ['jwt', 'product_id', 'reservation_expiration']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success'
            }
        )
        return Response(response, status=200)

@api_view(['POST'])
def get_buyer_information(request):
    required_fields = ['jwt']
    final_error = error_generator(required_fields, request)
    print(final_error)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'first_name': 'john',
                'last_name': 'ivy',
                'province': 'NY',
                'last_location': '41.40338, 2.17403'
            }
        )
        return Response(response, status=200)


@api_view(['POST'])
def seller_confirmation(request):
    required_fields = ['jwt', 'order_id']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success'
            }
        )
        return Response(response, status=200)


@api_view(['POST'])
def rate_to_store(request):
    required_fields = ['jwt', 'user_rate']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success'
            }
        )
        return Response(response, status=200)

@api_view(['POST'])
def cart(request):
    required_fields = ['jwt']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'cart': [
                    {
                        'product_name': 'apple',
                        'quantity': '3',
                        'remaining_time_in_seconds': '3600'
                    }
                ]
            }
        )
        return Response(response, status=200)


@api_view(['POST'])
def buyer_previous_orders(request):
    required_fields = ['jwt']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'orders': [
                    {
                        'order_id': '9725',
                        'date': '1403/05/1',
                        'total_spent': '125000'
                    }
                ]
            }
        )
        return Response(response, status=200)


@api_view(['POST'])
def store_registration(request):
    required_fields = ['jwt', 'store_name', 'store_location', 'store_logo_base64', 'store_description']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success'
            }
        )
        return Response(response, status=200)
    
@api_view(['POST'])
def buyer_order_details(request):
    required_fields = ['jwt', 'order_id']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'product_details': [
                    {
                        'product_name': 'apple',
                        'product_quantity': '3',
                        'total_price': '125000'
                    }
                ]
            }
        )
        return Response(response, status=200)


@api_view(['POST'])
def product_category_list(request):
    required_fields = ['jwt']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'categories': [
                    {
                        'category_id': 'میوه ها',
                        'category_name': '3'
                    },
                    {
                        'category_id': 'لبنیات',
                        'category_name': '4'
                    }
                ]
            }
        )
        return Response(response, status=200)
    
    
@api_view(['POST'])
def category_products(request):
    required_fields = ['jwt', 'category_id']
    final_error = error_generator(required_fields, request)
    response = dict()
    response.update(
        {
            'mock_data': True
        }
    )
    if final_error:
        response.update(
            {
                'server_message': final_error
            }
        )
        return Response(response, status=400)
    else:
        response.update(
            {
                'server_message': 'success',
                'products': [
                    {
                        'product_id': '122222',
                        'product_name': 'پنیر سنتی کاله',
                        'store_name': 'لبنیاتی پرستو',
                        'expiration_date': '84651456895' 
                    }
                ]
            }
        )
        return Response(response, status=200)
# @api_view(['GET'])
# def test_db(request):
#     with connection.cursor() as cursor:
#         cursor.execute("SELECT * FROM test_table")
#         row = cursor.fetchone()
#     return Response(
#         {
#             'res': row
#         }
#     )


# @api_view(['POST'])
# def sign_up(request):
#     required_fields = ['phone', 'password', 'user_role']
#     final_error = error_generator(required_fields, request)
#     response = dict()
#     response.update(
#         {
#             'mock_data': True
#         }
#     )
#     if final_error:
#         response.update(
#             {
#                 'server_message': final_error
#             }
#         )
#         return Response(response, status=400)
#     else:
#         response.update(
#             {
#                 'server_message': 'success'
#             }
#         )
#         return Response(response, status=200)
    