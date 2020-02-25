import socket
import pickle
import random
import argparse
import threading
from termcolor import colored
from linkedlist import Node, calculateBalance, printList


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
log         = []
bchain      = []

# paxos globals
index       = #(should always be number committed entries in my blockchain)
ballot_num  = #(useful for election and accepting a value)
accept_num  = #(index of last accepted blockchain object)
accept_val  = #(last accepted blockchain object)
state       = #(leader or not)
replies     = #(replies to check majority in any phase of paxos)
leader_race = #(true if we detect race; then we sleep for random time)

def create_transactions():
    global bchain
    global log

    
    while True:
        print(colored(f"\n\n(alert) This client ID is {PORT}.", 'cyan'))
        print("What type of transaction do you want to issue?\n\t1. Transfer\n\t2. Balance\n\t3. Print Log\n\t4. Print Blockchain")
        option = int(input())
        if option == 1:
            # this option deals with input for new transaction
            print("Enter the Reciever ID: ")
            reciever = int(input())
            print("Enter the amount you wish to send: ")
            amount = float(input())
            print(colored(f"(message) You {PORT} are sending {amount} to {reciever}.", 'yellow'))
            if calculateBalance(bchain+log, INIT_BAL, PORT) >= amount:
                transaction = Node(PORT, reciever, amount)
                log.append(transaction)
                print(colored("(response) SUCCESS", 'green'))
            else:
                # TODO: add the paxos call and check balance again and then either continue or send INCORRECT
                bchain, tran_status = paxos_election(PORT, log, bchain) # updated blockchain and flag about status of last transaction
                log = []
                if tran_status == True: 
                    print(colored("(response) SUCCESS", 'green'))
                else: 
                    print(colored("(response) INCORRECT", 'red'))
        elif option == 2:
            # this should be simple since there is no need to check or make any request to other clients
            print(colored(f"(message) Checking balance for {PORT}.", 'yellow'))
            balance = calculateBalance(bchain+log, INIT_BAL, PORT)
            print(colored(f"(response) The balance is: ${balance}.", 'green'))
            for client in CLIENTS:
                balance = calculateBalance(bchain+log, INIT_BAL, client)
                print(colored(f"(response) The estimated balance for {client} is: ${balance}.", 'green'))
        elif option == 3:
            # this option handles the printing of log
            print(colored("Printing local log.", 'yellow'))
            printList(log)
        elif option == 4:
            # this option handles the printing of bchain
            print(colored("Printing commited blockchain.", 'yellow'))
            printList(bchain)
        else:
            print(colored("Incorrect transaction type.", 'yellow'))


def send_to_clients(msg, client_id):
    global CLIENTS
    
    print(colored(f"(message) Sync timetable and transactions.", 'yellow'))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # sending the sync message to client_id
        # TODO: reply back to other clients during paxos run
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
        print(colored(f"(message) Some message recieved.", 'yellow'))
        # TODO: finish this logic for paxos majority from leader here
    client_listen.close()


if __name__ == '__main__':
    print(colored(f"(alert) Starting client with ID: {PORT}.", 'blue'))
    p = threading.Thread(name='Listen to Clients', target=listen_to_clients, args=())
    p.daemon = True     # this does not need to be daemon here 
    p.start()
    create_transactions()

    # cleanup
    p.join()
