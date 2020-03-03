import socket
import pickle
from time import sleep
from termcolor import colored
from linkedlist_and_helpers import*


# globals
HOSTNAME       = socket.gethostname()
HEADERSIZE     = 8
INIT_BAL       = 10
log            = []
bchain         = []
RECV_LENGTH    = 2000
CLIENT_ID      = None
CLIENTS        = None
PORT           = None

# paxos globals
index           = 0               # (should always be number committed entries in my blockchain -- will be initialized at zero
ballot_num      = None            # (useful for election and accepting a value) -- initialized at None, updated while sending request message and after receiving request message
#accept_num    =                # (index of last accepted blockchain object) -- may not be necessary at all
#accept_val    =                # (last accepted blockchain object -- mostly not necessary) -- again, may not be necessary
#state         =                 # (leader or not) 
#replies       =                 # (replies to check majority in any phase of paxos)
leader_race     = False           # (true if we detect race; then we sleep for random time)
pending_trans   = None            # (used in competing leader situation when received client request but somebody else is leader for this paxos run)
replied         = False           # (Flag to check if replied to someone or not)
to_prop_logs    = []              # used only when chosen as leader -- safety variable in case of leader race


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
        client_listen.settimeout(3)
        client_listen.listen(1)
        connection, client_address = client_listen.accept()
    except socket.timeout:
        pass
        return
    else:
        print(colored("(debugging) logs received from 2", 'blue'))
        network_message = connection.recv(RECV_LENGTH)
        connection.close()
        if network_message[HEADERSIZE] == 0:
            # detect competing leaders and receive for 10 sec
            print(colored("(debugging) detected leader race during reply phase", 'blue'))
            leader_race = True
            to_prop_logs = []
            return
        else:
            print(colored("(debugging) logs appended to to_prop_logs", 'blue'))
            received_logs = pickle.loads(network_message[HEADERSIZE+1:])
            to_prop_logs += received_logs

def set_to_default():
    global log
    global leader_race
    global replied
    global ballot_num
    log = []
    leader_race = False
    replied = False 
    ballot_num = (0, CLIENT_ID)
    print(colored("(debugging) setting values to default at the end of paxos run", 'blue'))

def pending_trans_status():
    global pending_trans
    global bchain
    global PORT
    receiver = pending_trans[0]
    amount = pending_trans[1]
    all_trans = all_transactions(bchain)
    if calculateBalance(all_trans, INIT_BAL, PORT) >= amount:
        return True
    return False


