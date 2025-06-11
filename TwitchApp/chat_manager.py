from typing import Union
from threading import Thread
from django.db.models.query import QuerySet
from ServiceApp import Singleton, StorageManager
from TwitchApp.models import TwitchAccount
from ProxyApp.models import Proxy
from TwitchApp.IRCChat import IRCChat
from django.contrib import messages
import logging
import time

logger = logging.getLogger(__name__)


class ChatManager(StorageManager, metaclass=Singleton):
    __connection_attempts: int = 5  # Increased attempts
    __retry_delay: float = 2.0  # Delay between retries

    def __connect_chat(self, twitch_account: TwitchAccount, chat: IRCChat, error_callback=None):
        """
        Enhanced connection method with better proxy rotation and error handling
        """
        current_attempt = 0
        last_proxy_id = None
        account_info = f"[{twitch_account.login}]"
        
        for attempt in range(self.__connection_attempts):
            current_attempt = attempt + 1
            logger.info(f"Connection attempt {current_attempt}/{self.__connection_attempts} for account {twitch_account.login}")
            
            try:
                # Try to connect with current proxy (with simple timeout)
                start_time = time.time()
                max_connection_time = 30  # 30 seconds max
                
                connection_result = chat.connect()
                connection_time = time.time() - start_time
                
                if connection_time > max_connection_time:
                    error_reason = f"Connection timeout after {connection_time:.1f} seconds"
                    logger.error(f"Timeout for account {twitch_account.login}: {error_reason}")
                    if error_callback:
                        error_callback(f"⏰ {account_info} {error_reason}")
                elif connection_result:
                    self.set_status(twitch_account.login, chat.is_connected)
                    logger.info(f"Successfully connected account {twitch_account.login} with proxy {twitch_account.proxy.url}")
                    if error_callback:
                        error_callback(f"✅ {account_info} Successfully connected")
                    return
                else:
                    # Connection failed - determine the reason
                    error_reason = self._diagnose_connection_failure(twitch_account, chat)
                    logger.warning(f"Connection failed for account {twitch_account.login}: {error_reason}")
                    
                    if error_callback:
                        error_callback(f"❌ {account_info} {error_reason}")
                    
            except Exception as e:
                error_reason = f"Connection error: {str(e)}"
                logger.error(f"Exception during connection for {twitch_account.login}: {error_reason}")
                if error_callback:
                    error_callback(f"❌ {account_info} {error_reason}")
            
            # Connection failed, handle proxy rotation
            if twitch_account.proxy:
                twitch_account.proxy.mark_as_bad()
                last_proxy_id = twitch_account.proxy.id
                logger.info(f"Marked proxy {twitch_account.proxy.url} as bad")
                
                if error_callback:
                    error_callback(f"🔄 {account_info} Switching from bad proxy {twitch_account.proxy.url}")
            
            # Get next available proxy (excluding the bad one)
            available_proxies = Proxy.objects.filter(
                status=True, 
                twitch_account=None
            ).exclude(id=last_proxy_id if last_proxy_id else 0)
            
            if not available_proxies.exists():
                # No more available proxies
                self.set_status(twitch_account.login, None)
                error_msg = f"🚫 {account_info} No available proxies left (tried {current_attempt} proxies)"
                logger.error(error_msg)
                if error_callback:
                    error_callback(error_msg)
                raise ConnectionError(error_msg)
            
            # Update account with new proxy
            new_proxy = available_proxies.first()
            twitch_account.proxy = new_proxy
            twitch_account.save()
            
            # Update chat with new proxy
            chat.change_proxy(new_proxy.url)
            logger.info(f"Switched account {twitch_account.login} to new proxy {new_proxy.url}")
            
            if error_callback:
                error_callback(f"🔄 {account_info} Trying proxy {new_proxy.url} (attempt {current_attempt + 1})")
            
            # Small delay before retry to avoid overwhelming the server
            if attempt < self.__connection_attempts - 1:
                time.sleep(self.__retry_delay)
        
        # All attempts failed
        self.set_status(twitch_account.login, None)
        error_msg = f"💥 {account_info} Connection failed after {self.__connection_attempts} attempts with different proxies"
        logger.error(error_msg)
        if error_callback:
            error_callback(error_msg)
        raise ConnectionError(error_msg)

    def _diagnose_connection_failure(self, twitch_account: TwitchAccount, chat: IRCChat) -> str:
        """
        Diagnose the specific reason for connection failure
        """
        account_info = f"[{twitch_account.login}]"
        
        # Check if proxy is accessible
        if not twitch_account.proxy:
            return f"No proxy assigned"
        
        if not twitch_account.proxy.status:
            return f"Proxy {twitch_account.proxy.url} is marked as inactive"
        
        # Check token format
        if not twitch_account.token or not twitch_account.token.startswith('oauth:'):
            return f"Invalid token format (must start with 'oauth:')"
        
        # Check IRC connection specifics
        if hasattr(chat, 'last_error'):
            return f"IRC error: {chat.last_error}"
        
        # Most likely causes for IRC connection failure:
        # 1. Invalid token (most common)
        # 2. Proxy issues
        # 3. Network connectivity
        
        # Since we passed basic format validation, likely causes:
        if "401" in str(getattr(chat, 'last_response', '')).lower() or "authentication" in str(getattr(chat, 'last_response', '')).lower():
            return f"Token authentication failed - token may be expired or invalid"
        
        if "timeout" in str(getattr(chat, 'last_error', '')).lower():
            return f"Connection timeout - proxy or network issue"
        
        # Default diagnostic
        return f"IRC connection failed - likely invalid token or proxy issue with {twitch_account.proxy.url}"

    def __open_new_chat(self, chatter_name: str, twitch_account: TwitchAccount, use_ssl: bool, forced: bool = False, error_callback=None):
        """
        Enhanced method to open new chat with better error handling
        """
        try:
            # Ensure account has a valid proxy before attempting connection
            if not twitch_account.proxy or not twitch_account.proxy.status:
                logger.info(f"Account {twitch_account.login} needs a new proxy")
                twitch_account.update_self_proxy()
                
                if not twitch_account.proxy:
                    error_msg = f"❌ [{twitch_account.login}] No available proxies for account"
                    logger.error(error_msg)
                    if error_callback:
                        error_callback(error_msg)
                    return
            
            chat = IRCChat(twitch_account.login, twitch_account.token, twitch_account.proxy.url, use_ssl)
            self.add(twitch_account.login, chatter_name, chat, forced)
            self.__connect_chat(twitch_account, chat, error_callback=error_callback)
            
        except Exception as e:
            error_msg = f"❌ [{twitch_account.login}] Connection error: {str(e)}"
            logger.error(error_msg)
            if error_callback:
                error_callback(error_msg)

    @staticmethod
    def __send_message(chat: IRCChat, channel: str, message: str):
        chat.send(channel, message)

    @staticmethod
    def __close_chat(chat: IRCChat):
        chat.disconnect()

    def connect(self, chatter_name: str, twitch_accounts: QuerySet[TwitchAccount], use_ssl: bool = True, error_callback=None):
        """
        Enhanced connect method with improved error handling and logging
        """
        total_accounts = twitch_accounts.count()
        logger.info(f"Connecting {total_accounts} Twitch accounts for user {chatter_name}")
        
        if error_callback:
            error_callback(f"🔄 Starting connection for {total_accounts} accounts...")
        
        connection_results = {
            'success': 0,
            'failed': 0,
            'total': total_accounts
        }
        
        for twitch_account in twitch_accounts:
            try:
                account_info = f"[{twitch_account.login}]"
                
                # Pre-connection validation
                if not twitch_account.token:
                    error_msg = f"❌ {account_info} No token configured"
                    logger.error(error_msg)
                    if error_callback:
                        error_callback(error_msg)
                    connection_results['failed'] += 1
                    continue
                
                if not twitch_account.proxy:
                    logger.info(f"Account {twitch_account.login} needs a proxy assignment")
                    twitch_account.update_self_proxy()
                    if not twitch_account.proxy:
                        error_msg = f"❌ {account_info} No available proxies"
                        logger.error(error_msg)
                        if error_callback:
                            error_callback(error_msg)
                        connection_results['failed'] += 1
                        continue
                
                if self.contains(twitch_account.login):
                    if self.get_status(twitch_account.login) is None:
                        logger.info(f"Reconnecting failed account {twitch_account.login}")
                        if error_callback:
                            error_callback(f"🔄 {account_info} Reconnecting...")
                        
                        def connection_callback(msg):
                            if error_callback:
                                error_callback(msg)
                            # Update counters based on result
                            if "✅" in msg:
                                connection_results['success'] += 1
                            elif "❌" in msg or "🚫" in msg:
                                connection_results['failed'] += 1
                        
                        thread = Thread(
                            target=self.__open_new_chat, 
                            args=(chatter_name, twitch_account, use_ssl, True), 
                            kwargs={'error_callback': connection_callback}
                        )
                    else:
                        logger.info(f"Adding owner {chatter_name} to existing connection {twitch_account.login}")
                        self.add_owner(twitch_account.login, chatter_name)
                        if error_callback:
                            error_callback(f"✅ {account_info} Already connected")
                        connection_results['success'] += 1
                        continue
                else:
                    logger.info(f"Creating new connection for account {twitch_account.login}")
                    if error_callback:
                        error_callback(f"🔄 {account_info} Connecting...")
                    
                    def connection_callback(msg):
                        if error_callback:
                            error_callback(msg)
                        # Update counters based on result
                        if "✅" in msg:
                            connection_results['success'] += 1
                        elif "❌" in msg or "🚫" in msg:
                            connection_results['failed'] += 1
                    
                    thread = Thread(
                        target=self.__open_new_chat, 
                        args=(chatter_name, twitch_account, use_ssl), 
                        kwargs={'error_callback': connection_callback}
                    )
                    
                thread.start()
                
                # Small delay between connection attempts to prevent overwhelming
                time.sleep(0.5)
                
            except Exception as e:
                error_msg = f"❌ {account_info} Error: {str(e)}"
                logger.error(error_msg)
                if error_callback:
                    error_callback(error_msg)
                connection_results['failed'] += 1
        
        # Final summary after delay to let connections complete
        def send_final_summary():
            time.sleep(5)  # Wait for connections to complete
            if error_callback:
                error_callback(f"📊 Summary: {connection_results['success']} connected, {connection_results['failed']} failed from {connection_results['total']} total")
        
        summary_thread = Thread(target=send_final_summary)
        summary_thread.start()

    def check_status(self, twitch_accounts: QuerySet[TwitchAccount]) -> dict[str, Union[None, bool]]:
        result = dict()
        for twitch_account in twitch_accounts:
            status = self.get_status(twitch_account.login)
            result[twitch_account.login] = status
            logger.debug(f"Account {twitch_account.login} status: {status}")
        return result

    def send(self, twitch_account: TwitchAccount, channel: str, message: str) -> bool:
        """
        Enhanced send method with better error handling and automatic reconnection
        """
        account_info = f"[{twitch_account.login}]"
        
        if not self.contains(twitch_account.login):
            logger.warning(f"Account {twitch_account.login} not found in chat manager")
            return False
            
        if not self.get_status(twitch_account.login):
            logger.warning(f"Account {twitch_account.login} is not connected")
            
            # Try to reconnect if account is disconnected
            chat: IRCChat = self.get(twitch_account.login)
            if not chat.is_connected:
                logger.info(f"Attempting to reconnect account {twitch_account.login}")
                try:
                    if chat.connect():
                        self.set_status(twitch_account.login, True)
                        logger.info(f"Successfully reconnected account {twitch_account.login}")
                    else:
                        logger.error(f"Failed to reconnect account {twitch_account.login}")
                        return False
                except Exception as e:
                    logger.error(f"Error reconnecting account {twitch_account.login}: {str(e)}")
                    return False
        
        try:
            chat: IRCChat = self.get(twitch_account.login)
            
            # Additional validation before sending
            if not chat.is_connected:
                logger.error(f"Chat for {twitch_account.login} is still not connected after reconnection attempt")
                return False
            
            thread = Thread(target=self.__send_message, args=(chat, channel, message))
            thread.start()
            logger.debug(f"Message queued by {twitch_account.login} to #{channel}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message from {twitch_account.login}: {str(e)}")
            return False

    def disconnect(self, chatter_name: str, twitch_accounts: QuerySet[TwitchAccount]):
        """
        Enhanced disconnect method with logging
        """
        logger.info(f"Disconnecting {twitch_accounts.count()} accounts for user {chatter_name}")
        
        for twitch_account in twitch_accounts:
            try:
                if self.contains(twitch_account.login):
                    chat: IRCChat = self.remove(twitch_account.login, chatter_name)
                    if chat is not None:
                        logger.info(f"Disconnecting account {twitch_account.login}")
                        thread = Thread(target=self.__close_chat, args=(chat,))
                        thread.start()
                    else:
                        logger.debug(f"Account {twitch_account.login} was already disconnected")
                        
            except Exception as e:
                logger.error(f"Error disconnecting account {twitch_account.login}: {str(e)}")
