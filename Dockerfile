# Use the specified base image
FROM python:3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /usr/app

# Copy the project files into the Docker container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

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
