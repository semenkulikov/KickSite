from datetime import datetime
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from time import sleep
from threading import Thread
from channels.db import database_sync_to_async
from django.db.transaction import atomic
from asgiref.sync import async_to_sync
from TwitchApp.chat_manager import ChatManager
from TwitchApp.models import TwitchAccount
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from StatsApp.models import Statistic
import logging

logger = logging.getLogger(__name__)


class TwitchAppChatWs(AsyncJsonWebsocketConsumer):
    """
    __clients = {
        "nickname_1": {
            "state": "ACTIVE",
            "twitch_stats": [
                "00:00:00 00.00.2023|twitch_channel|twitch_account|Message",
                "00:00:00 00.00.2023|twitch_channel|twitch_account|Message",
                ]
            }
        }
    }
    twitch_stats[i].split("|", 3)
    """
    __clients = dict() # (2|3)
    def send_error_message(self, message: str):
        print(message)
        async_to_sync(self.send_message)({
            "message": message,
            "event": "TWITCH_SHOW_ERROR"
        })
    @database_sync_to_async
    def accounts_connect(self, user: User):
        chat_manager = ChatManager()
        user_twitch_accounts = TwitchAccount.objects.filter(user=user)
        chat_manager.connect(user.username, user_twitch_accounts, use_ssl=True,error_callback = self.send_error_message)

    @database_sync_to_async
    def check_accounts(self, user: User):
        chat_manager = ChatManager()
        user_twitch_accounts = TwitchAccount.objects.filter(user=user)
        return chat_manager.check_status(user_twitch_accounts)

    async def connect(self):
        # print("WS CONNECT")

        user = self.scope["user"]
        if user not in self.__clients:
            self.__clients[user] = {"state": "ACTIVE"}
        else:
            self.__clients[user]["state"] = "ACTIVE"

        # print(self.__clients[user])

        # MUST accept connection first before sending any messages
        await self.accept()

        accounts_status = None

        await self.accounts_connect(user)

        accounts_status = await self.check_accounts(user)

        # Show accounts if we have any connections (successful or failed)
        # Don't require ALL accounts to be successful
        if accounts_status:
            # Count successful connections
            successful_connections = sum(1 for status in accounts_status.values() if status is True)
            total_accounts = len(accounts_status)
            
            logger.info(f"Account status summary: {successful_connections}/{total_accounts} connected successfully")
            
            # Always show accounts if we have any, regardless of success/failure ratio
            await self.send_message({"message": accounts_status, "event": "TWITCH_LOAD_ACCOUNTS"})
        else:
            # Only show "await" if we have no accounts at all
            await self.send_message({"message": "No accounts found", "event": "TWITCH_STOP_AWAIT_ACCOUNTS"})

        if "start_work_time" in self.__clients[user]:
            print(self.__clients[user]["start_work_time"])
            prepared_data = {
                "startWorkTime": self.__clients[user]["start_work_time"].strftime('%H:%M:%S %d.%m.%Y'),
                "messages": len(self.__clients[user]["twitch_stats"])
            }
            await self.send_message({"message": prepared_data,
                                     "event": "TWITCH_START_WORK"})

    async def disconnect(self, code):
        self.__clients[self.scope["user"]]["state"] = "INACTIVE"
        client = Thread(target=self.live_check,
                        daemon=True,
                        args=(self.scope["user"],))
        client.start()
        # print("WS DISCONNECT", code)

    async def receive(self, text_data):
        # print("WS RECEIVE")
        response = json.loads(text_data)
        # print(response)
        user = self.scope["user"]
        event = response.get("event", None)
        message = response.get("message", None)
        if event == "TWITCH_SEND_MESSAGE":
            if "twitch_stats" in self.__clients[user]:
                chat_manager = ChatManager()
                try:
                    twitch_account = await TwitchAccount.objects.aget(login=message["account"], user=user)
                    # FIX ME UNCOMMENTED AFTER TESTS
                    chat_manager.send(twitch_account, message["channel"], message["message"])
                    auto_status = "a" if message["auto"] else "m"
                    now_time = timezone.now().strftime('%H:%M:%S.%f %d.%m.%Y')
                    log_message = f"{now_time}|{message['channel']}|{twitch_account.login}|{auto_status}|{message['message']}"
                    self.__clients[user]["twitch_stats"].append(log_message)
                except TwitchAccount.DoesNotExist:
                    pass
            else:
                await self.send_message({"message": 'You haven\'t started work. Click on the "Start work" button',
                                         "event": "TWITCH_SHOW_ERROR"})

            # print(self.scope["user"].username, message["account"], message["channel"], message["message"])
        elif event == "TWITCH_AWAIT_ACCOUNTS":
            accounts_status = await self.check_accounts(self.scope["user"])
            if len(accounts_status.keys()):
                bool_status_values = set(accounts_status.values())
                if len(bool_status_values) == 1 and True in bool_status_values:
                    await self.send_message({"message": accounts_status, "event": "TWITCH_LOAD_ACCOUNTS"})
            else:
                await self.send_message({"message": "STOP", "event": "TWITCH_STOP_AWAIT_ACCOUNTS"})
        elif event == "TWITCH_START_WORK":
            if "twitch_stats" not in self.__clients[user] and "start_work_time" not in self.__clients[user]:
                self.__clients[user]["twitch_stats"] = []
                self.__clients[user]["start_work_time"] = timezone.now()
            prepared_data = {
                "startWorkTime": self.__clients[user]["start_work_time"].strftime('%H:%M:%S %d.%m.%Y'),
                "messages": len(self.__clients[user]["twitch_stats"])
            }
            await self.send_message({"message": prepared_data, "event": "TWITCH_START_WORK"})
            # print(event, message)
        elif event == "TWITCH_END_WORK":
            if "twitch_stats" in self.__clients[user] and len(self.__clients[user]["twitch_stats"]):
                await self.end_work(user)
            await self.send_message(
                {"message": "End work",
                 "event": "TWITCH_END_WORK"})
            del self.__clients[user]["twitch_stats"]
            del self.__clients[user]["start_work_time"]
            # print(event, message)
        elif event == "TWITCH_CONNECT":
            # print(event, message, self.__clients)
            ...

    async def send_message(self, res):
        # print(self.scope)
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "payload": res,
        }))

    def live_check(self, user: User):
        timer = 5
        while timer:
            sleep(1)
            if self.__clients[user]["state"] == "ACTIVE":
                break
            timer -= 1
        if self.__clients[user]["state"] == "INACTIVE":
            chat_manager = ChatManager()
            chat_manager.disconnect(user.username, TwitchAccount.objects.filter(user=user))
            if "twitch_stats" in self.__clients[user] and len(self.__clients[user]["twitch_stats"]):
                self.end_work(user)
            del self.__clients[user]

    @database_sync_to_async
    def end_work(self, user: User):
        # print(self.__clients[user]["twitch_stats"])
        return
        Statistic.objects.create(type=Statistic.Types.TWITCH,
                                 data="\n".join(self.__clients[user]["twitch_stats"]),
                                 start=self.__clients[user]["start_work_time"],
                                 user=user)


