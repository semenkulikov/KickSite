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
# This is done early to leverage Docker's layer caching
COPY package*.json ./
ENV NODE_ENV=production
RUN npm install && npm run prod

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
# This will be cached as long as requirements.txt does not change
RUN playwright install --with-deps chromium

# Copy the rest of the project files
COPY . .

# Create directory for logs, before any django commands are run
RUN mkdir -p /usr/app/logs

# Build frontend assets
RUN npm run prod
RUN python manage.py migrate --noinput
RUN python manage.py collectstatic --noinput

# Expose the port the app runs on
EXPOSE 8000

VOLUME ["/usr/app/database"]

# Run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "Django.asgi:application"]
