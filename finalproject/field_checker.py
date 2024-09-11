def error_generator(required_fields, request):
    if not request.method == 'POST':
        return ''
    
    errors_list = list()
    final_error = str()
    for item in required_fields:
        if type(item) == list:
            continue
        if item not in request.POST or not request.POST.get(item):
            errors_list.append(item)
    for item in errors_list:
        if type(item) == str:
            final_error += f' {item} and'
        elif type(item) == list:
            final_error += f'{" or ".join(item)} and'
    final_error = final_error.strip().strip("and").strip("or")
    if final_error:
        final_error += 'is required.'
    return final_error