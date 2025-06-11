from re import compile
from django.core.exceptions import ValidationError


def validate_socks5_address(value: str):
    """Validate the input string for pattern matching: socks5://«user»:«pass»@«host»:«port»"""
    if not value.startswith('socks5://'):
        raise ValidationError("The socks5 address must start with 'socks5://'")
    pattern = compile(r"socks5://.+:.+@.+:\d+")
    if pattern.fullmatch(value) is None:
        raise ValidationError("The socks5 address must match the pattern: socks5://«user»:«pass»@«host»:«port»")
