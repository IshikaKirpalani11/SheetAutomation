FROM python:3.10-slim

# Install Java for Tabula
RUN apt-get update && apt-get install -y default-jre && apt-get clean

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
