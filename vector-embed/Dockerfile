# Use an official lightweight Python image.
FROM python:3.9-slim

# Set environment variable to prevent buffering of Python output.
ENV PYTHONUNBUFFERED=1

# Install curl (needed for the health check)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set the working directory.
WORKDIR /app

# Copy the requirements file and install dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Expose the port the app runs on.
EXPOSE 8000

# Run the FastAPI service using uvicorn, with --reload for auto-reloading in development.
CMD ["uvicorn", "vector-service:app", "--host", "0.0.0.0", "--port", "8000"]
