from termcolor import colored

# Node class to handle transactions
class Node: 

    # Function to initialise the node object 
    def __init__(self, sender, reciever, amount): 
        self.sender = sender
        self.reciever = reciever
        self.amount = amount

class BlockChainNode:

    def __init__(self, index, log):
        self.index = index
        self.log = log

class PaxosMessage:

    def __init__(self, index, ballot_num, accept_val=[], log=[]):
        self.index = index
        self.ballot_num = ballot_num
        self.accept_val = accept_val
        self.log = log  # this is value that we are proposing


# function to calculate balance given a PID
def calculateBalance(bchain, log, INIT_BAL, PID):
    final_bal = INIT_BAL
    # check for transactions in each bchain entry
    for entry in bchain:
        for item in entry:
            if PID == item.sender:
                final_bal -= item.amount
            elif PID == item.reciever:
                final_bal += item.amount
    # check for transactions in local log
    for item in log:
        if PID == item.sender:
            final_bal -= item.amount
        elif PID == item.reciever:
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