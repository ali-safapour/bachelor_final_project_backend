"""
WSGI config for finalproject project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import threading
import os
import time
from django.db import connection, transaction
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finalproject.settings")

application = get_wsgi_application()


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict.
    Assume the column names are unique.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def order_handler():
    while True:
        with connection.cursor() as cursor:
            with transaction.atomic():
                cursor.execute(
                    """
                        UPDATE "order" 
                        SET order_status_id = 3, secret_phrase = NULL
                        WHERE %s - submission_time > 7200 AND order_status_id = 1
                        RETURNING order_id, buyer_id, store_id
                    """, [int(time.time())]
                )
                res = dictfetchall(cursor)
                # We use buyer id to inform user that his/her order has been
                # canceled
                for item in res:
                    cursor.execute(
                        """
                            UPDATE wallet
                            SET credit = credit + (
                                SELECT SUM(price_per_unit * amount) as sum
                                FROM order_item
                                WHERE order_id = %s
                                GROUP BY order_id
                            )
                            WHERE person_id = (
                                SELECT person_id
                                FROM buyer
                                WHERE buyer_id = %s
                            )
                        """, [item['order_id'], item['buyer_id']]
                    )
        time.sleep(5)


threading.Thread(target=order_handler).start()
