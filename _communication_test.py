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
    #global log
    global leader_race
    global replied
    global ballot_num
    global to_prop_logs
    global DEBUG
    global log

    #log = []
    leader_race = False
    replied = False 
    ballot_num = (0, CLIENT_ID)
    to_prop_logs = []
    dprint(DEBUG, "(debugging) setting values to default at the end of paxos run")


def get_logs():
    # TODO: this function should go through each client and collect logs or timeout
    pass

def leader_communication(header, network_message, child_conn):
    global ballot_num
    global CLIENT_ID
    global index
    global CLIENTS


    # first send request to be a leader
    if header == "START":
        ballot_num = (ballot_num[0]+1, CLIENT_ID)
        prop_index = index + 1
        prop_ballot = ballot_num
        msg = pickle.dumps([prop_index, prop_ballot])
        msg = bytes(f"{'REQUEST':<{HEADERSIZE}}", 'utf-8') + msg
        for client in CLIENTS:
            send_to_client(msg, client)
        replied_bal = ballot_num


    elif header == "REPLY":
        Event().wait(2)

        if network_message[HEADERSIZE] == 0:
            # detect competing leaders and receive for 10 sec
            dprint(DEBUG, "(debugging) Received reply 0; setting leader_race = True")
            leader_race = True
            to_prop_logs = []
        
        else:
            # accepted as a leader
            dprint(DEBUG, "(debugging) Received reply 1; selected as leader; logs received from 1")
            to_prop_logs = log
            log_received = pickle.loads(network_message[HEADERSIZE+1:])
            to_prop_logs += log_received
            for i in range(len(CLIENTS)-1): # we already received one reply => -1
                # TODO: get_logs to collect logs from all clients
                pass
            
    elif header == "ACCEPTED":
        dprint(f"(debugging) Recieved accpted msg: {network_message[HEADERSIZE:]}", 'red')

        if network_message[HEADERSIZE] == 1:
            # received 1 accept -- move on to commit phase
            accepted_index = int(network_message[HEADERSIZE+1:])

            if accepted_index < len(bchain):
                    # bchain entry already committed
                        dprint(DEBUG, "(debugging) another accepted for same entry; ingore this accepted")

            else:
                dprint(DEBUG, "(debugging) received one accepted; committing bc entry and sending commit")
                entry = BC_entry(to_prop_logs)
                bchain.append(entry)
                index = len(bchain)
                msg = bytes(f"{'COMMIT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps(to_prop_logs)
                for client in CLIENTS:
                    send_to_client(msg, client)
                # take care of all other variables which should be set to default
                set_to_default()
                log = []
                clear_saved_log(PORT)   #TODO: this needs to be fixed
                replied_bal = (0, 0)
                dprint(DEBUG, "(debugging) checking pending transaction status")
                pend_trans_status = pending_trans_status()
                #pend_trans_status = False
                if pend_trans_status == False:
                # don't have enough balance; send failed transaction message
                    dprint(DEBUG, "(debugging) client transaction failed, not enough balance :(")
                    pending_trans = None
                    child_conn.send('0')
                else:
                    # push pending trans to log and send reply to client (can make function for this)  
                    if pending_trans == None:
                        dprint(DEBUG, "(debugging) Was pending transaction; still came here")
                    else:     
                        dprint(DEBUG, "(debugging) client transaction suceeded, pushing to logs")                 
                        receiver = pending_trans[0]
                        amount = pending_trans[1]
                        transaction = Node(PORT, receiver, amount)
                        log.append(transaction)
                        write_log_to_file(PORT, receiver, amount)
                        child_conn.send('1')
                        pending_trans = None


def client_communication(child_conn, arguments):
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

    PORT = arguments[0]
    CLIENTS = arguments[1]
    CLIENT_ID = arguments[2]
    DEBUG = arguments[3]
    CATCHUP = arguments[4]
    
    ballot_num = (0, CLIENT_ID)
    replied_bal = (0,0)

    client_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_listen.bind((HOSTNAME, PORT))
    client_listen.listen()
    
    while True:
        conn, addr = client_listen.accept()
        
        data = conn.recv(RECV_LENGTH)
        header = data[:HEADERSIZE].decode().strip()

        """

        This code handles everything that a client would respond to

        """
        if header == 'REQUEST':
            prop_index, prop_ballot = pickle.loads(data[HEADERSIZE:])
            dprint(DEBUG, f"(debugging) Heard request message from {prop_ballot[1]}")

            Event().wait(2)

            """
            So this comparision I am not sure if it works. What if index increases but the client_id doesn't?
            """
            if prop_ballot > replied_bal:
                # reply to proposed -- send log entries
                    replied_bal = prop_ballot
                    print(colored(f"(debugging) Sending reply: " + f"{'REPLY':<{HEADERSIZE}}" + "0", 'red'))
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + (1).to_bytes(1, 'little') + pickle.dumps(log)
                    send_to_client(msg, prop_ballot[1])
                    dprint(DEBUG, f"(debugging) Replied 1 to {prop_ballot[1]}; replied_ballot := {replied_bal}.")
                    continue
            else:
                # replied to higher ballot
                # ignore for now
                # TODO
                pass
                continue

        elif header == "ACCEPT":
            # check ballot with replied ballot and take decision on acceptance
            prop_ballot, to_prop_logs = pickle.loads(data[HEADERSIZE:])

            # currently not using to prop logs; but can use if decided to get rid of commit phase
            if prop_ballot == replied_bal:
                # move forward with this accept
                dprint(DEBUG, f"(debugging) Received accept from chosen leader -- reply with accept 1 and length of my bchain: {len(bchain)}")
                msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + (1).to_bytes(1, 'little') + bytes(str(len(bchain)), "utf-8")
                send_to_client(msg, prop_ballot[1])

                """

                Why are we removing the log here? Shouldn't we send the log to the leader?

                """
                log = []
                clear_saved_log(PORT) # TODO: this needs to be fixed

                # updating logs for non-leader
                continue

            elif replied_bal == (0,0):
                # came out of crash state (ignore the message --  can reply with 'ACCEPTED 0
                dprint(DEBUG, "(debugging) received accept message just after recovering from crash")
                continue # no need

            else:
                # leader race, replied to someone else
                """
                Here the leader might want to take a random break and sleep for a bit before sending a leader request again with higher ballot
                """
                dprint(DEBUG, "(debugging) got accept message from previous leader; informing about the new game in the town")
                msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + (0).to_bytes(1, 'little')
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
                replied_bal = (0, 0)
                continue
        

        # leader code 

        elif header == "REPLY":
            leader_communication(header, data, child_conn)
            pass

        elif header == "ACCEPTED":
            leader_communication(header, data, child_conn)
            pass