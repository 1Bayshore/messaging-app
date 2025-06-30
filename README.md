# messaging-app
It's a messaging app! Mostly for me to learn how to build one

## How it works
Basically, there are two types of instances. Clients allow sending and receiving of messages, and servers forward messages to other servers and clients. The same protocol is used between all of the servers and clients.

### Servers
The server code is written in Python. It focuses on forwarding messages to the correct clients.

### Clients
While I hope to someday have a lot of different types of clients, for now the only client is a web client. It allows users to send and receive messages.

### Protocol
The protocol consists of a JSON dictionary containing the following:
- Destination user
- Origin user
- Message (encrypted) (coming soon)
- Timestamp

## A note about security
This is not a super secure messaging system yet! I'm still building it. When I am finished, it should be more secure.