# main communication function
def communication(child_conn, arguments):
   
    global HOSTNAME
    global HEADERSIZE
    global INIT_BAL
    # global ID
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

    PORT = arguments[0]
    CLIENTS = arguments[1]
    CLIENT_ID = arguments[2]
    ballot_num = (0, CLIENT_ID)
    replied_bal = (0,0)

    client_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_listen.bind((HOSTNAME, PORT))
    client_listen.listen()
    
    
    # play catch-up (can make separate function to do this)
    print(colored("(message) Catching-up with others in the network", 'yellow'))
    msg = bytes("CATCH-UP", 'utf-8')
    for client in CLIENTS:
        bchain_recvd = send_catch_up(msg, client)
        if bchain_recvd == '': # crashed client
            continue
        else:
            bchain_recvd = pickle.loads(bchain_recvd)
            if len(bchain_recvd) > len(bchain):
                bchain = bchain_recvd
    print(colored("(response) All catched-up", 'yellow'))

    # send and receive messages to network and take requests from parent
    while True:
        try:
            if replied or leader_race:
                print(colored("(debugging) Waiting to hear on network -- replied or leader race", 'blue'))
                client_listen.settimeout(10)
                client_listen.listen(1)
                connection, client_addess = client_listen.accept()
            else:
                #print(colored("(debugging) Normal listening case", 'blue'))
                client_listen.settimeout(1)
                client_listen.listen(1)
                connection, client_address = client_listen.accept()
        except socket.timeout:
            #did not hear anything on the network 
            # pass
            replied = False          #kind of risky but believing in 10 secs now
            leader_race = False      # fine
            if pending_trans != None:
                print(colored("(debugging) Have a pending trans from client -- initiating paxos", 'blue'))
                send_request_messages()
            elif child_conn.poll():
                request = child_conn.recv()
                if request[0] == '2': # balance
                    print(colored("(debugging) Received balance request from client", 'blue'))
                    balances = balance(PORT, CLIENTS, bchain, log)
                    child_conn.send(pickle.dumps(balances))
                    print(colored("(debugging) Sent balances to parent", 'blue'))
                
                elif request[0] == '3': # print log
                    print(colored("(debugging) Received print log request",'blue'))
                    child_conn.send(pickle.dumps(log))
                    print(colored("(debugging) Sent logs to parent", 'blue'))

                elif request[0] == '4': # print Blockchain
                    print(colored("(debugging) Received print bchain request", 'blue'))
                    child_conn.send(pickle.dumps(bchain))
                    print(colored("(debugging) Sent bchain to parent", 'blue'))

                elif request[0] == '1': # transfer
                    print(colored("(debuggin) Received transfer request from client", 'blue'))
                    list_request = list(map(int, request.strip().split()))
                    receiver = list_request[1]
                    amount = list_request[2]
                    all_trans = all_transactions(bchain, log)
                    if calculateBalance(all_trans, INIT_BAL, PORT) >= amount: 
                        transaction = Node(PORT, receiver, amount)
                        log.append(transaction)
                        child_conn.send('1') # success
                        print(colored("(debugging) Client has enough balance -- Transaction added to the logs", 'blue'))

                    else:
                    # need to initiate paxos run    
                        print(colored("(debugging) Cliet doesn't have enough balance; need to start paxos run", 'blue'))
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
                print(colored("(debugging) Heard catch-up", 'blue'))
                connection.send(pickle.dumps(bchain))
                connection.close()
                print(colored("(debugging) Send bchain records", 'blue'))
            elif header == 'REQUEST':
                connection.close()
                prop_index, prop_ballot = pickle.loads(network_message[HEADERSIZE:])
                print(colored(f"(debugging) Heard request message from {prop_ballot[1]}", 'blue'))
                #if prop_index < len(bchain): 
                    # proposing filled index                                        (will never happen -- If you are alive you'll have updated bchain)
                #    missing_entries = bchain[len(bchain) - (prop_index - 1):]
                #    msg = bytes('REPLY   2','utf-8') + pickle.dumps(missing_entries)
                #    send_to_client(msg, prop_ballot[1])
                if prop_ballot < replied_bal: 
                    # replied to higher ballot
                    print(colored(f"Sending reply: " + f"{'REPLY':<{HEADERSIZE}}" + "0", 'red'))
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + (0).to_bytes(1, 'little')
                    send_to_client(msg, prop_ballot[1])
                    print(colored(f"(debugging) Replied 0 to {prop_ballot[1]}; replied_ballot := {replied_bal}.", 'blue'))
                else:  
                    # reply to proposed -- send log entries
                    replied_bal = prop_ballot
                    print(colored(f"Sending reply: " + f"{'REPLY':<{HEADERSIZE}}" + "0", 'red'))
                    msg = bytes(f"{'REPLY':<{HEADERSIZE}}",'utf-8') + (1).to_bytes(1, 'little') + pickle.dumps(log)
                    send_to_client(msg, prop_ballot[1])
                    print(colored(f"(debugging) Replied 1 to {prop_ballot[1]}; replied_ballot := {replied_bal}.", 'blue'))
            elif header == 'REPLY':
                connection.close()
                    #'''if network_message[HEADERSIZE].decode() == '2': 
                        # need to fill up missing entries and propose with higher index
                    #    missing_entries = pickle.loads(network_message[HEADERSIZE+1:])
                    #    bchain += missing_entries'''
                
                print(colored(network_message[HEADERSIZE], 'red'))
                if network_message[HEADERSIZE] == 0:
                    # detect competing leaders and receive for 10 sec
                    print(colored("(debugging) Received reply 0; setting leader_race = True", 'blue'))
                    leader_race = True
                    to_prop_logs = []
                    continue # no need of this continue
                else: 
                    # accepted as a leader
                    print(colored("(debugging) Received reply 1; selected as leader; logs received from 1", 'blue'))
                    to_prop_logs = log
                    log_received = pickle.loads(network_message[HEADERSIZE+1:])
                    to_prop_logs += log_received
                    for i in range(len(CLIENTS)-1): # we already received one reply => -1
                        get_logs(client_listen)
                    if not leader_race:
                        # selected as leader; move on to next phase
                        print(colored("(debugging) No leader_race; sending accept messages", 'blue'))
                        msg = bytes(f"{'ACCEPT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps([ballot_num, to_prop_logs])                        
                        for client in CLIENTS:
                            send_to_client(msg, client)
                    else:
                        print(colored("(debugging) detected leader race during reply phase", 'blue'))
                        continue # no need
                            
            elif header == 'ACCEPT':
                connection.close()
                # check ballot with replied ballot and take decision on acceptance
                prop_ballot, to_prop_logs = pickle.loads(network_message[HEADERSIZE:])
                # currently not using to prop logs; but can use if decided to get rid of commit phase
                if prop_ballot == replied_bal:
                    # move forward with this accept
                    print(colored(f"(debugging) Received accept from chosen leader -- reply with accept 1 and length of my bchain: {len(bchain)}", 'blue'))
                    msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + (1).to_bytes(1, 'little') + bytes(str(len(bchain)), "utf-8")
                    send_to_client(msg, prop_ballot[1])
             
                elif replied_bal == (0,0):
                    # came out of crash state (ignore the message --  can reply with 'ACCEPTED 0
                    print(colored("(debugging) received accept message just after recovering from crash", 'blue'))
                    continue # no need
                
                else:
                    # leader race, replied to someone else
                    print(colored("(debugging) got accept message from previous leader; informing about the new game in the town", 'blue'))
                    msg = bytes(f"{'ACCEPTED':<{HEADERSIZE}}", 'utf-8') + (0).to_bytes(1, 'little')
                    send_to_client(msg, prop_ballot[1])

            elif header == 'ACCEPTED':
                connection.close()
                # only leader will get this (maybe we need to add in this phase later)
                print(colored(f"Recieved accpted msg: {network_message[HEADERSIZE:]}", 'red'))
                if network_message[HEADERSIZE:] == 0: # no idea what's going on here
                    # detect leader race
                    print(colored("(debugging) detected leader race during accept phase", 'blue'))
                    leader_race = True
                    to_prop_logs = []
                    continue
                else:
                    # received 1 accept -- move on to commit phase
                    accepted_index = int(network_message[HEADERSIZE+1])
                    if accepted_index <= len(bchain):
                    # bchain entry already committed
                        print(colored("(debugging) another accepted for same entry; ingore thos accepted", 'blue'))
                        continue

                    else:
                        print(colored("(debugging) received one accepted; committing bc entry and sending commit", 'blue'))
                        entry = BC_entry(to_prop_logs)
                        bchain.append(entry)
                        index = len(bchain)
                        msg = bytes(f"{'COMMIT':<{HEADERSIZE}}", 'utf-8') + pickle.dumps(to_prop_logs)
                        for client in CLIENTS:
                            send_to_client(msg, client)
                        # take care of all other variables which should be set to default
                        set_to_default()
                        replied_bal = (0, 0)
                    print(colored("(debugging) checking pending transaction status", 'blue'))
                    pend_trans_status = pending_trans_status()
                    pend_trans_status = False
                    if not pend_trans_status:
                        # don't have enough balance; send failed transaction message
                        print(colored("(debugging) client transaction failed, not enough balance :(", 'blue'))
                        pending_trans = None
                        child_conn.send('0')
                    else:
                        # push pending trans to log and send reply to client (can make function for this)
                        print(colored("(debugging) client transaction suceeded, pushing to logs", 'blue'))                        
                        receiver = pending_trans[0]
                        amount = pending_trans[1]
                        transaction = Node(PORT, receiver, amount)
                        log.append(transaction)
                        child_conn.send('1')
                
            elif header == 'COMMIT': 
                connection.close()
                print(colored("(debugging) received COMMIT message; adding to bchain irrespective of my participation in this run", 'blue'))
                # can remove this phase in next itearation, everyone sends to everyone when accepted
                new_bc_entry = pickle.loads(network_message[HEADERSIZE:])
                entry = BC_entry(new_bc_entry)
                bchain.append(entry)
                index = len(bchain)
                # take care of variables which needs to be set to default
                set_to_default()
                replied_bal = (0, 0)
                # check transaction status if any pending and append it to the log
                # pend_trans_status = False
                pend_trans_status = pending_trans_status()
                if pending_trans != None:
                    print(colored("(debugging) have some pending transaction from client; checking status", 'blue'))
                    pend_trans_status = pending_trans_status()
                if not pend_trans_status:
                    # do paxos run with this process as a leader
                    print(colored("(debugging) pending transaction not resolved; initiating own run of paxos", 'blue'))
                    continue
                else:
                    # push pending trans to log and send reply to client
                    print(colored("(debugging) pending transaction resolved due to someone else's paxos run", 'blue'))
                    pending_trans = None
                    receiver = pending_trans[0]
                    amount = pending_trans[1]
                    transaction = Node(PORT, receiver, amount)
                    log.append(transaction)
                    child_conn.send('1')
                    
                    
