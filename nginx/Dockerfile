# Use the official Nginx image as a parent image
FROM nginx:latest

# Copy the configuration file into the container
COPY nginx.conf /etc/nginx/nginx.conf

# Copy SSL certificates
COPY starkinc.shop/certificate.crt /etc/nginx/certs/starkinc/certificate.crt
COPY starkinc.shop/private_key.key /etc/nginx/certs/starkinc/private_key.key
COPY starkinc.shop/certificate_ca.crt /etc/nginx/certs/starkinc/certificate_ca.crt

# Expose ports
EXPOSE 80
EXPOSE 443

# Start Nginx when the container has provisioned
CMD ["nginx", "-g", "daemon off;"]
