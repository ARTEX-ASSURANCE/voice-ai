# infra/execution.Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy the entire src directory
COPY src/ /app/src

# Copy and install requirements for the execution service
COPY src/execution/requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Run the execution worker
CMD ["python", "-m", "src.execution.worker"]
