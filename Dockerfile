FROM python:3.12-slim

WORKDIR /app

COPY app/Report/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 5000

CMD ["sh", "-c", "flask --app run db upgrade && gunicorn -w 4 -b 0.0.0.0:5000 run:app"]