class TwitchAppStatsWs(AsyncJsonWebsocketConsumer):

    @database_sync_to_async
    def prepare_user_stat(self, username, count):
        # user_stat = user.statistics.filter(type=Statistic.Types.TWITCH)
        result = {}
        try:
            user_stat = Statistic.objects.filter(user__username=username, type=Statistic.Types.TWITCH).order_by('-id')[:int(count)]
            result["status"] = {"code": "success"}
            result["stat"] = list(map(lambda x: x.serialized_object, reversed(user_stat)))
        except ValueError:
            result["status"] = {"code": "error", "text": "Invalid parameters"}
        return result

    async def connect(self):
        print("WS CONNECT")
        user = self.scope["user"]
        await self.accept()

    async def disconnect(self, code):
        print("WS DISCONNECT", code)

    async def receive(self, text_data):
        print("WS RECEIVE")
        response = json.loads(text_data)
        print(response)
        user = self.scope["user"]
        event = response.get("event", None)
        message = response.get("message", None)
        if event == "TWITCH_CONNECT":
            print(event, message)
        elif event == "TWITCH_STATS_SHOW":
            print(event, message)
            message_user = message["user"].replace(" ", "").replace("	", "")
            if not message_user == "yourself" and user.is_staff:
                request_user = message_user
            else:
                request_user = user.username

            stat = await self.prepare_user_stat(request_user, message["count"])
            await self.send_message({"message": stat, "event": "TWITCH_STATS_SHOW"})

    async def send_message(self, res):
        print(self.scope)
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "payload": res,
        }))
