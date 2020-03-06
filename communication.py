import socket
import pickle
from time import sleep
from termcolor import colored
from helpers import *


# globals
HOSTNAME       = 'localhost'
HEADERSIZE     = 8
INIT_BAL       = 10
log            = []
bchain         = []
RECV_LENGTH    = 10000
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


# helper functions (first 4)
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

def get_logs(client_listen):
    global to_prop_logs
    global leader_race
    
    try:
        client_listen.settimeout(1.5)
        client_listen.listen(1)
        connection, client_address = client_listen.accept()
    except socket.timeout:
        pass
        return
    else:
        dprint(DEBUG, "(debugging) logs received from {client_address}")
        network_message = connection.recv(RECV_LENGTH)
        connection.close()
        if network_message[-1] == 54:
            # detect competing leaders and receive for 10 sec
            dprint(DEBUG, "(debugging) detected leader race during reply phase", 'cyan')
            leader_race = True
            to_prop_logs = []
            return
        else:
            dprint(DEBUG, "(debugging) logs appended to to_prop_logs")
            received_logs = pickle.loads(network_message[HEADERSIZE:])
            to_prop_logs += received_logs

def set_to_default():
    #global log
    global leader_race
    global replied
    global ballot_num
    global to_prop_logs
    global DEBUG

    #log = []
    leader_race = False
    replied = False 
    ballot_num = (0, CLIENT_ID)
    to_prop_logs = []
    dprint(DEBUG, "(debugging) setting values to default at the end of paxos run")

def pending_trans_status():
    global pending_trans
    global bchain
    global PORT
    global DEBUG

    if pending_trans is None:
        dprint(DEBUG, "(debugging) Did not have pending transaction")
        return True
    receiver = pending_trans[0]
    amount = pending_trans[1]
    all_trans = all_transactions(bchain)
    if calculateBalance(all_trans, INIT_BAL, PORT) >= amount:
        dprint(DEBUG, "(debugging) Had pending transaction and enough balance")
        return True
    return False


def catchup_log():
    global log
    global PORT

    try:
        log = read_log_from_file(PORT)
    except:
        print(colored(f"(message) Error catching up log from file.", 'yellow'))


