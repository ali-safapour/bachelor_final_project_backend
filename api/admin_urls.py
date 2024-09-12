import datetime
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
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import json
import requests
from .custom_modules.Haversin import haversine
from .custom_modules.EncodeDecode import encrypt, decrypt
from .custom_modules.EpochToJalali import epoch_to_jalali
from .custom_modules.FetchDBResultAsDict import dictfetchall

key = "xkjKL!442vrEzE97b@T%1IP*4Bl5FB74HevPSbR6qao4NHE="

@api_view(['POST'])
def admin_login(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    if username == 'amirnikzad' and password == 'marketyab':
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

def find_progress_and_increase(today, yesterday):
    if yesterday == 0:
        progress = '1'
        increase = f'+{today}'+'%'
    else:
        progress = (today - yesterday) // yesterday
        if progress >= 1:
            increase = str(progress * 100)+'%'
            progress = '1'
        elif 0 < progress < 1:
            increase = str(progress * 100)+'%'
            progress = str(progress)
        elif progress == 0:
            increase = '0%'
            progress = '0'
        else:
            increase = str(progress * 100)+'%'
            progress = '0'
            
    return progress, increase

@api_view(['GET'])
def admin_top_bar(request):
    # id: 0 => total sales in Tomans
    # id: 1 => total orders
    # id: 2 => new customers
    # id: 3 => new vendors
    now = datetime.datetime.now()
    start_of_today = datetime.datetime(now.year, now.month, now.day)
    start_of_today_epoch = int(time.mktime(start_of_today.timetuple()))
    start_of_previous_day_epoch = start_of_today_epoch-86400
    with connection.cursor() as cursor:
        response_list = list()
        cursor.execute(
            """
                SELECT SUM(price_per_unit)
                FROM order_item oi
                LEFT JOIN "order" o ON (o.order_id = oi.order_id)
                where submission_time > %s
            """, [start_of_today_epoch]
        )
        today_total_sales = dictfetchall(cursor)[0]['sum']
        today_total_sales = today_total_sales if today_total_sales else 0
        cursor.execute(
            """
                SELECT SUM(price_per_unit)
                FROM order_item oi
                LEFT JOIN "order" o ON (o.order_id = oi.order_id)
                WHERE %s < submission_time AND submission_time < %s
            """, [start_of_previous_day_epoch, start_of_today_epoch]
        )
        yesterday_total_sales = dictfetchall(cursor)[0]['sum']
        yesterday_total_sales = yesterday_total_sales if yesterday_total_sales else 0
        progress, increase = find_progress_and_increase(today_total_sales, yesterday_total_sales)
                
        response_list.append(
            {
                'id': "0",
                'title': str(today_total_sales) if today_total_sales else '0',
                'progress': progress,
                'increase': increase
            }
        )
        cursor.execute(
            """
                SELECT COUNT(*)
                FROM "order"
                WHERE submission_time > %s
            """, [start_of_today_epoch]
        )
        today_orders_count = dictfetchall(cursor)[0]['count']
        today_orders_count = today_orders_count if today_orders_count else 0
        cursor.execute(
            """
                SELECT COUNT(*)
                FROM "order"
                WHERE %s < submission_time AND submission_time < %s
            """, [start_of_previous_day_epoch, start_of_today_epoch]
        )
        yesterday_orders_count = dictfetchall(cursor)[0]['count']
        yesterday_orders_count = yesterday_orders_count if yesterday_orders_count else 0
        progress, increase = find_progress_and_increase(today_orders_count, yesterday_orders_count)
        response_list.append(
            {
                'id': "1",
                'title': str(today_orders_count) if today_orders_count else '0',
                'progress': progress,
                'increase': increase
            }
        )
        
        cursor.execute(
            """
                SELECT COUNT(*)
                FROM buyer b
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE registration_time_epoch > %s
            """, [start_of_today_epoch]
        )
        today_buyer_registrations = dictfetchall(cursor)[0]['count']
        today_buyer_registrations = today_buyer_registrations if today_buyer_registrations else 0

        cursor.execute(
            """
                SELECT COUNT(*)
                FROM buyer b
                LEFT JOIN person p ON (p.person_id = b.person_id)
                WHERE %s < registration_time_epoch AND registration_time_epoch < %s
            """, [start_of_previous_day_epoch, start_of_today_epoch]
        )
        yesterday_buyer_registrations = dictfetchall(cursor)[0]['count']
        yesterday_buyer_registrations = yesterday_buyer_registrations if yesterday_buyer_registrations else 0
        progress, increase = find_progress_and_increase(today_buyer_registrations, yesterday_buyer_registrations)  
        response_list.append(
            {
                'id': "2",
                'title': str(today_buyer_registrations) if today_buyer_registrations else '0',
                'progress': progress,
                'increase': increase
            }
        )
        
        
        cursor.execute(
            """
                SELECT COUNT(*)
                FROM seller s
                LEFT JOIN person p ON (p.person_id = s.person_id)
                WHERE registration_time_epoch > %s
            """, [start_of_today_epoch]
        )
        today_seller_registrations = dictfetchall(cursor)[0]['count']
        today_seller_registrations = today_seller_registrations if today_seller_registrations else 0
        cursor.execute(
            """
                SELECT COUNT(*)
                from seller s
                LEFT JOIN person p ON (p.person_id = s.person_id)
                WHERE %s < registration_time_epoch AND registration_time_epoch < %s
            """, [start_of_previous_day_epoch, start_of_today_epoch]
        )
        yesterday_seller_registrations = dictfetchall(cursor)[0]['count']
        yesterday_seller_registrations = yesterday_seller_registrations if yesterday_seller_registrations else 0
        progress, increase = find_progress_and_increase(today_seller_registrations, yesterday_seller_registrations)
        
        response_list.append(
            {
                'id': "3",
                'title': str(today_seller_registrations) if today_seller_registrations else '0',
                'progress': progress,
                'increase': increase
            }
        )
    return Response(
        response_list, status=200
    )

@api_view(['GET'])
def admin_superior_stores(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                select name, count(*), sum(price_per_unit * amount)
                from "order" o
                left join store s on (s.store_id = o.store_id)
                left join order_item oi on (oi.order_id = o.order_id)
                where order_status_id = 2
                group by o.store_id, name
                order by sum DESC
            """
        )
        superior_stores_db = dictfetchall(cursor)
        superior_stores_db = superior_stores_db[:5]
        superior_stores = list()
        for store in superior_stores_db:
            superior_stores.append(
                {
                    'shopName': store['name'],
                    'shopCount': store['count'],
                    'cost': store['sum']
                }
            )
        return Response(superior_stores, status=200)
        
@api_view(['GET'])
def admin_superior_customers(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                select p.name, p.lastname, count(*), sum(price_per_unit * amount)
                from order_item oi
                left join "order" o on (o.order_id = oi.order_id)
                left join buyer b on (b.buyer_id = o.buyer_id)
                left join person p on (p.person_id = b.person_id)
                where order_status_id = 2
                group by p.person_id
                order by sum DESC
            """
        )
        superior_customers_db = dictfetchall(cursor)
        return Response(superior_customers_db, status=200)
    
@api_view(['GET'])
def admin_best_selling_products(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
                select p.seller_title as name, count(oi.product_id),
                c.name as category, sum(oi.price_per_unit * amount)
                from order_item oi
                left join "order" o on (o.order_id = oi.order_id)
                left join product p on (oi.product_id = p.product_id)
                left join category c on (p.category_id = c.category_id)
                group by oi.product_id, p.seller_title, c.name
                order by count(oi.product_id) desc
            """
        )
        best_selling_products_db = dictfetchall(cursor)
        # for item in best_selling_products_db:
        #     item['name'] = item['name'][:15]+'...'
        #     item['sum'] /= 1000
        return Response(best_selling_products_db, status=200)    

@api_view(['GET'])
def admin_today_completed_orders(request):
    now = datetime.datetime.now()
    start_of_today = datetime.datetime(now.year, now.month, now.day)
    start_of_today_epoch = int(time.mktime(start_of_today.timetuple()))
    start_of_previous_day_epoch = start_of_today_epoch-86400
    with connection.cursor() as cursor:
        cursor.execute(
            """
                select count(*)
                from "order" o
                where order_status_id = 2 and submission_time > %s
            """, [start_of_today_epoch]
        )
        today_total_orders = dictfetchall(cursor)[0]['count']
        cursor.execute(
            """
                select count(*)
                from "order" o
                where order_status_id = 2 and submission_time > %s and
                submission_time < %s
            """, [start_of_today_epoch, start_of_previous_day_epoch]
        )
        previous_total_orders = dictfetchall(cursor)[0]['count']
        progress, _ = find_progress_and_increase(today_total_orders, previous_total_orders)
        
        return Response(
            {
                'deliveryNumber': today_total_orders,
                'progress': progress
            }, status=200)
   
   
@api_view(['GET'])
def customers_pie_chart(request):   
    with connection.cursor() as cursor:
        cursor.execute(
            """
                WITH order_success_rate AS (
                    SELECT 
                        total_orders.buyer_id, 
                        (COALESCE(successful_orders.success_count, 0) / total_orders.total_count::decimal) * 100 AS success_rate
                    FROM 
                        (SELECT buyer_id, COUNT(*) AS total_count
                        FROM "order"
                        GROUP BY buyer_id) AS total_orders
                    LEFT JOIN 
                        (SELECT buyer_id, COUNT(*) AS success_count
                        FROM "order"
                        WHERE order_status_id = 2
                        GROUP BY buyer_id) AS successful_orders
                    ON total_orders.buyer_id = successful_orders.buyer_id
                ),
                success_ranges AS (
                    SELECT 'bad' AS success_range
                    UNION ALL
                    SELECT 'normal' AS success_range
                    UNION ALL
                    SELECT 'good' AS success_range
                )
                SELECT 
                    sr.success_range,
                    COALESCE(COUNT(osr.buyer_id) * 100.0 / (SELECT COUNT(*) FROM order_success_rate), 0) AS percentage
                FROM success_ranges sr
                LEFT JOIN (
                    SELECT 
                        CASE 
                            WHEN success_rate BETWEEN 0 AND 30 THEN 'bad'
                            WHEN success_rate BETWEEN 30 AND 60 THEN 'normal'
                            ELSE 'good' 
                        END AS success_range,
                        buyer_id
                    FROM order_success_rate
                ) osr
                ON sr.success_range = osr.success_range
                GROUP BY sr.success_range;
            """
        )
        result = dictfetchall(cursor)
        print(result)
        response = list()
        for item in result:
            print(item)
            if item['success_range'] == 'normal':
                response.append(
                    {
                        'id': 'عادی',
                        'label': 'عادی',
                        'value': int(item['percentage'])
                    }
                )
            if item['success_range'] == 'good':
                response.append(
                   {
                        'id': 'وفادار',
                        'label': 'وفادار',
                        'value': int(item['percentage'])
                    } 
                )
            if item['success_range'] == 'bad':
                response.append(
                    {
                        'id': 'بدنام',
                        'label': 'بدنام',
                        'value': int(item['percentage'])
                    }
                )
        return Response(
            response, status=200
        )
        
        
@api_view(['GET'])
def test(request):
    return Response(
        [
  {
    "id": "حراج یلدا",
    "color": "#4caf50",
    "data": [
      { "x": "خشکبار", "y": 101 },
      { "x": "نان", "y": 75 },
      { "x": "چای وقهوه", "y": 36 },
      { "x": "میوه و سبزیجات", "y": 216 },
      { "x": "میوه پذیرایی", "y": 35 },
      { "x": "کنسروجات", "y": 236 },
      { "x": "لوازم بهداشتی", "y": 88 },
      { "x": "محصولات پروتئینی", "y": 232 },
      { "x": "برنج", "y": 281 },
      { "x": "روغن", "y": 1 },
      { "x": "سایر", "y": 14 }
    ]
  },
  {
    "id": "حراج تابستانه",
    "color": "#64b5f6",
    "data": [
      { "x": "خشکبار", "y": 212 },
      { "x": "نان", "y": 190 },
      { "x": "چای وقهوه", "y": 270 },
      { "x": "میوه و سبزیجات", "y": 9 },
      { "x": "میوه پذیرایی", "y": 75 },
      { "x": "کنسروجات", "y": 175 },
      { "x": "لوازم بهداشتی", "y": 33 },
      { "x": "محصولات پروتئینی", "y": 189 },
      { "x": "برنج", "y": 97 },
      { "x": "روغن", "y": 87 },
      { "x": "سایر", "y": 251 }
    ]
  },
  {
    "id": "نوروز",
    "color": "#d32f2f",
    "data": [
      { "x": "خشکبار", "y": 191 },
      { "x": "نان", "y": 136 },
      { "x": "چای وقهوه", "y": 91 },
      { "x": "میوه و سبزیجات", "y": 190 },
      { "x": "میوه پذیرایی", "y": 211 },
      { "x": "کنسروجات", "y": 152 },
      { "x": "لوازم بهداشتی", "y": 189 },
      { "x": "محصولات پروتئینی", "y": 152 },
      { "x": "برنج", "y": 8 },
      { "x": "روغن", "y": 197 },
      { "x": "سایر", "y": 170 }
    ]
  }
], status=200
    )