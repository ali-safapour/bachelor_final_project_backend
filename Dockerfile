FROM python:3.12-alpine
WORKDIR /app
COPY . .
RUN python -m pip install -r requirements.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]