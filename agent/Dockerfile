FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY providers.py .
COPY roles.py .
COPY narrative/ ./narrative/
COPY reasoning/ ./reasoning/
COPY hooks/ ./hooks/
COPY memory/ ./memory/
COPY specialists/ ./specialists/

EXPOSE 8080

CMD ["python", "agent.py"]
