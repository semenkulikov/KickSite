from typing import Union
from threading import Thread
from ServiceApp.Validators import validate_socks5_address, validate_twitch_token
from TwitchApp.IRCChat.base import (ConfigurationManager,
                                    SSLManager,
                                    AuthManager,
                                    ProxyManager,
                                    PingPongManager,
                                    ChannelManager,
                                    SendManager,
                                    SocketManager)


class IRCChat(ConfigurationManager,
              SSLManager,
              AuthManager,
              ProxyManager,
              PingPongManager,
              ChannelManager,
              SendManager,
              SocketManager):
    def __init__(self, login: str, token: str, proxy: str, use_ssl: bool = True):
        self._login: str = login
        validate_twitch_token(token)
        self._token: str = token
        validate_socks5_address(proxy)
        self._proxy: str = proxy
        self._use_ssl: bool = use_ssl

        self._ping_pong_thread: Union[None, Thread] = None
        self._channel: Union[None, str] = None
        self._socket: Union[None, str] = None


if __name__ == '__main__':
    from time import sleep


    def main():
        login = ''
        token = ''

        proxy = ''

        channel = ''
        message_1 = 'Hello there!'
        message_2 = 'How are you?'

        chat = IRCChat(login=login, token=token, proxy=proxy, use_ssl=True)

        print(f'connect: {chat.connect()}')

        chat.send(channel=channel, message=message_1)
        sleep(3)
        chat.send(channel=channel, message=message_2)

        print(f'disconnect: {chat.disconnect()}')


    main()
