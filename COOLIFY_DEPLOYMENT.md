# Coolify Deployment Guide for Computer Control API

This guide will help you securely deploy the Computer Control API on Coolify with proper authentication and security measures.

## Security Overview

This repository has been configured with the following security measures for internet deployment:

- **API Key Authentication**: All API endpoints require a valid API key
- **VNC Password Protection**: noVNC access requires a password
- **Rate Limiting**: API endpoints have rate limits to prevent abuse
- **Security Headers**: HTTP security headers are automatically applied
- **Input Validation**: Basic input validation and size limits

## Prerequisites

1. **Coolify Instance**: You need a running Coolify installation
2. **Domain/Subdomain**: A domain or subdomain for your deployment
3. **SSH Access**: SSH access to your Coolify server (if needed)

## Deployment Steps

### 1. Prepare Your Environment Variables

Create strong, unique values for the required environment variables:

```bash
# Generate a secure API key (32-character hex string)
openssl rand -hex 32

# Create a strong VNC password (at least 8 characters)
# Example: Use a password manager to generate a secure password
```

### 2. Deploy on Coolify

#### Option A: Git Repository Deployment (Recommended)

1. **Add Your Repository to Coolify**:
   - Go to your Coolify dashboard
   - Click "New Resource" → "Application"
   - Choose "Public Repository" or "Private Repository"
   - Enter your repository URL
   - Select the branch to deploy

2. **Configure Build Settings**:
   - **Build Pack**: Select "Docker Compose"
   - **Docker Compose File**: Use the default `docker-compose.yml`
   - **Port**: The application will expose ports 5000 (API) and 6080 (noVNC)

3. **Set Environment Variables**:
   In the Coolify application settings, add the following environment variables:
   
   ```
   API_KEY=<your-generated-api-key>
   VNC_PASSWORD=<your-secure-vnc-password>
   ```
   
   Optional variables (use defaults if not specified):
   ```
   BASH_TIMEOUT=60
   SCREENSHOT_TIMEOUT=10
   SCREEN_GEOM=1280x800x24
   ```

4. **Configure Domains**:
   - Add your domain/subdomain for the API service
   - Coolify will automatically handle SSL certificates via Let's Encrypt

#### Option B: Docker Image Deployment

If you prefer to build and push the image manually:

1. Build and push your image to a registry
2. Create a new "Docker Image" resource in Coolify
3. Configure the same environment variables as above

### 3. Security Configuration in Coolify

#### Domain Configuration
- **API Access**: Configure your domain to point to port 5000
- **noVNC Access**: Configure a subdomain to point to port 6080
- **SSL**: Coolify automatically provides SSL certificates

Example domain setup:
- API: `https://api.yourdomain.com` → port 5000
- noVNC: `https://vnc.yourdomain.com` → port 6080

#### Firewall Considerations
Coolify's built-in proxy handles SSL termination and provides additional security layers.

### 4. Verify Deployment

1. **Health Check**: Visit `https://your-api-domain.com/health`
   - Should return: `{"status": "healthy", "message": "Computer Control API is running"}`

2. **API Authentication Test**:
   ```bash
   # This should fail (401 Unauthorized)
   curl https://your-api-domain.com/computer
   
   # This should work with your API key
   curl -H "X-API-Key: your-api-key" https://your-api-domain.com/computer
   ```

3. **noVNC Access**: Visit `https://your-vnc-domain.com`
   - Should prompt for VNC password
   - Enter the VNC_PASSWORD you configured

## Security Best Practices

### API Key Management
- **Keep your API key secret**: Never commit it to version control
- **Use strong keys**: Generate cryptographically secure random keys
- **Rotate regularly**: Change your API key periodically
- **Limit access**: Only share with trusted users/applications

### VNC Security
- **Strong passwords**: Use a complex VNC password
- **Access control**: Consider restricting VNC access to specific IP ranges if possible
- **Monitor access**: Check Coolify logs for unusual access patterns

### Monitoring and Maintenance
- **Monitor logs**: Check Coolify application logs regularly
- **Rate limiting**: The API has configurable rate limits (defaults: 3600/hour, 60/minute per IP). Adjust via env vars.
- **Health checks**: Coolify automatically monitors application health
- **Updates**: Keep your deployment updated with security patches

## API Usage with Authentication

All API endpoints (except `/health`) require authentication:

```bash
# Example: Take a screenshot
curl -X POST https://your-api-domain.com/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"action": "screenshot"}'

# Example: Execute a bash command
curl -X POST https://your-api-domain.com/bash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"command": "ls -la"}'
```

## Rate Limits

The API implements the following configurable rate limits per IP address (defaults shown):
- **Computer control endpoints**: 60/minute, 3600/hour (`COMPUTER_RATE_PER_MINUTE`, `COMPUTER_RATE_PER_HOUR`)
- **Bash execution**: 60/minute, 3600/hour (`BASH_RATE_PER_MINUTE`, `BASH_RATE_PER_HOUR`)
- **Text editor**: 60/minute, 3600/hour (`TEXT_RATE_PER_MINUTE`, `TEXT_RATE_PER_HOUR`)
- **Overall default**: 60/minute, 3600/hour (`GLOBAL_RATE_PER_MINUTE`, `GLOBAL_RATE_PER_HOUR`)

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check that you're providing the correct API key in the `X-API-Key` header

2. **VNC Connection Failed**: Verify the VNC_PASSWORD is correct

3. **Rate Limited**: Wait for the rate limit to reset or reduce request frequency

4. **Environment Variables**: Ensure all required environment variables are set in Coolify

### Logs
Check Coolify application logs for detailed error messages and security events.

## Support

For deployment issues:
- Check Coolify documentation: https://coolify.io/docs
- Review application logs in Coolify dashboard
- Verify environment variable configuration

For application issues:
- Check the API_USAGE.md file for detailed API documentation
- Review security headers and rate limiting configurations