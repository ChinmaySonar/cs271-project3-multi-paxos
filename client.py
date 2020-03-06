import socket
import pickle
import argparse
from multiprocessing import Process, Pipe
from time import sleep
from termcolor import colored
from helpers import *
from _communication_test import *
import os


# check for valid command line arguments
parser = argparse.ArgumentParser(description='Blockchain Client')
parser.add_argument('--port' , '-p', nargs=1, type=int, required=True, help="Port number for the client")
parser.add_argument('--debug', '-d', action='store_true', default=False, help="Set the flag to enable debug statements")
parser.add_argument('--catchup', '-c', action='store_false', default=True, help="Disable catch-up")
parser.add_argument('--beertime', '-b', action='store_true', default=False, help="Beer time")
args = parser.parse_args()

# the pid will serve as the client ID/PID
HOSTNAME    = 'localhost'
PORT        = (args.port)[0]
DEBUG       = (args.debug)
CATCHUP     = (args.catchup)
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


# beer time handling
def beer_time(late_call=False):
    # show a kiss face
    if (args.beertime):
        print("\U0001F618")

    if (args.beertime) and os.name == 'posix':
        os.system('say "Beer Time"')
    elif (args.beertime) and os.name == 'Linux':
        os.system('spd-say "Beer Time"')
    elif (args.beertime):
        print(colored("(important) Go get a beer, and a better OS.", 'red'))

    if (args.beertime) and not late_call:
        sys.exit()



# main function seeking client requests
def create_transaction(parent_conn):
        
    while True:
        print(colored(f"\n\n(alert) This client ID is {PORT}. Client PID is {os.getpid()}.", 'cyan'))
        print("What type of transaction do you want to issue?\n\t1. Transfer\n\t2. Balance\n\t3. Print Log\n\t4. Print Blockchain\n\t5. Clear log")
        option = int(input())
        if option == 1:
            # this option deals with input for new transaction
            print("Enter the Reciever ID: ")
            receiver = int(input())
            if receiver in CLIENTS:
                print("Enter the amount you wish to send: ")
                amount = int(input()) # for now we can only send integer money
                print(colored(f"(message) You {PORT} are sending {amount} to {receiver}.", 'yellow'))
                request = '1' + " " + str(receiver) + " " + str(amount)
                parent_conn.send(request)
                response = get_response(parent_conn)
                if response[0] == '1':
                    print(colored("(response) SUCCESS", 'green'))
                elif response[0] == '2':
                    print(colored("(response) LEADER ERROR", 'red'))
                else:
                    print(colored("(response) INCORRECT", 'red'))
            else:
                print(colored(f"(message) Client {receiver} is not a valid.", "yellow"))
                
            
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
            print(colored("(message) -----------------------------", 'yellow'))
            parent_conn.send('3')
            response = get_response(parent_conn)
            log = pickle.loads(response)
            dprint(DEBUG, f"(debugging) {log}")
            print_log(log)
            print(colored("(message) -----------------------------", 'yellow'))
    

        elif option == 4:
            # this option handles the printing of bchain
            print(colored("(message) Printing commited blockchain.", 'yellow'))
            print(colored("(message) -----------------------------", 'yellow'))
            parent_conn.send('4')
            response = get_response(parent_conn)
            bchain = pickle.loads(response)
            j = 0
            for entry in bchain:
                print(colored(f"Index in blockchain: {j}", 'yellow'))            
                print_log(entry.entry)
                j += 1
            print(colored("(message) -----------------------------", 'yellow'))

        elif option == 5:
            # this option deletes the local log on disk
            print(colored("(message) Deleting local log for client {PORT}", 'yellow'))
            clear_saved_log(PORT)

        elif option == 6:
            # this option handles someone needing a beer in the middle -- hidden option
            args.beertime = True
            beer_time(True)


        else:
            print(colored("(response) Incorrect transaction type.", 'red'))


if __name__ == '__main__':
    # parent and child process
    parent_conn, child_conn = Pipe()

    # call beer time intially if set
    beer_time()

    # add arguments here whenever you need to pass to the communication
    arguments = [PORT, CLIENTS, CLIENT_ID, DEBUG, CATCHUP]
    network_communication = Process(target=follower_communication, args=(child_conn, arguments,))
    network_communication.start()

    # to play catch-up
    if CATCHUP:
        print(colored("(message) Catching-up with other clients (10 sec sleep).",'yellow'))
        sleep(3)
    else:
        print(colored("(message) Catch-up was disabled. Enable it by removing '-c' flag."))

    create_transaction(parent_conn)

    # check if we can do this given we want to handle failures..
    network_communication.join()

