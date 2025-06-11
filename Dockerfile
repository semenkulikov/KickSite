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

# Expose the port the app runs on
EXPOSE 8000

VOLUME ["/usr/app/database"]

RUN python manage.py collectstatic --noinput  --clear

RUN ls -la ${STATIC_ROOT}

# Command to run the app
CMD ["daphne", "-p", "8000", "-b", "0.0.0.0", "Django.asgi:application"]
