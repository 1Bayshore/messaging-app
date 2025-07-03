import websockets.exceptions
import websockets.server
import asyncio
import json
import datetime
import argon2
import time
import math
import base64

from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_OAEP

server_address = '127.0.0.1'
is_user_server = True

username = None
ph = argon2.PasswordHasher()
hash_obj = None

user_ids_to_websockets = {}
message_history = []

async def encrypt_message(message):
    with open('public_key.pem', 'rb') as f:
        public_key = RSA.import_key(f.read())
    
    cipher = PKCS1_OAEP.new(public_key)

    print(message)
    encrypted_message = str(base64.b64encode(cipher.encrypt(bytes(message, 'utf-8'))), 'utf-8')
    print(encrypted_message)
    return encrypted_message

async def decrypt_message(encrypted_message):
    with open('private_key.pem', 'rb') as f:
        private_key = RSA.import_key(f.read())
    
    cipher = PKCS1_OAEP.new(private_key)
    print(encrypted_message)
    message = str(cipher.decrypt(bytes(base64.b64decode(encrypted_message), 'utf-8')), 'utf-8')
    print(message)
    return message

def save_messages():
    if not is_user_server:
        return
    with open('message_history.json', 'w') as f:
        f.write(json.dumps(message_history))

def load_messages():
    if not is_user_server:
        return
    try:
        with open('message_history.json') as f:
            global message_history
            message_history = json.loads(f.read())
        print('Loaded messages. Starting server...')
    except FileNotFoundError:
        print('No messages found. Starting empty server...')


async def send_message(dest_user_id, src_user_id, message_text, timestamp, type='message', save=True, forwarding_dest_user_id=None, single_socket_only=None):
    message_dict = {
        'dest_userid': forwarding_dest_user_id if forwarding_dest_user_id else dest_user_id,
        'src_userid': src_user_id,
        'type': type,
        'message': message_text,
        'timestamp': timestamp
    }

    message_json = json.dumps(message_dict)

    # save messages here, so that they aren't lost if the recipiant is offline
    # exception is if the save flag is set to false, for situations when the message is already saved
    # or if the message is a ping or login, which we don't save
    # definitely don't save keys!
    if save and (type not in ['ping', 'login', 'connection_successful', 'key1', 'key2']):
        message_history.append(message_dict)
    
    if single_socket_only:
        try:
            await single_socket_only.send(message_json)
        except websockets.exceptions.ConnectionClosed:
            del user_ids_to_websockets[dest_user_id][user_ids_to_websockets[dest_user_id].index(single_socket_only)]

    # forward the message if possible
    try:
        for websocket in user_ids_to_websockets[dest_user_id]:
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                del user_ids_to_websockets[dest_user_id][user_ids_to_websockets[dest_user_id].index(websocket)]
    except KeyError:
        pass # user is not online

    save_messages()

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
                await send_message(error_user_id, server_address, await encrypt_message('Error: Your message was corrupted or formatted incorrectly'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'error')
                continue

            # handle new connections
            if websocket not in [x for xs in user_ids_to_websockets.values() for x in xs]:
                # confirm this is a valid handshake, rather than an impersonation
                if message_type != 'login':
                    # impersonation, drop it
                    continue
                
                l_data = json.loads(message_text)
                if (l_data['username'] != username):
                    # incorrect login
                    await send_message(src_user_id, server_address, await encrypt_message('Error: Incorrect username or password'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'error', single_socket_only=websocket)
                    continue
                try:
                    global hash_obj
                    ph.verify(hash_obj, l_data['pass_hash'])
                except argon2.exceptions.VerifyMismatchError:
                    # incorrect login
                    await send_message(src_user_id, server_address, await encrypt_message('Error: Incorrect username or password'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'error', single_socket_only=websocket)
                    continue

                # check if the user is already connected once to avoid overwriting
                try:
                    user_ids_to_websockets[src_user_id].append(websocket)
                except KeyError:
                    user_ids_to_websockets[src_user_id] = [websocket]
                
                # if user server, send the keys to the new login
                if is_user_server:
                    with open('public_key.pem', 'rb') as f:
                        await send_message(src_user_id, server_address, str(f.read(), 'utf-8'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'key1', single_socket_only=websocket)
                    
                    with open('private_key.pem', 'rb') as f:
                        await send_message(src_user_id, server_address, str(f.read(), 'utf-8'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'key2', single_socket_only=websocket)

                # forward the user's messages to their new connection
                for msg_backup in message_history:
                    if msg_backup['dest_userid'] == src_user_id or msg_backup['src_userid'] == src_user_id:
                        await send_message(src_user_id, msg_backup['src_userid'], msg_backup['message'], msg_backup['timestamp'], msg_backup['type'], save=False, forwarding_dest_user_id=msg_backup['dest_userid'], single_socket_only=websocket)
                await send_message(src_user_id, server_address, await encrypt_message('Connected successfully.'), datetime.datetime.now(datetime.timezone.utc).isoformat(), 'connection_successful', single_socket_only=websocket)


            # forward the message
            await send_message(dest_user_id, src_user_id, message_text, timestamp, message_type)
    except websockets.exceptions.ConnectionClosedError:
        pass

def login_signup(mode=None, attempt=0):
    global username
    global hash_obj
    if mode:
        log_sign = mode
    else:
        log_sign = input('(L)og in or (S)ign up: ')
    
    if log_sign in ['s', 'sign up', '2']:
        # sign up
        username = input('Username: ')
        hash_obj = ph.hash(input('Password: '))
        login_data = {}
        try:
            with open('login_info.json') as f:
                login_data = json.loads(f.read())
        except FileNotFoundError:
            pass
        if username in login_data.keys():
            print('User already exists.')
            login_signup()
            return
        
        login_data[username] = hash_obj
        with open('login_info.json', 'w') as f:
            f.write(json.dumps(login_data))
        # generate a public - private key for the user
        key = RSA.generate(2048)
        private_key = key.export_key()
        with open('private_key.pem', 'wb') as f:
            f.write(private_key)
        
        public_key = key.public_key().exportKey()
        with open('public_key.pem', 'wb') as f:
            f.write(public_key)
    
    elif log_sign in ['l', 'log in', '1']:
        # log in
        username = input('Username: ')
        try:
            with open('login_info.json') as f:
                login_data = json.loads(f.read())
        except FileNotFoundError:
            print('No logins exist. Please sign up.')
            login_signup()
            return

        try:
            hash_obj = login_data[username]
            ph.verify(login_data[username], input('Password: '))
        except argon2.exceptions.VerifyMismatchError:
            print('Incorrect password, please try again.')
            time.sleep(math.exp2(attempt)/4) # wait a little bit before allowing them to try again
            login_signup('sign up', attempt+1)
        
    else:
        login_signup()

async def main():
    if is_user_server:
        login_signup()

    print('Starting server...')
    async with websockets.server.serve(forward_message, server_address, 19125) as server:
        await server.serve_forever()

load_messages()
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print('\nServer stopped, saving messages')
    save_messages()
    print('Saved message, exiting.')
