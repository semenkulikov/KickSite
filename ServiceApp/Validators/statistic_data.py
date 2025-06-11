from re import compile
from django.core.exceptions import ValidationError


def validate_statistic_data(value: str):
    """
    Check each line of the input string for pattern matching:
        hh:mm:ss.f DD.MM.YYYY|«twitch_channel»|«twitch_account»|a/m|«message»
        h - hours
        m - minutes
        s - seconds
        f - milliseconds

        D - days
        M - Months
        Y - years

        a - auto
        m - manual
    """
    for line in value.split('\n'):
        pattern = compile(r'\d+:\d+:\d+\.\d+ \d+\.\d+\.\d+\|.+\|.+\|[am]\|.+')
        if pattern.fullmatch(line) is None:
            raise ValidationError(f'The string "{line}" does not match the pattern '
                                  f'"hh:mm:ss.f DD.MM.YYYY|«twitch_channel»|«twitch_account»|a/m|«message»"')
