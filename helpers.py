from termcolor import colored
import pickle
import socket
import os, sys

#globals
INIT_BAL = 10
RECV_LENGTH = 2000
HOSTNAME = 'localhost'

# Node class to handle transactions
class Node: 

    # Function to initialise the node object 
    def __init__(self, sender, receiver, amount): 
        self.sender = sender
        self.receiver = receiver
        self.amount = amount


# function to calculate balance given a PID
def calculateBalance(arr, INIT_BAL, PID):
    final_bal = INIT_BAL
    for item in arr:
        if PID == item.sender:
            final_bal -= item.amount
        elif PID == item.receiver:
            final_bal += item.amount
    return final_bal


# function to print whatever list is given
def printList(list):
    try:
        if not list:
            print(colored("List is empty.", 'yellow'))
        else:
            for item in range(len(list)):
                print(colored(f"Sender: {item.sender}, Reciever: {item.reciever}, Amount: {item.amount}.", 'yellow'))
    except:
        print(colored("Error printing list.", 'yellow'))


def print_log(logs):
    i = 1
    for transaction in logs:
        print(colored(f"Transaction number {i}.",'cyan'))
        print(colored(f"Sender: {transaction.sender}",'yellow'))
        print(colored(f"Receiver: {transaction.receiver}", 'yellow'))
        print(colored(f"Amount: {transaction.amount}", 'yellow'))
        print("")
        i += 1


# each entry in blockchain is list of nodes
# bc_entry is a list of nodes
class BC_entry:
    
    def __init__(self, bc_entry):
        self.entry = bc_entry



## helper functions
# returns all transaction in bchain + log as a list
def all_transactions(bchain, log=[]):
    all_trans = []
    for i in bchain:
        all_trans += i.entry
    all_trans += log
    return all_trans


# return list of balances of PORT + CLIENTS in same order as given
def balance(PORT, CLIENTS, bchain, log):
    all_trans = all_transactions(bchain, log)
    balances = []
    t = calculateBalance(all_trans, INIT_BAL, PORT)
    balances.append((t,PORT))
    for client in CLIENTS:
        t = calculateBalance(all_trans, INIT_BAL, client)
        balances.append((t, client))
    return balances


# send message and get reply for catch-up phase
def send_catch_up(msg, client):
    print(colored(f"(message) sending {msg} to {client}.",'yellow'))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:    
        s.connect((HOSTNAME, client))
        s.send(msg)
        response = s.recv(RECV_LENGTH)
        s.close()
        return response
    except:
        print(colored(f"(message) Client on port {client} is offline.", 'yellow'))
        return ''


# send message msg to client
def send_to_client(msg, client):
    print(colored(f"(message) sending {msg} to {client}.",'yellow'))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:    
        s.connect((HOSTNAME, client))
        s.send(msg)
        s.close()
    except:
        print(colored(f"(message) Client on port {client} is offline.", 'yellow'))

# print function to control printing debugging messages
# the msg should always have prefix "(debugging) *"
def dprint(debug=False, msg="", color='blue'):
    if not debug:
        _original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    else:
        print(colored(msg, color))