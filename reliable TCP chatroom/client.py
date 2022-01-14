import socket
import signal
import sys
import argparse
from urllib.parse import urlparse
import selectors

# Selector for helping us select incoming data from the server and messages typed in by the user.

sel = selectors.DefaultSelector()

# Socket for sending messages.

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# User name for tagging sent messages.

user = ''
filename = ''
filenameR = ''
reading = False
BUFFER = 32768


# Signal handler for graceful exiting.  Let the server know when we're gone.

def signal_handler(sig, frame):
    print('Interrupt received, shutting down ...')
    message = f'DISCONNECT {user} CHAT/1.0\n'
    client_socket.send(message.encode())
    sys.exit(0)


# Simple function for setting up a prompt for the user.

def do_prompt(skip_line=False):
    if (skip_line):
        print("")
    print("> ", end='', flush=True)


# Read a single line (ending with \n) from a socket and return it.
# We will strip out any \r and \n in the process.

def get_line_from_socket(sock):
    line = sock.recv(BUFFER)
    return line


# Function to handle incoming messages from server.  Also look for disconnect messages to shutdown.

def handle_message_from_server(sock, mask):
    global filename, reading, filenameR, haveFile
    msg = get_line_from_socket(sock)
    try:
        message = msg.decode()
        words = message.strip("\n").split(' ')
        if words[0] == 'DISCONNECT':
            print('Disconnected from server ... exiting!')
            sys.exit(0)
        if "@" in words[0]:
            reading = False

        # sending file
        elif words[0] == 'ReadySend':
            filename = words[1]
            try:
                # handle the file with give name
                handleFileSend(filename)
            except FileNotFoundError:
                print(f"{filename} does not exist!")

        # recving file
        elif words[0] == 'ReadyReceive':
            filenameR = words[1]
            sizes = words[3]
            fromUser = words[2]
            print(f"\nIncoming filename: {filenameR}\nOrigin From: {fromUser}\nContent size: {sizes}")
            reading = True
            haveFile = True

        # reading the file
        if reading:
            with open(filenameR, "wb") as writes:
                if message.startswith("ReadyReceive"):
                    pass
                else:
                    bytes_write = message.encode()
                    writes.write(bytes_write)
        else:
            if words[0] != 'ReadyReceive' or words[0] != 'ReadySend':
                print(message)
                do_prompt()

    except UnicodeDecodeError:
        with open(filenameR, "wb") as writes:
            writes.write(msg)

# Function to handle file transfer
def handleFileSend(filename):
    with open(filename, 'rb') as readfile:
        myChuck = readfile.read(BUFFER)
        while myChuck:
            client_socket.send(myChuck)
            readfile.flush()
            myChuck = readfile.read(BUFFER)
    print(f"{filename} sent successfully")


# Function to handle incoming messages from user.

def handle_keyboard_input(file, mask):
    line = sys.stdin.readline()
    message = f'@{user}: {line}'
    client_socket.send(message.encode())
    do_prompt()


# Our main function.

def main():
    global user
    global client_socket

    # Register our signal handler for shutting down.

    signal.signal(signal.SIGINT, signal_handler)

    # Check command line arguments to retrieve a URL.

    parser = argparse.ArgumentParser()
    parser.add_argument("user", help="user name for this user on the chat service")
    parser.add_argument("server", help="URL indicating server location in form of chat://host:port")
    args = parser.parse_args()

    # Check the URL passed in and make sure it's valid.  If so, keep track of
    # things for later.

    try:
        server_address = urlparse(args.server)
        if ((server_address.scheme != 'chat') or (server_address.port == None) or (server_address.hostname == None)):
            raise ValueError
        host = server_address.hostname
        port = server_address.port
    except ValueError:
        print('Error:  Invalid server.  Enter a URL of the form:  chat://host:port')
        sys.exit(1)
    user = args.user

    # Now we try to make a connection to the server.

    print('Connecting to server ...')
    try:
        client_socket.connect((host, port))
    except ConnectionRefusedError:
        print('Error:  That host or port is not accepting connections.')
        sys.exit(1)

    # The connection was successful, so we can prep and send a registration message.

    print('Connection to server established. Sending intro message...\n')
    message = f'REGISTER {user} CHAT/1.0\n'
    client_socket.send(message.encode())

    # Receive the response from the server and start taking a look at it

    response_line = get_line_from_socket(client_socket).decode()
    response_list = response_line.split(' ')

    # If an error is returned from the server, we dump everything sent and
    # exit right away.

    if response_list[0] != '200':
        print('Error:  An error response was received from the server.  Details:\n')
        print(response_line)
        print('Exiting now ...')
        sys.exit(1)
    else:
        print('Registration successful.  Ready for messaging!')

    # Set up our selector.

    client_socket.setblocking(False)
    sel.register(client_socket, selectors.EVENT_READ, handle_message_from_server)
    sel.register(sys.stdin, selectors.EVENT_READ, handle_keyboard_input)

    # Prompt the user before beginning.

    do_prompt()

    # Now do the selection.

    while (True):
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)


if __name__ == '__main__':
    main()

# end of programs