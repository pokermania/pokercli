from twisted.internet import reactor
from pokerprotocol import PokerFactory, PokerClientProtocol, STATE_JOIN
from pokerpackets.networkpackets import PACKET_POKER_STATE
from explain import GAME_STATE_END
try:
    from localsecret import getPasswordForBot
except ImportError:
    print "ERROR: localsecret.py does not provide getPasswordForBot (or does not exist)"
    exit(0)

import random
import time

class DbgScreen(object):
    
    def __init__(self, id):
        self.dbfn = '/home/olaf/Desktop/bots%s.log' % id
        with open(self.dbfn, "w") as fh:
            fh.write("hello again\n\n")
        self.id = id
    def addLine(self, astr):
        print self.id, astr
        # if not astr.startswith(" EEE "):
        #     return
        # astr = astr[5:]
        with open(self.dbfn, "a") as fh:
            fh.write("%s\n"%(astr,))
    def _log_into_file(*args, **kw):
        pass

class PokerBotFactory(PokerFactory):
    def __init__(self, screen, msgpokerurl, bot_serial):
        PokerFactory.__init__(self, screen, msgpokerurl)
        self.protocol = PokerBotProtocol
        self.bot_serial = bot_serial

    def letsGo(self, protocol):
        #wait between 0.1 and 5 seconds
        time.sleep(random.randint(1,50)/10.)
        #login
        self.protocol_instance.botLogin(name="BOT%s"%self.bot_serial, password=getPasswordForBot(self.bot_serial))

class PokerBotProtocol(PokerClientProtocol):
    def addTable(self, p):
        #check if table is suitable for this bot/ e.g. if it is not full
        # and try to join
        def table_is_ok(p):
            return p.seats - p.players > 0

        if not hasattr(self, "logged_in"):
            self.logged_in = False

        if table_is_ok(p) and not self.logged_in:
            self.logged_in = True
            self.executeCmd("join %s" % p.id)
        
    def changeState(self, new_state):
        PokerClientProtocol.changeState(self, new_state)
        if new_state == STATE_JOIN:
            self.executeCmd("seat")
            self.executeCmd("buy_in")
    
    def defaultHandler(self, packet):
        if packet.type == PACKET_POKER_STATE and packet.string == GAME_STATE_END:
            self.checkIfRebuy()
        PokerClientProtocol.defaultHandler(self, packet)

    def checkIfRebuy(self):
        money = self.avatar.getMoney()
        chips = self.avatar.getChips()
        if chips < 10:
            if money > 0:
                self.executeCmd("bi")
            else:
                self.executeCmd("leave")
                # Todo loose connection

    def itsYourTurn(self, last_chance=False):
        PokerClientProtocol.itsYourTurn(self)
        time.sleep(random.randint(1,2))
        if last_chance:
            self.executeCmd("call")
            return
        rand = random.random()

        if rand < 0.3:
            self.executeCmd("raise 1000")
        elif rand < 0.4:
            self.executeCmd("fold")
        else:
            self.executeCmd("call")


# screen = 
for i in range(100,108):
    print i
    reactor.connectTCP("localhost",19380, PokerBotFactory(DbgScreen(i), msgpokerurl="http://poker.pokermania.de/", bot_serial=i))
reactor.run()