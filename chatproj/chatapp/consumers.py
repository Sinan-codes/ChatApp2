from asgiref.sync import sync_to_async
import json
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from urllib.parse import parse_qs


class ChatConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        query_string = self.scope['query_string'].decode('utf-8')
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]

        if token:
            try:
                decode_data = jwt.decode(token, setting.SECRET_KEY, algorithms=['HS256'])
                self.user = await self.get_user(decode_data['user_id'])
                self.scope["user"] = self.user

            except jwt.exceptions.ExpiredSignatureError:
                await self.close(code=4000)
                return 
            
            except jwt.exceptions.InvalidTokenError:
                await self.close(code=4001)
                return
            
        else:
            await self.close(code=4002)
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f"chat {self.conversation_id}"

        # Add channel to the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # accept websocket connections
        await self.accept()

        user_data = await self.get_user_data(self.user)
        await self.channel.layer.group_send(
            self.room_group_name,
            {
                'type': 'online_status',
                'online_user': [user_data],
                'status': 'online',
            }

        )


    async def disconnect(self, close_code):
        if hassattr(self, 'room_group_name'):
            # notify others about the disconnect
            user_data = await self.get_user_data(self.scope["user"])
            await self.channel_layer_group_send(
                self.room_group_name,
                {
                    'type': 'online_status',
                    'online_user': [user_data],
                    'status': 'offline',
                }
            )

            # Remove channel from group
            await self.channel_layer_group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        event_type = text_data_json.get("type")

        if event_type == "chat_message":
            message_content = text_data_json.get('message')
            user_id = text_data_json.get('user')

            try:
                user = await self.get_user(user_id)
                conversation = await self.get_conversation(self.conversation_id)
                from .serializers import UserListSerializer
                user_data = UserListSerializer(user).data

            except Exception as e:
                print("Error saving message: {e}")

        elif event_type == 'typing':
            try:
                user_data = await self.get_user_data(self.scope['user'])
                receiver_id = text_data_json.get('receiver')

                if reveiver_id is not None:
                    if isinstance(receiver_id, (str, int, float)):
                        receiver_id = int(receiver_id)

                        if receiver_id != self.scope["user"].id:
                            print(f"{user_data['username']} is typing for Receiver: {receiver_id} ")
                            await self.channel_layer.group_send(
                                self.room_group_name,
                                {
                                    'type': 'typing',
                                    'online_user': user_data,
                                    'receiver': receiver_id,
                                }
                            )
                        else:
                            print(f"User is typing for themselves")

                    else :
                        print(f"Invalid receiver ID: {type(receiver_id)}")

                else:
                    print("No receiver ID provided.")
            
            except ValueError as e:
                print(f"Error parsing receiver ID: {e}")

            except Exception as e:
                print(f"Error getting user data: {e}")

            
    # helper functions
    async def chat_message(self, event):
        message = event['message']
        user = event['user']
        timestamp = event['timestamp']

        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': 'message',
            'user': 'user',
            'timestamp': 'timestamp',
        }))


    async def typing(self, event):
        user = event['typing']
        receiver = event.get('receiver')
        is_typing = event.get('is_typing', False)
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user': user,
            'receiver': receiver,
            'is_typing': is_typing,
        }))

    async def online_status(self, event):
        await self.send(text_data=json.dumps(event))

    

    @sync_to_async
    def get_user(self, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.object.get(id=user_id)

    @sync_to_async
    def get_user_data(self, user):
        from .serilaizer import UserListSerializer
        return UserListSerializer(user).data

    @sync_to_async
    def get_conversation(self, conversation_id):
        from .models import Conversation
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            print(F"Conversation with {conversation_id} does not exist")

    @sync_to_async
    def save_message(self, conversation, user, content):
        from .models import Message
        Message.object.create(
            conversation=conversation,
            sender=user,
            content=content,
        )

    # @sync_to_async
    # def get_user_model(self):
    #     from django.contrib.auth import get_user_model



