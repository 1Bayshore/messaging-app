import websockets.exceptions
import websockets.server
import asyncio
import json
import datetime

server_address = '127.0.0.1'

user_ids_to_websockets = {}
message_history = []

async def encrypt_message(message):
    # XXX encryption not implemented yet
    return message

async def decrypt_message(message):
    # XXX encryption not implemented yet
    return message

async def send_message(dest_user_id, src_user_id, message_text, timestamp, type='message', save=True, forwarding_dest_user_id=None):
    message_dict = {
        'dest_userid': forwarding_dest_user_id if forwarding_dest_user_id else dest_user_id,
        'src_userid': src_user_id,
        'type': type,
        'message': message_text,
        'timestamp': timestamp
    }

    # save messages here, so that they aren't lost if the recipiant is offline
    # exception is if the save flag is set to false, for situations when the message is already saved
    # or if the message is a ping, which we don't save
    if save and (type != 'ping'):
        message_history.append(message_dict)

    # forward the message if possible
    message_json = json.dumps(message_dict)
    try:
        for websocket in user_ids_to_websockets[dest_user_id]:
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                del user_ids_to_websockets[dest_user_id][user_ids_to_websockets[dest_user_id].index(websocket)]
    except KeyError:
        pass # user is not online

    with open('message_history.json', 'w') as f:
        f.write(json.dumps(message_history))

async def forward_message(websocket):
    try:
        async for message_str in websocket:
            # load the message, catching if message is corrupt
            try:
                message_dict = json.loads(message_str)
                dest_user_id = message_dict['dest_userid']
                src_user_id = message_dict['src_userid']
                message_type = message_dict['type']
                message_text = message_dict['message']
                timestamp = message_dict['timestamp']
            except (json.decoder.JSONDecodeError, KeyError):
                # send an error message back to the sender
                error_user_id = user_ids_to_websockets.keys()[list(user_ids_to_websockets.values()).index(websocket)]
                await send_message(error_user_id, server_address, encrypt_message('Error: Your message was corrupted or formatted incorrectly'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'error')
                continue

            # handle new connections
            if websocket not in [x for xs in user_ids_to_websockets.values() for x in xs]:
                # confirm this is a valid handshake, rather than an impersonation
                if message_type != 'ping':
                    # impersonation, drop it
                    continue

                # check if the user is already connected once to avoid overwriting
                try:
                    user_ids_to_websockets[src_user_id].append(websocket)
                except KeyError:
                    user_ids_to_websockets[src_user_id] = [websocket]

                # forward the user's messages to their new connection
                for msg_backup in message_history:
                    if msg_backup['dest_userid'] == src_user_id or msg_backup['src_userid'] == src_user_id:
                        await send_message(src_user_id, msg_backup['src_userid'], msg_backup['message'], msg_backup['timestamp'], msg_backup['type'], save=False, forwarding_dest_user_id=msg_backup['dest_userid'])

            # forward the message
            await send_message(dest_user_id, src_user_id, message_text, timestamp, message_type)
    except websockets.exceptions.ConnectionClosedError:
        pass


async def main():
    async with websockets.server.serve(forward_message, server_address, 19125) as server:
        await server.serve_forever()

try:
    with open('message_history.json') as f:
        message_history = json.loads(f.read())
    print('Loaded messages. Starting server...')
except FileNotFoundError:
    print('No messages found. Starting empty server...')

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print('\nServer stopped, saving messages')
    with open('message_history.json', 'w') as f:
        f.write(json.dumps(message_history))
    print('Saved message, exiting.')
