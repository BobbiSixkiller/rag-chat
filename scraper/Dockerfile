# Use a lightweight Python image
FROM python:3.9-slim

# Install cron and clean up
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the scraper script and cron configuration file
COPY scraper.py .
COPY crontab /etc/cron.d/scraper-cron

# Ensure the cron job file has the correct permissions and install it
RUN chmod 0644 /etc/cron.d/scraper-cron && crontab /etc/cron.d/scraper-cron

# Create a log file for cron output
RUN touch /var/log/cron.log

# Start cron in the foreground and output the logs
CMD cron && tail -f /var/log/cron.log
