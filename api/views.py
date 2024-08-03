from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
import copy, json
# Create your views here.


@api_view(['POST'])
def sign_up(request):
    required_fields = [['email', 'phone'], 'password']
    errors_dict = {}
    for item in required_fields:
        if type(item) == list:
            for j in item:
                if j in request.data:
                    break
            else:
                for j in item:
                    res = copy.deepcopy(item)
                    res.remove(j)
                    errors_dict[j] = f'Is required if you don\'t provide {" or ".join(res)}.'
        else:
            if item not in request.data:
                errors_dict[item] = f'Is required.'
    if errors_dict:
        response = {
            'server_message': 'failure'
        }
        response.update(errors_dict)
    else:
        response = {
            'server_message': 'success'
        }
    response.update(
        {
            'mock_data': True
        }
    )
    return Response(json.dumps(response))

@api_view(['POST'])
def login(request):
    required_fields = [['email', 'phone'], 'password']
    errors_dict = {}
    for item in required_fields:
        if type(item) == list:
            for j in item:
                if j in request.data:
                    break
            else:
                for j in item:
                    res = copy.deepcopy(item)
                    res.remove(j)
                    errors_dict[j] = f'Is required if you don\'t provide {" or ".join(res)}.'
        else:
            if item not in request.data:
                errors_dict[item] = f'Is required.'
    if errors_dict:
        response = {
            'server_message': 'failure',
        }
        response.update(errors_dict)
    else:
        response = {
            'server_message': 'success',
            'jwt': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        }
    response.update(
        {
            'mock_data': True
        }
    )
    return Response(json.dumps(response))


@api_view(['POST'])
def update_customer_information(request):
    required_fields = ['buyer_username', ['first_name', 'last_name', 'new_password', 'province', 'last_location']]
    errors_dict = {}
    for item in required_fields:
        if type(item) == list:
            for j in item:
                if j in request.data:
                    break
            else:
                for j in item:
                    res = copy.deepcopy(item)
                    res.remove(j)
                    errors_dict[j] = f'Is required if you don\'t provide {" or ".join(res)}.'
        else:
            if item not in request.data:
                errors_dict[item] = f'Is required.'
    if errors_dict:
        response = {
            'server_message': 'failure',
        }
        response.update(errors_dict)
    else:
        response = {
            'server_message': 'success'
        }
    response.update(
        {
            'mock_data': True
        }
    )
    return Response(json.dumps(response))

@api_view(['POST'])
def add_product_to_buyer_reserved_list(request):
    required_fields = ['buyer_username', 'product_id', 'reservation_duration_in_seconds']
    errors_dict = {}
    for item in required_fields:
        if type(item) == list:
            for j in item:
                if j in request.data:
                    break
            else:
                for j in item:
                    res = copy.deepcopy(item)
                    res.remove(j)
                    errors_dict[j] = f'Is required if you don\'t provide {" or ".join(res)}.'
        else:
            if item not in request.data:
                errors_dict[item] = f'Is required.'
    if errors_dict:
        response = {
            'server_message': 'failure',
        }
        response.update(errors_dict)
    else:
        response = {
            'server_message': 'success'
        }
    response.update(
        {
            'mock_data': True
        }
    )
    return Response(json.dumps(response))

@api_view(['GET'])
def get_buyer_information(request):
    required_fields = ['buyer_username']
    errors_dict = {}
    for item in required_fields:
        if type(item) == list:
            for j in item:
                if j in request.data:
                    break
            else:
                for j in item:
                    res = copy.deepcopy(item)
                    res.remove(j)
                    errors_dict[j] = f'Is required if you don\'t provide {" or ".join(res)}.'
        else:
            if item not in request.data:
                errors_dict[item] = f'Is required.'
    if errors_dict:
        response = {
            'server_message': 'user not found',
        }
        response.update(errors_dict)
    else:
        response = {
            'server_message': 'success',
            'first_name': 'john',
            'last_name': 'ivy',
            'province': 'NY',
            'last_location': '41.40338, 2.17403'
        }
    response.update(
        {
            'mock_data': True
        }
    )
    return Response(json.dumps(response))