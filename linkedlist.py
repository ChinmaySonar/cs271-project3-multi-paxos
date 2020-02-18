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