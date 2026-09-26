import socketio

# Khởi tạo AsyncServer của Socket.IO hỗ trợ CORS
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

@sio.event
async def connect(sid, environ, auth=None):
    query_string = environ.get('QUERY_STRING', '')
    query_params = dict(qp.split('=') for qp in query_string.split('&') if '=' in qp)
    user_id = None
    if auth and isinstance(auth, dict) and 'userId' in auth:
        user_id = auth['userId']
    elif 'userId' in query_params:
        user_id = query_params['userId']

    if user_id:
        await sio.enter_room(sid, f"user:{str(user_id)}")
        print(f"🔌 [Socket.IO Python] User {user_id} đã kết nối (Socket ID: {sid})")

@sio.event
async def join_conversation(sid, conversation_id):
    if conversation_id:
        room_name = f"conv:{str(conversation_id)}"
        await sio.enter_room(sid, room_name)
        print(f"💬 Socket {sid} đã vào cuộc hội thoại {room_name}")

@sio.event
async def leave_conversation(sid, conversation_id):
    if conversation_id:
        room_name = f"conv:{str(conversation_id)}"
        await sio.leave_room(sid, room_name)

@sio.event
async def typing(sid, data):
    conversation_id = data.get('conversationId')
    if conversation_id:
        room_name = f"conv:{str(conversation_id)}"
        await sio.emit('user_typing', data, room=room_name, skip_sid=sid)

@sio.event
async def stop_typing(sid, data):
    conversation_id = data.get('conversationId')
    if conversation_id:
        room_name = f"conv:{str(conversation_id)}"
        await sio.emit('user_stop_typing', data, room=room_name, skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f"🔌 [Socket.IO Python] Socket {sid} đã ngắt kết nối")

async def send_notification_to_user(user_id, notification_data):
    """Gửi thông báo đẩy trực tiếp tới user qua room cá nhân"""
    if not user_id:
        return
    room_name = f"user:{str(user_id)}"
    await sio.emit('notification:new', notification_data, room=room_name)

async def emit_message_to_conversation(conversation_id, message_data, recipient_ids=None):
    """Phát tin nhắn mới vào phòng trò chuyện VÀ phòng cá nhân của người nhận"""
    if not conversation_id:
        return
    # Phát vào phòng cuộc trò chuyện
    conv_room = f"conv:{str(conversation_id)}"
    await sio.emit('receive_message', message_data, room=conv_room)

    # Phát tới từng người nhận
    if recipient_ids:
        if isinstance(recipient_ids, list):
            for uid in recipient_ids:
                if uid:
                    await sio.emit('receive_message', message_data, room=f"user:{str(uid)}")
        else:
            await sio.emit('receive_message', message_data, room=f"user:{str(recipient_ids)}")
