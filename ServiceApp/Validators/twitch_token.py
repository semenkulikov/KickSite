from django.core.exceptions import ValidationError


def validate_twitch_token(value: str):
    """Validate the input string for pattern matching: oauth:«token»"""
    if not value.startswith('oauth:'):
        raise ValidationError("The twitch token must start with 'oauth:'")

    # Extract the actual token part
    token = value[6:]  # Remove 'oauth:' prefix
    
    if not token.strip():
        raise ValidationError("Twitch token cannot be empty after 'oauth:' prefix")
    
    # Basic format validation
    if len(token) < 10:
        raise ValidationError("Twitch token appears too short")
    
    if not token.replace('_', '').replace('-', '').isalnum():
        raise ValidationError("Twitch token contains invalid characters")
    
    # NOTE: Real token validation happens during IRC connection
    # If token is invalid, IRC connection will fail and user will see specific error