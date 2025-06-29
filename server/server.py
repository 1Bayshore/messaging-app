import websockets.server
import asyncio
import json

user_ids_to_websockets = {}

async def encrypt_message(message):
    # XXX encryption not implemented yet
    return message

async def send_message(dest_user_id, src_user_id, message_text):
    message_dict = {
        'dest_userid': dest_user_id,
        'src_userid': src_user_id,
        'message': message_text
    }
    message_json = json.dumps(message_dict)
    for websocket in user_ids_to_websockets[dest_user_id]:
        await websocket.send(message_json)

async def forward_message(websocket):
    async for message_str in websocket:
        # load the message, catching if message is corrupt
        try:
            message_dict = json.loads(message_str)
            dest_user_id = message_dict['dest_userid']
            src_user_id = message_dict['src_userid']
            message_text = message_dict['message']
        except json.decoder.JSONDecodeError or KeyError:
            # send an error message back to the sender
            error_user_id = user_ids_to_websockets.keys()[user_ids_to_websockets.values().index(websocket)]
            await send_message(error_user_id, 'error_msgs', encrypt_message('Error: Your message was corrupted or formatted incorrectly'))
            return

        # handle new connections
        if websocket not in [x for xs in user_ids_to_websockets.values() for x in xs]:
            # check if the user is already connected once to avoid overwriting
            try:
                user_ids_to_websockets[src_user_id].append(websocket)
            except KeyError:
                user_ids_to_websockets[src_user_id] = [websocket]

        # forward the message
        await send_message(dest_user_id, src_user_id, message_text)


async def main():
    async with websockets.server.serve(forward_message, '0.0.0.0', 19125) as server:
        await server.serve_forever()

asyncio.run(main())
