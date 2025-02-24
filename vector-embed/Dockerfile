# Use an official lightweight Python image.
FROM python:3.9-slim

# Set the working directory.
WORKDIR /app

# Copy the requirements file and install dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Expose the port the app runs on.
EXPOSE 8000

# Run the FastAPI service using uvicorn.
CMD ["uvicorn", "embed_service:app", "--host", "0.0.0.0", "--port", "8000"]
