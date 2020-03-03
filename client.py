import socket
import pickle
import argparse
import threading
from termcolor import colored
from linkedlist import Node, calculateBalance, printList, BlockChainNode
from paxos import *

# check for valid command line arguments
parser = argparse.ArgumentParser(description='Blockchain Client')
parser.add_argument('--port' ,nargs=1, type=int, required=True, help="Port number for the client")
args = parser.parse_args()

# the pid will serve as the client ID/PID
HOSTNAME    = socket.gethostname()
PORT        = (args.port)[0]
HEADERSIZE  = 7
CLIENTS     = [9001,9002,9003]
CLIENT_ID   = PORT - 9000 - 1
INIT_BAL    = 10
CLIENTS.remove(PORT) #removing the current clients port
RECV_SIZE   = 1024

# globals
lock1       = threading.Lock()
lock2       = threading.Lock()
log         = []
bchain      = []
threads     = []

# paxos globals
INDEX       = 0
BALLOT_NUM  = 0
LEADER_FLAG = False

def create_transactions():
    global bchain
    global log

    
    while True:
        print(colored(f"\n\n(alert) This client ID is {PORT}.", 'cyan'))
        print("What type of transaction do you want to issue?\n\t1. Transfer\n\t2. Balance")
        option = int(input())
        if option == 1:
            # this option deals with input for new transaction
            print("Enter the Reciever ID: ")
            reciever = int(input())
            print("Enter the amount you wish to send: ")
            amount = float(input())
            print(colored(f"(message) You {PORT} are sending {amount} to {reciever}.", 'yellow'))
            if calculateBalance(bchain, log, INIT_BAL, PORT) >= amount:
                transaction = Node(PORT, reciever, amount)
                log.append(transaction)
                print(colored("(response) SUCCESS", 'green'))
            else:
                # TODO: add the paxos call and check balance again and then either continue or send INCORRECT
                start_leader_election(INDEX, BALLOT_NUM)
                if calculateBalance(bchain, log, INIT_BAL, PORT) >= amount:
                    log.append(transaction)
                    print(colored("(response) SUCCESS", 'green'))
                else:
                    print(colored("(response) INCORRECT", 'red'))
        elif option == 2:
            # this should be simple since there is no need to check or make any request to other clients
            print(colored(f"(message) Checking balance for {PORT}.", 'yellow'))
            balance = calculateBalance(bchain, log, INIT_BAL, PORT)
            print(colored(f"(response) The balance is: ${balance}.", 'green'))
            for client in CLIENTS:
                balance = calculateBalance(bchain, log, INIT_BAL, client)
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


def create_paxos_message():
    global INDEX
    """
    This function will create the initial message that needs to be sent to start paxos.
    Things to check:
        1. All items in log are not in bchain
        2. What would be the header? Does it need to know which client sent it? And what other contents?
    """
    # make the header
    msg = bytes(f"{'REQ':<{HEADERSIZE}}", "utf-8")

    # assume everything within local log is def not in blockchain
    msg += pickle.dumps(BlockChainNode(INDEX, log))
    return msg


def play_catchup():
    global INDEX
    """
    1. send message to everyone with header CAT
    2. listen and if they respond with CATACK update:
        * with max(len(bchain)) from either clients
        * done
    """
    msg = bytes(f"{'CAT':<{HEADERSIZE}}", "utf-8")
    t1 = threading.Thread(name="Catchup the blockchain", target=send_to_clients, args=(msg,))
    t1.start()

    # cleanup
    t1.join()


def handle_client_response(conn):
    global bchain
    global log
    global INDEX
    global BALLOT_NUM

    try:
        data = conn.recv(RECV_SIZE)
        header = data[:HEADERSIZE]
        header = header.decode().lstrip().rstrip()
        print(colored(f"The header is {header}.", "yellow"))
        msg = pickle.loads(data[HEADERSIZE:])

        if header == "CAT":
            msg = bytes(f"{'CATACK':<{HEADERSIZE}}", "utf-8") + pickle.dumps(bchain)
            conn.send(msg)
        elif header == "CATACK":
            if len(bchain) < len(msg):
                bchain = msg
            else:
                print(f"Recieved bchain is shorter.", "yellow")


        # paxos headers
        elif header == "REQ":
            handle_request(msg, LEADER_FLAG, INDEX, BALLOT_NUM, log, bchain)

        elif header == "REP" and msg.accept_val:
            INDEX += 1
            BALLOT_NUM += 1
            start_leader_election(INDEX, BALLOT_NUM)
        elif header == "REP" and (not msg.accept_val) and log:
            log += log
            # start the next phase


    except:
        print(f"Error handling client response", "red")



def send_to_clients(msg, client_id = 0):
    global CLIENTS
    
    print(colored(f"(message) Sending message.", 'yellow'))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # sending the sync message to client_id
        # TODO: reply back to other clients during paxos run
        if client_id == 0:
            for client in CLIENTS:
                send_to_clients(msg, client)
        else:
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
        t1 = threading.Thread(name="Handle client requests & responses", target=handle_client_response, args=(conn,))
        t1.start()

        # cleanup
        t1.join()

    client_listen.close()


if __name__ == '__main__':
    print(colored(f"(alert) Starting client with ID: {PORT}.", 'blue'))
    p = threading.Thread(name='Listen to Clients', target=listen_to_clients, args=())
    p.daemon = True     # this does not need to be daemon here 
    p.start()

    # init catchup
    play_catchup()
    INDEX = len(bchain)

    create_transactions()

    # cleanup
    p.join()
