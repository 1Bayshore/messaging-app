# messaging-app
It's a messaging app! Mostly for me to learn how to build one

## How it will work
Basically, there will two types of instances. Clients will allow sending and receiving of messages, and servers will forward messages to other servers and clients. The same protocol will be used between all of the servers and clients.

### Servers
The server code will be written in Python. It will focus on forwarding messages to the correct clients.

### Clients
While I hope to someday have a lot of different types of clients, for now the main client will be a web client. It will focus on allowing users to send and receive messages.

### Protocol
The protocol will consist of a JSON dictionary containing the following:
- Destination
- Message (encrypted)

## A note about security
This is not a super secure messaging system yet! I'm still building it. When I am finished, it should be more secure.
