from pokerpackets.packets import *
from pokerpackets.networkpackets import *
from pokerpackets.clientpackets import *

class PacketNotFoundError(Exception): pass
        

def getPacketFromString(astring):
    name, rest = astring.split(" ",1)
    print name, repr(rest)
    params = getParamsFromString(rest)
    return convertToPacket(name, params)

def getParamsFromString(paramString):
    """
        >>> getParamsFromString("foo = bar")
        {"foo": "bar"}
        >>> getParamsFromString("foo = bar hello = world")
        {"foo": "bar", "hello": "world"}
        >>> getParamsFromString("multiword = this is a sample foo = bar")
        {"multiword": "this is a sample", "foo": "bar"}
    """
    params = {}
    rest = paramString.strip()
    next_equal = 1
    while next_equal >= 0:
        name, rest = rest.split(" ",1)
        # print name, repr(rest)
        assert rest.startswith("="), repr(rest[:20])
        _, rest = rest.split(" ",1)
        if rest.startswith("["):
            end = rest.find("]")
            packets = rest[1:end ].split(', ')
            if packets[0].isdigit():
                value = list(map(int, packets))
            else:
                value = [getPacketFromString(packet) for packet in packets]
            rest = rest[end+1:].strip()
            next_equal = rest.find("=")
            # print repr(rest)
            
        else:
            next_equal = rest.find("=")
            if next_equal == -1:
                value = rest
            else:
                tmp = rest[:next_equal-1][::-1].find(" ")
                assert tmp != -1
                value, rest = rest[:next_equal-2-tmp], rest[next_equal-1-tmp:]
        params[name]=value
    return params

def clean(value, var_type):
    # print "clean %-10s %r" % (var_type, value)
    converter = {
        "I": lambda x:int(x),
        "B": lambda x:int(x),
        "Bnone": lambda x:int(x) if x != 255 else None,
        "Q": lambda x:int(x),
        "bool": lambda x: x == "True",
    }

    if var_type in converter:
        return converter[var_type](value)

    return value

def convertToPacket(name, params):
    # print params
    try:
        packet_type = globals()["PACKET_" + name]
    except KeyError:
        raise PacketNotFoundError()

    packet = PacketFactory[packet_type]

    type_lookup = {}
    for name, _, var_type in packet.info:
        type_lookup[name]=var_type

    clean_params = {}
    for name, value in params.items():
        clean_params[name]=clean(value, type_lookup[name])

    # print clean_params
    return packet(**clean_params)


if __name__ == "__main__":
    packet = getPacketFromString("POKER_TABLE  type = 73 length = 103 id = 28 seats = 9 average_pot = 11315 hands_per_hour = 40 percent_flop = 58 players = 0 observers = 3 waiting = 0 player_timeout = 25 muck_timeout = 5 currency_serial = 1 name = Fish and Chips variant = holdem betting_structure = 1-2_10-100_1000-pokermania skin = default reason = TableJoin tourney_serial = 0 player_seated = -1")
