# infra/execution.Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy the entire src directory
COPY src/ /app/src

# Install system dependencies required for building some python packages (e.g., mysqlclient)
RUN apt-get update && apt-get install -y pkg-config default-libmysqlclient-dev build-essential

# Copy and install requirements for the execution service
COPY src/execution/requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Run the execution worker
CMD ["python", "-m", "src.execution.worker"]
