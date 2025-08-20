# infra/application.Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy the entire src directory
COPY src/ /app/src

# Copy and install requirements for the application service
COPY src/application/requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.application.main:app", "--host", "0.0.0.0", "--port", "8000"]