# main communication function
def communication(child_conn, arguments):
   
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
    
    if CATCHUP:
        # play catch-up (can make separate function to do this)
        print(colored("(message) Catching-up with others in the network", 'yellow'))
        msg = bytes(f"{'CATCH-UP':<{HEADERSIZE}}", 'utf-8')
        for client in CLIENTS:
            bchain_recvd = send_catch_up(msg, client)
            if bchain_recvd == '': # crashed client
                continue
            else:
                bchain_recvd = pickle.loads(bchain_recvd)
                if len(bchain_recvd) > len(bchain):
                    bchain = bchain_recvd
        print(colored("(response) All catched-up", 'yellow'))
        catchup_log()

    # send and receive messages to network and take requests from parent
    while True:
        try:
            if replied or leader_race:
                dprint(DEBUG, "(debugging) Waiting to hear on network -- replied or leader race")
                client_listen.settimeout(10)
                client_listen.listen(1)
                connection, client_addess = client_listen.accept()
            else:
                #dprint(DEBUG, "(debugging) Normal listening case")
                client_listen.settimeout(1)
                client_listen.listen(1)
                connection, client_address = client_listen.accept()

        except socket.timeout:
            #did not hear anything on the network 
            # pass
            replied = False          #kind of risky but believing in 10 secs now
            leader_race = False      # fine
            if pending_trans != None:
                dprint(DEBUG, "(debugging) Have a pending trans from client -- initiating paxos")
                send_request_messages()
            elif child_conn.poll():
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
                        pending_trans = [receiver, amount]
                        # send request messages to everyone on the network -- send ballot -- <num, pid>, index = len(bc+1) -- bc is one indexed
                        send_request_messages()
            continue

        else:
            # received some message on the network
            # (may need to put all of this in try, finally thing)
            network_message = connection.recv(RECV_LENGTH)
            # (can't close connection only bacause of CATCH-UP)
            # for now all messages are strings with first half 8 characters as header and rest is the message
            header = network_message[:HEADERSIZE].decode().strip()
            print(colored(f"(message) Received header: {header}.", 'yellow'))
            if header == 'CATCH-UP':
                dprint(DEBUG, "(debugging) Heard catch-up")
                connection.send(pickle.dumps(bchain))
                connection.close()
                dprint(DEBUG, "(debugging) Send bchain records")
            elif header == 'REQUEST':
                connection.close()
                prop_index, prop_ballot = pickle.loads(network_message[HEADERSIZE:])
                dprint(DEBUG, f"(debugging) Heard request message from {prop_ballot[1]}")
                
                if prop_ballot < replied_bal: 
                    # replied to higher ballot
                    print(colored(f"Sending reply: " + f"{'REPLY':<{HEADERSIZE}}" + "-1", 'red'))
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + bytes('6','utf-8')
                    #print(colored(f"Sending reply: "))
                    send_to_client(msg, prop_ballot[1])
                    dprint(DEBUG, f"(debugging) Replied 0 to {prop_ballot[1]}; replied_ballot := {replied_bal}.")
                else:  
                    # reply to proposed -- send log entries
                    replied_bal = prop_ballot
                    print(colored(f"(debugging) Sending reply: " + f"{'REPLY':<{HEADERSIZE}}" + "0", 'red'))
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + pickle.dumps(log)
                    send_to_client(msg, prop_ballot[1])
                    dprint(DEBUG, f"(debugging) Replied 1 to {prop_ballot[1]}; replied_ballot := {replied_bal}.")
            elif header == 'REPLY':
                connection.close()
                for i in range(500000000):
                    continue
                #print(colored(f"(message) status of not leader race {network_message[HEADERSIZE]}", 'red'))
                if network_message[-1] == 54:
                    # detect competing leaders and receive for 10 sec
                    dprint(DEBUG, "(debugging) Received reply 0; setting leader_race = True")
                    leader_race = True
                    to_prop_logs = []
                    continue # no need of this continue
                else: 
                    # accepted as a leader
                    dprint(DEBUG, "(debugging) Received reply 1; selected as leader; logs received from 1")
                    to_prop_logs = log
                    log_received = pickle.loads(network_message[HEADERSIZE:])
                    to_prop_logs += log_received
                    for i in range(len(CLIENTS)-1): # we already received one reply => -1
                        get_logs(client_listen)
                    if not leader_race:
                        # selected as leader; move on to next phase
                        dprint(DEBUG, "(debugging) No leader_race; sending accept messages")
                        msg = bytes(f"{'ACCEPT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps([ballot_num, to_prop_logs])                        
                        for client in CLIENTS:
                            send_to_client(msg, client)
                    else:
                        dprint(DEBUG, "(debugging) detected leader race during reply phase", 'cyan')
                        continue # no need
                            
            elif header == 'ACCEPT':
                connection.close()
                # check ballot with replied ballot and take decision on acceptance
                prop_ballot, to_prop_logs = pickle.loads(network_message[HEADERSIZE:])
                # currently not using to prop logs; but can use if decided to get rid of commit phase
                if prop_ballot == replied_bal:
                    # move forward with this accept
                    dprint(DEBUG, f"(debugging) Received accept from chosen leader -- reply with accept 1 and length of my bchain: {len(bchain)}")
                    msg = bytes('ACCEPTED', 'utf-8') + bytes(str(len(bchain)), "utf-8")
                    send_to_client(msg, prop_ballot[1])
                    log = []
                    clear_saved_log(PORT) # TODO: this needs to be fixed
                    # updating logs for non-leader
                    
             
                elif replied_bal == (0,0):
                    # came out of crash state (ignore the message --  can reply with 'ACCEPTED 0
                    dprint(DEBUG, "(debugging) received accept message just after recovering from crash")
                    continue # no need
                
                else:
                    # leader race, replied to someone else
                    dprint(DEBUG, "(debugging) got accept message from previous leader; informing about the new game in the town")
                    msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + bytes('6', 'utf-8')
                    send_to_client(msg, prop_ballot[1])

            elif header == 'ACCEPTED':
                connection.close()
                # only leader will get this (maybe we need to add in this phase later)
                dprint(f"(debugging) Recieved accpted msg: {network_message[HEADERSIZE:]}")
                if network_message[-1] == 54: 
                    # detect leader race
                    dprint(DEBUG, "(debugging) detected leader race during accept phase",'cyan')
                    leader_race = True
                    to_prop_logs = []
                    continue
                else:
                    # received 1 accept -- move on to commit phase
                    accepted_index = int(network_message[HEADERSIZE:].decode())
                    #if accepted_index == -1:
                        # detect leader race
                    #    dprint(DEBUG, "(debugging) detected leader race during accept phase",'cyan')
                    #    leader_race = True
                    #    to_prop_logs = []
                    #    continue
                    dprint(f"(debugging) Accepted_index: {accepted_index}")
                    if accepted_index < len(bchain):
                    # bchain entry already committed
                        dprint(DEBUG, "(debugging) another accepted for same entry; ignore this accepted")
                        continue

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
                                continue
                            else:     
                                dprint(DEBUG, "(debugging) client transaction suceeded, pushing to logs")                 
                                receiver = pending_trans[0]
                                amount = pending_trans[1]
                                transaction = Node(PORT, receiver, amount)
                                log.append(transaction)
                                write_log_to_file(PORT, receiver, amount)
                                child_conn.send('1')
                                pending_trans = None
                
            elif header == 'COMMIT': 
                connection.close()
                dprint(DEBUG, "(debugging) received COMMIT message; adding to bchain irrespective of my participation in this run")
                # can remove this phase in next itearation, everyone sends to everyone when accepted
                new_bc_entry = pickle.loads(network_message[HEADERSIZE:])
                entry = BC_entry(new_bc_entry)
                bchain.append(entry)
                index = len(bchain)
                # take care of variables which needs to be set to default
                set_to_default()
                replied_bal = (0, 0)
                    
