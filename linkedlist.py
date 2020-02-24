from termcolor import colored

# Node class to handle transactions
class Node: 

    # Function to initialise the node object 
    def __init__(self, sender, reciever, amount): 
        self.sender = sender
        self.reciever = reciever
        self.amount = amount

# function to calculate balance given a PID
def calculateBalance(arr, INIT_BAL, PID):
    final_bal = INIT_BAL
    for item in arr:
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