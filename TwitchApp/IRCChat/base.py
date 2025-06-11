from abc import ABC
from typing import Callable, Union
from socket import socket as sock, timeout
from threading import Thread
from python_socks.sync import Proxy
from ssl import create_default_context
from ServiceApp.Validators import validate_socks5_address


class ConfigurationManager(ABC):
    __encoding: str = 'utf-8'
    __separator: str = '\n'
    __buffer: int = 1024
    __host: str = 'irc.chat.twitch.tv'
    __ssl_port: int = 6697
    __no_ssl_port: int = 6667
    __timeout: int = 4

    use_ssl: bool  # Defined in another class

    @property
    def encoding(self) -> str:
        return self.__encoding

    @property
    def separator(self) -> str:
        return self.__separator

    @property
    def buffer(self) -> int:
        return self.__buffer

    @property
    def host(self) -> str:
        return self.__host

    @property
    def port(self) -> int:
        return self.__ssl_port if self.use_ssl else self.__no_ssl_port

    @property
    def timeout(self) -> int:
        return self.__timeout


class SSLManager(ABC):
    _use_ssl: bool  # Redefine in "__init__"

    @property
    def use_ssl(self) -> bool:
        return self._use_ssl


class AuthManager(ABC):
    _login: str  # Redefine in "__init__"
    _token: str  # Redefine in "__init__" and validate

    @property
    def login(self) -> str:
        return self._login

    @property
    def token(self) -> str:
        return self._token


class ProxyManager(ABC):
    connect: Callable  # Defined in another class
    disconnect: Callable  # Defined in another class
    is_connected: bool  # Defined in another class

    _proxy: str  # Redefine in "__init__" and validate

    @property
    def proxy(self):
        return self._proxy

    def change_proxy(self, new_proxy: str) -> bool:
        validate_socks5_address(new_proxy)
        if self.is_connected:
            self.disconnect()
            self._proxy = new_proxy
            return self.connect()
        else:
            self._proxy = new_proxy
            return True


class PingPongManager(ABC):
    separator: str  # Defined in another class
    buffer: int  # Defined in another class
    encoding: str  # Defined in another class
    socket: Union[None, sock]  # Defined in another class

    _ping_pong_thread: Union[None, Thread]  # Redefine in "__init__"

    def ping_pong(self):
        total = str()
        while True:
            try:
                recv = self.socket.recv(self.buffer).decode(self.encoding, "replace")
            except timeout:
                if not self.is_ping_pong_running:
                    raise SystemExit()
                continue
            except OSError:
                raise SystemExit()
            except AttributeError:
                raise SystemExit()

            total += recv
            if self.separator not in total:
                continue

            for line in total.split(self.separator):
                if line.startswith('PING'):
                    self.socket.send(f"PONG :tmi.twitch.tv{self.separator}".encode(self.encoding))
                total = line

    @property
    def is_ping_pong_running(self) -> bool:
        if self._ping_pong_thread is None:
            return False
        return self._ping_pong_thread.is_alive()

    def start_ping_pong(self):
        if self.is_ping_pong_running:
            return

        if self._ping_pong_thread is None:
            self._ping_pong_thread = Thread(target=self.ping_pong, daemon=True)

        self._ping_pong_thread.start()

    def stop_ping_pong(self):
        if not self.is_ping_pong_running:
            return

        self._ping_pong_thread = None


class ChannelManager(ABC):
    separator: str  # Defined in another class
    encoding: str  # Defined in another class
    socket: Union[None, sock]  # Defined in another class

    _channel: Union[None, str]  # Redefine in "__init__"

    @property
    def channel(self) -> str:
        return self._channel
    
    @channel.setter
    def channel(self, value: str):
        if value == self._channel:
            return

        if self.is_joined:
            del self.channel

        self._channel = value
        self.socket.send(f'JOIN #{self._channel}{self.separator}'.encode(self.encoding))
    
    @channel.deleter
    def channel(self):
        if self.is_joined:
            self.socket.send(f'PART #{self._channel}{self.separator}'.encode(self.encoding))
        self._channel = None

    @property
    def is_joined(self) -> bool:
        return self._channel is not None


class SendManager(ABC):
    separator: str  # Defined in another class
    encoding: str  # Defined in another class
    socket: Union[None, sock]  # Defined in another class
    is_connected: bool  # Defined in another class
    channel: str  # Defined in another class

    def send(self, channel: str, message: str):
        assert self.is_connected, 'The "send" method can be called only after the "connect" method'

        self.channel = channel

        self.socket.send(f'PRIVMSG #{self.channel} :{message}{self.separator}'.encode(self.encoding))


class SocketManager(ABC):
    separator: str  # Defined in another class
    encoding: str  # Defined in another class
    host: str  # Defined in another class
    port: int  # Defined in another class
    proxy: str  # Defined in another class
    timeout: int  # Defined in another class
    use_ssl: bool  # Defined in another class
    login: str  # Defined in another class
    token: str  # Defined in another class
    channel: str  # Defined in another class
    start_ping_pong: Callable  # Defined in another class
    stop_ping_pong: Callable  # Defined in another class

    _socket: Union[None, sock]  # Redefine in "__init__"

    @property
    def socket(self) -> Union[None, sock]:
        return self._socket

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> bool:
        if self.is_connected:
            return True
        try:
            proxy = Proxy.from_url(self.proxy)
            self._socket = proxy.connect(dest_host=self.host, dest_port=self.port, timeout=self.timeout)
        except Exception:
            return False

        if self.use_ssl:
            self._socket = create_default_context().wrap_socket(sock=self._socket, server_hostname=self.host)

        self._socket.send(f'PASS {self.token}{self.separator}'.encode(self.encoding))
        self._socket.send(f'NICK {self.login}{self.separator}'.encode(self.encoding))

        self.start_ping_pong()

        print("I`m alive")
        return True

    def disconnect(self) -> bool:
        if not self.is_connected:
            return True

        del self.channel
        self._socket.send(f'QUIT{self.separator}'.encode(self.encoding))
        self.stop_ping_pong()
        self._socket.close()
        self._socket = None

        return True
