from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from datetime import datetime
from . import models

import openai, environ, deepl, boto3, json, replicate
import google.generativeai as palm


class _BaseConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        self.prefix = kwargs.pop("prefix", "base")
        self.room = None
        super().__init__(*args, **kwargs)

    def get_current_time(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_client_key(self, user):
        return f"user{user.pk}"

    async def post_accept(self, user):
        raise NotImplementedError

    async def pre_disconnect(self, user):
        raise NotImplementedError

    async def post_disconnect(self, user):
        raise NotImplementedError

    # WebSocket接続時の処理
    async def connect(self):
        try:
            user = self.scope["user"]
            pk = int(self.scope["url_route"]["kwargs"]["room_id"])
            self.room = await database_sync_to_async(models.Room.objects.get)(pk=pk)
            self.group_name = f"{self.prefix}{pk}"
            is_assigned = await database_sync_to_async(self.room.is_assigned)(user)

            if is_assigned:
                await self.accept()
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.post_accept(user)

        except Exception as err:
            raise Exception(err)

    # WebSocket切断時の処理
    async def disconnect(self, close_code):
        user = self.scope["user"]
        await self.pre_disconnect(user)
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.close()
        await self.post_disconnect(user)


# global instance for chat
g_chat_clients = {}

# ChatConsumerクラス: チャット用のWebSocketコンシューマー
class ChatConsumer(_BaseConsumer):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "chat-room"
        super().__init__(*args, **kwargs)

    async def post_accept(self, user):
        # チャットルームへの参加メッセージを送信
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_system_message",
                "is_connected": True,
                "username": str(user),
                "client_key": self.get_client_key(user),
            },
        )

    async def pre_disconnect(self, user):
        # チャットルームからの離脱メッセージを送信
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_system_message",
                "is_connected": False,
                "username": str(user),
                "client_key": self.get_client_key(user),
            },
        )

    async def post_disconnect(self, user):
        target = g_chat_clients.get(self.group_name, None)

        # 参加者がいなくなった場合、辞書から削除
        if target is not None and len(target) == 0:
            del g_chat_clients[self.group_name]

    # システムメッセージの送信
    async def send_system_message(self, event):
        try:
            room_name = str(self.room)
            is_connected = event["is_connected"]
            username = event["username"]
            client_key = event["client_key"]
            current_time = self.get_current_time()
            target = g_chat_clients.get(self.group_name, {})

            if is_connected:
                target[client_key] = username
                message_type = "connect"
                message = f"Join {username} to {room_name}"
            else:
                del target[client_key]
                message_type = "disconnect"
                message = f"Leave {username} from {room_name}"

            g_chat_clients[self.group_name] = target

            await self.send_json(
                content={
                    "type": message_type,
                    "username": "system",
                    "datetime": current_time,
                    "content": message,
                    "members": g_chat_clients[self.group_name],
                }
            )
        except Exception as err:
            raise Exception(err)

    # WebSocketからメッセージを受信
    async def receive_json(self, content):
        try:
            user = self.scope["user"]
            message = content["content"]
            await self.create_message(user, message)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "send_chat_message",
                    "msg_type": "user_message",
                    "username": str(user),
                    "message": message,
                },
            )
        except Exception as err:
            raise Exception(err)

    # チャットメッセージの送信
    async def send_chat_message(self, event):
        try:
            msg_type = event["msg_type"]
            username = event["username"]
            message = event["message"]
            current_time = self.get_current_time()
            await self.send_json(
                content={
                    "type": msg_type,
                    "username": username,
                    "datetime": current_time,
                    "content": message,
                }
            )
        except Exception as err:
            raise Exception(err)

    # メッセージをデータベースに保存
    @database_sync_to_async
    def create_message(self, user, message):
        try:
            models.Message.objects.create(
                owner=user,
                room=self.room,
                content=message,
            )
        except Exception as err:
            raise Exception(err)


class AI:
    def __init__(self):
        env = environ.Env()
        env.read_env(".env")

        openai.api_key = env("CHATGPT_API_KEY")
        self.translator = deepl.Translator(env("DEEPL_API_KEY"))
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")
        palm.configure(api_key=env("PALM_API_KEY"))

        self.User_message = "Hello"
        self.prompt = "Hello"

    def ChatGPT(self):
        input_text = self.translator.translate_text(
            self.User_message, source_lang="JA", target_lang="EN-US"
        )

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": input_text},
            ],
        )

        output_text = self.translator.translate_text(
            response["choices"][0]["message"]["content"],
            source_lang="JA",
            target_lang="EN-US",
        )

        return output_text

    def Claude(self):
        body = json.dumps(
            {
                "prompt": self.prompt,
                "max_tokens_to_sample": 500,
            }
        )

        resp = self.bedrock_runtime.invoke_model(
            modelId="anthropic.claude-v2",
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        answer = resp["body"].read().decode()
        output_text = json.loads(answer)["completion"]

        return output_text

    def Palm2(self):
        response = palm.chat(messages=self.prompt)
        return response.last

    def Llama(self):
        output = replicate.run(
            "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
            input={"prompt": self.prompt, "system_prompt": self.prompt},
        )
        s = ""
        for item in output:
            s += item
        return s
