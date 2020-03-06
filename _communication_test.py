import socket
import pickle
from time import sleep
from threading import Event
from termcolor import colored
from helpers import *


# globals
HOSTNAME       = 'localhost'
HEADERSIZE     = 8
INIT_BAL       = 10
log            = []
bchain         = []
RECV_LENGTH    = 2000
CLIENT_ID      = None
CLIENTS        = None
PORT           = None
DEBUG          = False

# paxos globals
index         = 0               # (should always be number committed entries in my blockchain -- will be initialized at zero
ballot_num    = None            # (useful for election and accepting a value) -- initialized at None, updated while sending request message and after receiving request message
leader_race   = False           # (true if we detect race; then we sleep for random time)
pending_trans = None            # (used in competing leader situation when received client request but somebody else is leader for this paxos run)
replied       = False           # (Flag to check if replied to someone or not)
to_prop_logs  = []              # used only when chosen as leader -- safety variable in case of leader race
replied_bal   = (0,0)
count = 0


# this function serves as a init function to send request message to clients
def send_request_messages():
    global ballot_num
    global CLIENT_ID
    global index
    global CLIENTS

    ballot_num = (ballot_num[0]+1, CLIENT_ID)
    prop_index = index + 1
    prop_ballot = ballot_num
    msg = pickle.dumps([prop_index, prop_ballot])
    msg = bytes(f"{'REQUEST':<{HEADERSIZE}}", 'utf-8') + msg
    for client in CLIENTS:
        send_to_client(msg, client)
    replied_bal = ballot_num
    return



def set_to_default():
    global log
    global leader_race
    global replied
    global ballot_num
    global to_prop_logs
    global DEBUG
    global replied_bal
    global count

    log = []
    leader_race = False
    replied = False 
    ballot_num = (0, CLIENT_ID)
    to_prop_logs = []
    replied_bal = (0, 0)
    count = 0
    dprint(DEBUG, "(debugging) setting values to default at the end of paxos run")


def get_logs():
    # TODO: this function should go through each client and collect logs or timeout
    pass

