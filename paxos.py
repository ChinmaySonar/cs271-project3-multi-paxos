#TODO: Write all paxos logic here

from client import *
from linkedlist import PaxosMessage

HEADERSIZE = 7

def start_leader_election(index, ballot_num):
    """
    This function sends a request to all other clients to become leader

    args:
        - ballot_num
        - index
    """

    # create a message for REQ
    msg = bytes(f"{'REQ':<{HEADERSIZE}}", "utf-8")
    msg += pickle.dumps(PaxosMessage(index, ballot_num))

    t = threading.Thread(name="Send Paxos REQ message", target=send_to_clients, args=(msg,))
    t.start()
    t.join()

def handle_request(conn, msg, state, index, ballot_num, log, bchain):
    """
    This function is called if the header recv is REQ - leader election/proposal
    args:
        - state - to check if it has requested to be a leader 
        - index - current index of bchain
        - ballot_num - comparision for current index run

    return:
        absolutely nothing
    """
    msg = bytes(f"{'REP':<{HEADERSIZE}}", "utf-8")
    if msg.index > index:
        # reply back with yes to leader election
        msg += pickle.dumps(PaxosMessage(index, ballot_num, [],log))
        
    else:
        # reply back with the the bchain[index] and accept_val

        msg += pickle.dumps(PaxosMessage(index, ballot_num, bchain[index]))

    conn.send(msg)
    return