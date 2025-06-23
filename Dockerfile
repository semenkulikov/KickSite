# Use the specified base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBUG=False

# Install Node.js and npm
RUN apt-get update && apt-get install -y npm

# Set the working directory in the container
WORKDIR /usr/app

# Copy package files and install npm dependencies
COPY package*.json ./
RUN npm install

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Build static files and then prune dev dependencies
RUN npm run prod && npm prune --production

# Create logs directory for django.log
RUN mkdir -p logs

# Collect static files
RUN python manage.py collectstatic --noinput

# Install Playwright browsers
# This will be cached as long as requirements.txt does not change
RUN playwright install --with-deps chromium

# Create directory for logs, before any django commands are run
RUN mkdir -p /usr/app/logs

# Run migrations
RUN python manage.py migrate --noinput

# Expose the port the app runs on
EXPOSE 8000

VOLUME ["/usr/app/database"]

# Run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "Django.asgi:application"]
