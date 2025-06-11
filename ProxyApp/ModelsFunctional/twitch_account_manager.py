from typing import Any, Callable


class ModelTwitchAccountManager:
    twitch_account: Any
    save: Callable

    @property
    def is_twitch_free(self) -> bool:
        return self.twitch_account is None

    @property
    def is_twitch_used(self) -> bool:
        return self.twitch_account is not None
