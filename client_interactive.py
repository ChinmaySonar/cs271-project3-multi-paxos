import socket
import pickle
import argparse
import threading
from multiprocessing import Process, Pipe
from time import sleep
from termcolor import colored
from linkedlist_and_helpers import *
from communication import *



# check for valid command line arguments
parser = argparse.ArgumentParser(description='Blockchain Client')
parser.add_argument('--port' ,nargs=1, type=int, required=True, help="Port number for the client")
args = parser.parse_args()

# the pid will serve as the client ID/PID
HOSTNAME    = 'localhost'
PORT        = (args.port)[0]
HEADERSIZE  = 8
CLIENTS     = [9001,9002,9003]
CLIENT_ID   = PORT
INIT_BAL    = 10
CLIENTS.remove(PORT) #removing the current clients port

# wait for response from child
def get_response(parent_conn):
    while True:
        if parent_conn.poll():
            response = parent_conn.recv()
            return response
        else:
            continue

def print_log(logs):
    i = 1
    for transaction in logs:
        print(colored(f"Transaction number {i}.",'cyan'))
        print(colored(f"Sender: {transaction.sender}",'yellow'))
        print(colored(f"Receiver: {transaction.receiver}", 'yellow'))
        print(colored(f"Amount: {transaction.amount}", 'yellow'))
        print("")
        i += 1

# main function seeking client requests
def create_transaction(parent_conn):
        
    while True:
        print(colored(f"\n\n(alert) This client ID is {PORT}.", 'cyan'))
        print("What type of transaction do you want to issue?\n\t1. Transfer\n\t2. Balance\n\t3. Print Log\n\t4. Print Blockchain")
        option = int(input())
        if option == 1:
            # this option deals with input for new transaction
            print("Enter the Reciever ID: ")
            receiver = int(input())
            print("Enter the amount you wish to send: ")
            amount = int(input()) # for now we can only send integer money
            print(colored(f"(message) You {PORT} are sending {amount} to {receiver}.", 'yellow'))
            
            request = '1' + " " + str(receiver) + " " + str(amount)
            parent_conn.send(request)
            response = get_response(parent_conn)
            if response[0] == '1':
                print(colored("(response) SUCCESS", 'green'))
            else:
                print(colored("(response) INCORRECT", 'red'))
            
        elif option == 2:
            # prints estimated balance from local bchain+log for each client
            print(colored(f"(message) Checking balance for {PORT}.", 'yellow'))
            request = '2'
            parent_conn.send(request)
            response = get_response(parent_conn)
            response = pickle.loads(response)
            for client in response:
                print(colored(f"(response) Balance for port {client[1]} is {client[0]}.",'yellow'))
        elif option == 3:
            # this option handles the printing of log
            print(colored("(message) Printing local log.", 'yellow'))
            parent_conn.send('3')
            response = get_response(parent_conn)
            log = pickle.loads(response)
            print(f"(debugging) {log}")
            print_log(log)
    
        elif option == 4:
            # this option handles the printing of bchain
            print(colored("(message) Printing commited blockchain.", 'yellow'))
            parent_conn.send('4')
            response = get_response(parent_conn)
            bchain = pickle.loads(response)
            j = 0
            for entry in bchain:
                print(colored(f"Index in blockchain: {j}", 'black'))            
                print_log(entry.entry)
                j += 1
        else:
            print(colored("(response) Incorrect transaction type.", 'red'))


# parent and child process
parent_conn, child_conn = Pipe()

arguments = [PORT, CLIENTS, CLIENT_ID]
network_communication = Process(target = communication, args=(child_conn, arguments,))
network_communication.start()

# to play catch-up
print(colored("(message) Catching-up with other clients (10 sec sleep).",'yellow'))
sleep(10) 

create_transaction(parent_conn)

# check if we can do this given we want to handle failures..
network_communication.join()

