# Use the specified base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBUG=False

# Set the working directory in the container
WORKDIR /usr/app

# Copy only requirements to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
# This will be cached as long as requirements.txt does not change
RUN playwright install --with-deps chromium

# Copy the rest of the project files
COPY . .

# Create directory for logs
RUN mkdir -p /usr/app/logs

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Expose the port the app runs on
EXPOSE 8080

VOLUME ["/usr/app/database"]

RUN ls -la ${STATIC_ROOT}

# Run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8080", "Django.asgi:application"]
