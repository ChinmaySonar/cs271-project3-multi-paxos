import socket
import pickle
import argparse
import threading
from termcolor import colored
from linkedlist import Node, SyncMsg, calculateBalance

# check for valid command line arguments
parser = argparse.ArgumentParser(description='Blockchain Client')
parser.add_argument('--port' ,nargs=1, type=int, required=True, help="Port number for the client")
args = parser.parse_args()

# the pid will serve as the client ID/PID
HOSTNAME    = socket.gethostname()
PORT        = (args.port)[0]
HEADERSIZE  = 2
CLIENTS     = [9001,9002,9003]
CLIENT_ID   = PORT - 9000 - 1
INIT_BAL    = 10
CLIENTS.remove(PORT) #removing the current clients port

# globals
lock1       = threading.Lock()
lock2       = threading.Lock()
bchain      = []

def create_transactions():
    global bchain
    while True:
        print(bchain)
        print(colored(f"\n\n(alert) This client ID is {PORT}.", 'cyan'))
        print("What type of transaction do you want to issue?\n\t1. Transfer\n\t2. Balance")
        option = int(input())
        if option == 1:
            # update the clock for each transaction
            print("Enter the Reciever ID: ")
            reciever = int(input())
            print("Enter the amount you wish to send: ")
            amount = float(input())
            print(colored(f"(message) You {PORT} are sending {amount} to {reciever}.", 'yellow'))
            if calculateBalance(bchain, INIT_BAL, PORT) >= amount:
                transaction = Node(PORT, reciever, amount)
                bchain.append(transaction)
                print(colored("(response) SUCCESS", 'green'))
            else:
                print(colored("(response) INCORRECT", 'red'))
        elif option == 2:
            # this should be simple since there is no need to check or make any request to other clients
            print(colored(f"(message) Checking balance for {PORT}.", 'yellow'))
            balance = calculateBalance(bchain, INIT_BAL, PORT)
            print(colored(f"(response) The balance is: ${balance}.", 'green'))
            for client in CLIENTS:
                balance = calculateBalance(bchain, INIT_BAL, client)
                print(colored(f"(response) The estimated balance for {client} is: ${balance}.", 'green'))
        else:
            print(colored("Incorrect transaction type.", 'yellow'))


def send_to_clients(msg, client_id):
    global CLIENTS
    
    print(colored(f"(message) Sync timetable and transactions.", 'yellow'))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # sending the sync message to client_id
        s.connect((HOSTNAME, client_id))
        s.send(msg)
        s.close()
    except:
        print(colored(f"(message) Client on port {client_id} is offline.", 'yellow'))
    


def listen_to_clients():
    client_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_listen.bind((HOSTNAME, PORT))
    client_listen.listen()
    while True:
        print(colored("(alert) Waiting for connections.", 'cyan'))
        conn, addr = client_listen.accept()
        print(colored(f"(message) Sync message recieved.", 'yellow'))
        update_thread = threading.Thread(name="Sync Message Thread", target=process_clients_sync, args=(conn, addr))
        update_thread.start()
        update_thread.join()
    client_listen.close()


if __name__ == '__main__':
    print(colored(f"(alert) Starting client with ID: {PORT}.", 'blue'))
    p = threading.Thread(name='Listen to Clients', target=listen_to_clients, args=())
    p.daemon = True
    p.start()
    create_transactions()

    # cleanup
    p.join()