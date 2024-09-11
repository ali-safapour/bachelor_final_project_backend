Run the database, Swagger UI, and the web server with:
```
docker container rm market-yaab-postgres-container market-yaab-django-container -f && docker compose up --build -d
```

Then, after a few seconds, run:
```
docker exec -it market-yaab-postgres-container pg_restore -U postgres -c -C -dpostgres -Fc ./pgbackup.dump
```

The server will serve the requests at:
```URL
http://localhost:8000
```

The documentation would be available at:
```URL
http://localhost:7171
```