def leader_communication(header, network_message, child_conn, client_listen):
    global ballot_num
    global CLIENT_ID
    global index
    global CLIENTS
    global replied_bal
    global to_prop_logs
    global bchain
    global log
    global DEBUG
    global count


    # first send request to be a leader
    if header == "START":
        ballot_num = (ballot_num[0]+1, CLIENT_ID)
        prop_ballot = ballot_num
        msg = MessageFromat(ballot_num)
        replied_bal = ballot_num
        msg = bytes(f"{'REQUEST':<{HEADERSIZE}}", 'utf-8') + pickle.dumps(msg)
        for client in CLIENTS:
            send_to_client(msg, client)
        send_to_client(msg, PORT)


    elif header == "REPLY":
        Event().wait(2)
        # accepted as a leader
        dprint(DEBUG, "(debugging) Received reply 1; selected as leader; logs received from 1")
        # to_prop_logs = log
        log_received = pickle.loads(network_message[HEADERSIZE:])
        to_prop_logs += log_received
        count += 1
        
        # check for len or timeout
        for i in range(2):
            try:
                client_listen.settimeout(3)
                client_listen.listen(1)
                conn, addr = client_listen.accept()
            except socket.timeout:
                pass
            else:
                log_received = pickle.loads(network_message[HEADERSIZE:])
                dprint(DEBUG, f"(debugging) Adding log {log_received} to proposed logs.")
                for recv_log in log_received:
                    if recv_log not in to_prop_logs:
                        to_prop_logs.append(recv_log)
                dprint(DEBUG, f"(debugging) Total log size now is {len(to_prop_logs)}.")
                count += 1
        
        if count >= len(CLIENTS):
            msg = bytes(f"{'ACCEPT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps(MessageFromat(ballot_num))
            for client in CLIENTS:
                send_to_client(msg, client)
            send_to_client(msg, PORT)

        dprint(DEBUG, f"(debugging) Pending Transaction is {pending_trans}.")
        if pending_trans is not None and len(pending_trans) == 2:
            if calculateBalance(bchain, INIT_BAL, PORT) >= pending_trans[1]:
                transaction = Node(PORT, pending_trans[0], pending_trans[1])
                log.append(transaction)
                child_conn.send("1")
            else:
                child_conn.send("0")

        dprint(DEBUG, f"(debugging) Received logs from {count} clients")



            
    elif header == "ACCEPTED":
        dprint(DEBUG, f"(debugging) Recieved accpted msg: {network_message[HEADERSIZE:]}", 'red')
        # moving on to commit phase
        entry = BC_entry(to_prop_logs)
        bchain.append(entry)
        index = len(bchain)

        msg = bytes(f"{'COMMIT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps(entry)
        for client in CLIENTS:
            send_to_client(msg, client)
        
        set_to_default()
        clear_saved_log(PORT)


    elif header == "NO":
        print(colored("(message) Leader race. Aborting...", 'red'))
        child_conn.send("2")

def follower_communication(child_conn, arguments):
    global HOSTNAME
    global HEADERSIZE
    global INIT_BAL
    global log
    global bchain
    global RECV_LENGTH
    global index
    global replied
    global leader_race
    global pending_trans
    global ballot_num
    global to_prop_logs
    global CLIENT_ID
    global CLIENTS
    global PORT
    global DEBUG
    global replied_bal

    PORT = arguments[0]
    CLIENTS = arguments[1]
    CLIENT_ID = arguments[2]
    DEBUG = arguments[3]
    CATCHUP = arguments[4]
    
    ballot_num = (0, CLIENT_ID)
    replied_bal = (0,0)

    client_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_listen.bind((HOSTNAME, PORT))
    
    while True:
        try:
            client_listen.settimeout(1)
            client_listen.listen()
            conn, addr = client_listen.accept()
            data = conn.recv(RECV_LENGTH)
            header = data[:HEADERSIZE].decode().strip()
        except socket.timeout:
            if child_conn.poll():
                request = child_conn.recv()
                if request[0] == '2': # balance
                    dprint(DEBUG, "(debugging) Received balance request from client")
                    balances = balance(PORT, CLIENTS, bchain, log)
                    child_conn.send(pickle.dumps(balances))
                    dprint(DEBUG, "(debugging) Sent balances to parent")
                
                elif request[0] == '3': # print log
                    dprint(DEBUG, "(debugging) Received print log request")
                    child_conn.send(pickle.dumps(log))
                    dprint(DEBUG, "(debugging) Sent logs to parent")

                elif request[0] == '4': # print Blockchain
                    dprint(DEBUG, "(debugging) Received print bchain request")
                    child_conn.send(pickle.dumps(bchain))
                    dprint(DEBUG, "(debugging) Sent bchain to parent")

                elif request[0] == '1': # transfer
                    dprint(DEBUG, "(debugging) Received transfer request from client")
                    list_request = list(map(int, request.strip().split()))
                    receiver = list_request[1]
                    amount = list_request[2]
                    all_trans = all_transactions(bchain, log)
                    if calculateBalance(all_trans, INIT_BAL, PORT) >= amount: 
                        transaction = Node(PORT, receiver, amount)
                        log.append(transaction)
                        write_log_to_file(PORT, receiver, amount)
                        child_conn.send('1') # success
                        dprint(DEBUG, "(debugging) Client has enough balance -- Transaction added to the logs")

                    else:
                        # need to initiate paxos run    
                        dprint(DEBUG, "(debugging) Cliet doesn't have enough balance; need to start paxos run")
                        msg = bytes(f"{'START':<{HEADERSIZE}}", 'utf-8')
                        send_to_client(msg, PORT)
                        pending_trans = [receiver, amount]

        # This code handles everything that a client would respond to
        else:
            if header == 'REQUEST':
                prop_ballot = (pickle.loads(data[HEADERSIZE:])).ballot
                dprint(DEBUG, f"(debugging) Heard request message from {prop_ballot[1]}")

                Event().wait(2)

                """
                So this comparision I am not sure if it works. What if index increases but the client_id doesn't?
                """

                if prop_ballot >= replied_bal:
                    # reply to proposed -- send log entries
                    replied_bal = prop_ballot
                    dprint(DEBUG, f"(debugging) Sending reply: {'REPLY':<{HEADERSIZE}}")
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + pickle.dumps(log)
                    send_to_client(msg, prop_ballot[1])
                    dprint(DEBUG, f"(debugging) Replied to {prop_ballot[1]}; replied_ballot := {replied_bal}.")
                    continue
                else:
                    # replied to higher ballot -- reply no
                    dprint(DEBUG, "(debugging) Already replied to a higher ballot. Leader race. Sending abort.", 'red')
                    msg = bytes(f"{'NO':<{HEADERSIZE}}", 'utf-8')
                    send_to_client(msg, prop_ballot[1])
                    continue

            elif header == "ACCEPT":
                # check ballot with replied ballot and take decision on acceptance
                prop_ballot = (pickle.loads(data[HEADERSIZE:])).ballot

                # currently not using to prop logs; but can use if decided to get rid of commit phase
                if prop_ballot == replied_bal:
                    # move forward with this accept
                    dprint(DEBUG, f"(debugging) Received accept from chosen leader -- length of my bchain: {len(bchain)}")
                    msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + bytes(str(len(bchain)), "utf-8")
                    send_to_client(msg, prop_ballot[1])
                    # since the log has been already sent in prev phase, we send length of bchain
                    # and remove the transactions from our local log 
                    log = []
                    clear_saved_log(PORT)
                    continue

                elif replied_bal == (0,0):
                    # came out of crash state (ignore the message --  can reply with 'ACCEPTED 0
                    dprint(DEBUG, "(debugging) received accept message just after recovering from crash")
                    # TODO: maybe run catchup
                    continue # no need

                else:
                    # replied to higher ballot -- reply no
                    dprint(DEBUG, "(debugging) Already replied to a higher ballot. Leader race. Sending abort.", 'red')
                    msg = bytes(f"{'NO':<{HEADERSIZE}}", 'utf-8')
                    send_to_client(msg, prop_ballot[1])
                    continue

            elif header == "COMMIT":
                dprint(DEBUG, "(debugging) received COMMIT message; adding to bchain irrespective of my participation in this run")
                # can remove this phase in next itearation, everyone sends to everyone when accepted
                new_bc_entry = pickle.loads(data[HEADERSIZE:])
                entry = BC_entry(new_bc_entry)
                bchain.append(entry)
                index = len(bchain)
                # take care of variables which needs to be set to default
                set_to_default()
                continue
            

            # leader code 

            elif header == "START":
                leader_communication(header, data, child_conn, client_listen)
                continue

            elif header == "REPLY":
                leader_communication(header, data, child_conn, client_listen)
                continue

            elif header == "ACCEPTED":
                leader_communication(header, data, child_conn, client_listen)
                continue

            elif header == "NO":
                leader_communication(header, data, child_conn, client_listen)
                continue