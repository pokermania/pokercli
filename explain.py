import traceback, sys
from pokerpackets import networkpackets
from pokereval import PokerEval


def catcher(fn):
    """short helper wrapper function to get nicer tracebacks"""
    def wrap(*args,**kw):
        try:
            return fn(*args, **kw)
        except Exception:
            retl = []
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            retl.append(" EEE  %s failed: " % fn.__name__)

            for exline in traceback.format_exception(exc_type, exc_value,
                                          exc_traceback):
                for line in exline.split('\n'):
                    retl.append(" EEE %s" % str(line))
            return retl
    return wrap

# possible poker game states
GAME_STATE_NULL = "null"
GAME_STATE_BLIND_ANTE = "blindAnte"
GAME_STATE_PRE_FLOP = "pre-flop"
GAME_STATE_FLOP = "flop"
GAME_STATE_THIRD = "third"
GAME_STATE_TURN = "turn"
GAME_STATE_FOURTH = "fourth"
GAME_STATE_RIVER = "river"
GAME_STATE_FIFTH = "fifth"
GAME_STATE_MUCK = "muck"
GAME_STATE_END = "end"


class Player(object):
    """Player object handles money and game states of the player"""

    def __init__(self, serial=None, **player_info):
        self.serial = serial
        self.money = {}
        self._chips = 0
        self._bet = 0
        self.cards = []
        self._fold = False
        self.update(player_info)

    def update(self, player_info):
        """update informations about this player. E.g. seat or name of player"""
        self.seat = player_info.get("seat", -1)
        self.name = player_info.get("name", "unknown")
        self.sit_out = player_info.get("sit_out", True)

    def notFold(self):
        """returns True if player is not fold"""
        return not self._fold

    def sit(self):
        """change internale sit state to sit"""
        self.sit_out = False

    def sitOut(self):
        """change internale sit state to sit_out"""
        self.sit_out = True

    def updateMoney(self, moneydict):
        """update money of current player"""
        for currency_serial, amounts in moneydict.iteritems():
            self.money[currency_serial] = amounts[0]
    def updateChips(self, chips=None, bet=None):
        """update table chips/bet of the player"""
        if not chips is None:
            self._chips = chips
        if not bet is None:
            self._bet = bet
    def updateCards(self, cards):
        """update player cards"""
        self.cards = cards
    def getCards(self):
        """get cards (whithout information if the card is visible to others or not)"""
        return list(map(lambda x:x&63, self.cards))
    def rebuy(self, amount):
        """transfer money to the table (just internal state)"""
        self._chips += amount
        self._decrease_money(amount)

    def reset(self):
        """reset internal states"""
        if self._bet != 0:
            self._bet = 0
        self.cards = []
        self._fold = False

    def bet(self, amount):
        """transfer money from table to bet (just internal state)"""
        self._chips -= amount
        self._bet += amount
        assert self._chips >= 0

    def getChips(self):
        """returns the current chips amount"""
        return self._chips

    def getMoney(self):
        """return players bank money"""
        if 1 in self.money:
            return self.money[1]
        else:
            return 0

    def isSit(self):
        """returns True if player sits"""
        print self.sit_out
        return (not self.sit_out)

    def _decrease_money(self, amount):
        """decrese player money, to keep track of your bank money (internal state)"""
        if 1 in self.money:
            self.money[1] -= amount

    def _player_info(self):
        """return some usefull information about"""
        return "%r %s seat:%s m:%r c:%s b:%s " % (self.name, self.serial, self.seat, self.money, self._chips, self._bet)

class NoneTable(object):
    """
        If there is no Table we use the None table.
        It has the same public interface but ignores all calls and returns the safest
        values. (An empty list when a list is required)

    """
    def __init__(self):
        self.id = -1
        self.seats = [0]
        self.name = "unnamed"
        self.seat = -1
        self.players = {}
        self.in_game = []
        self.position = -1
        self.max_buy_in = 0
        self.min_buy_in = 0
        self.board_cards = []
    def isInPosition(self, *args):
        return False
    def getDebugLines(self, *args, **kw):
        return []
    def logIt(self, *args, **kw):
        pass
    updateSeats = addPlayer = removePlayer = updatePlayer = updatePlayerChips = \
    rebuy = reset = explain = doBuyIn = doSit = doSitOut = doQuit = doFold = \
    doCall = doRaise = logIt
    def __nonzero__(self):
        return False

class Table(object):
    def __init__(self, protocol, avatar, table_info):
        self.protocol = protocol
        self.id = table_info.get('id', 0)
        self.seat = table_info.get('player_seated', -1)
        self.seats = [0] * table_info.get('seats', 10)
        if self.seat != -1:
            self.seats[self.seat] = avatar.serial
            assert avatar.seat == self.seat, "as %s, ss %s" % (avatar.seat, self.seat)
        self.name = table_info.get('name', 'unnamed')
        self.betting_structure =  table_info['betting_structure']
        blinds, buy_ins, limit = table_info['betting_structure'].split('_')
        min_buy_in, max_buy_in = buy_ins.split('-')
        small, big = blinds.split('-')

        self.max_buy_in = int(max_buy_in)*100
        self.min_buy_in = int(min_buy_in)*100
        self.big_blind = int(big)*100
        self.small_blind = int(small)*100

        self.players = {avatar.serial: avatar}
        self.avatar = avatar
        self._serial_and_game_id = dict(serial=avatar.serial, game_id=self.id)
        self._eval = PokerEval()
        self.reset()
        self._game_state = GAME_STATE_NULL

    def reset(self):
        """reseting game states for a new hand"""
        self.board_cards = []
        self.position = -1
        self._reset_players()

    def getBoardCards(self):
        """return a list of board games"""
        return list(map(lambda x:x&63, self.board_cards))

    def getAvatarInfo(self):
        """return a string of usefull information about the avatar"""
        return ", ".join(self._get_avatar_info())

    def isInPosition(self, serial):
        """returs true if player with serial is in position"""
        return serial in self.in_game and self.position == self.in_game.index(serial)

    def logIt(self, astr, prefix=" [D] "):
        """a little helper function to log output"""
        self.protocol.logIt(astr, prefix=prefix)

    def updateSeats(self, seats):
        """update seat information"""
        for index, (old, new) in enumerate(zip(self.seats, seats)):
            if old == 0 and new != 0:
                self.addPlayer(index, new)
            elif old != 0 and new == 0:
                self.removePlayer(index)
            elif old != new:
                self.removePlayer(index)
                self.addPlayer(index, new)
                self.logIt("warning idx %s, old %s, new %s" % (index, old, new))

    def addPlayer(self, index, serial):
        """Add player to this table"""
        self.seats[index] = serial
        # Request more information about this player
        if serial == self.avatar.serial:
            self.players[index] = self.avatar
        else:
            self.protocol.sendPacket(networkpackets.PacketPokerGetUserInfo(serial=serial))

    def removePlayer(self, index):
        """remove player from this table"""
        serial = self.seats[index]
        self.seats[index]=0
        if serial in self.players:
            del self.players[serial]

    def updatePlayer(self, player_info):
        """update general palyer information (we requested them in addPlayer)"""
        player = self._get_or_create_player(**player_info)
        player.update(player_info)

    def updatePlayerChips(self, serial, chips, bet):
        """update players chips"""
        player = self._get_or_create_player(serial=serial)
        return player.updateChips(chips, bet)

    def updatePlayerCards(self, serial, cards):
        """update players cards"""
        player = self._get_player(serial)
        player.updateCards(cards)

    def rebuy(self, serial, amount):
        """update money state of player because a rebuy happend"""
        player = self._get_player(serial)
        player.rebuy(amount)

    def _reset_players(self):
        """reset player states"""
        for player in self.players.values():
            player.reset()

    def highestBetNotFold(self):
        """returns the highest bet of all players that are not fold"""
        return max([0]+[p._bet for p in self.players.values() if p.serial in self.in_game and p.notFold()])
    
    def inSmallBlindPosition(self):
        """returns True if the player in position is in small_blind position"""
        return len(self.in_game) > 0 and ((self.dealer + 1) % len(self.in_game)) == self.position

    def bigBlind(self):
        """returns the big_blind of the current table"""
        return self.big_blind or 0

    def doBuyIn(self):
        """actually request a buy_in"""
        self.protocol.sendPacket(networkpackets.PacketPokerBuyIn(amount=self.max_buy_in, **self._serial_and_game_id))
        self.protocol.sendPacket(networkpackets.PacketPokerAutoBlindAnte(**self._serial_and_game_id))
    
    def doRebuy(self, amount):
        """actually request a rebuy"""
        self.protocol.sendPacket(networkpackets.PacketPokerRebuy(amount=amount, **self._serial_and_game_id))

    def doSit(self):
        """actually request a sit"""
        self.protocol.sendPacket(networkpackets.PacketPokerSit(**self._serial_and_game_id))
    
    def doSitOut(self):
        """actually request a sitout"""
        self.protocol.sendPacket(networkpackets.PacketPokerSitOut(**self._serial_and_game_id))
    
    def doQuit(self):
        """actually request a table quit"""
        self.protocol.sendPacket(networkpackets.PacketPokerTableQuit(**self._serial_and_game_id))
    
    def doFold(self):
        """actually request a fold"""
        self.protocol.sendPacket(networkpackets.PacketPokerFold(**self._serial_and_game_id))
    
    def doCheck(self):
        """actually request a check"""
        self.protocol.sendPacket(networkpackets.PacketPokerCheck(**self._serial_and_game_id))
    
    def doCall(self):
        """actually request a call"""
        self.protocol.sendPacket(networkpackets.PacketPokerCall(**self._serial_and_game_id))
    
    def doAllIn(self):
        """actually raise all chips"""
        self.doRaise(self.avatar.getChips())
    def doRaise(self, amount):
        """
            actually request a raise by a given amount.
            WARNING: If the amount you requested is too low, the raise will be accepted but the 
            minimum amount to raise will be used instead. You will be informend about the amount 
            that is used to raise.
        """
        self.protocol.sendPacket(networkpackets.PacketPokerRaise(amount=amount, **self._serial_and_game_id))
    

    def explain(self, packet, state):
        """packets that might be interesting for the game will be handled here"""
        def handlePacketPokerBuyInLimits(packet):
            self.max_buy_in = packet.max
            self.min_buy_in = packet.min
        def handlePacketPokerSeats(packet):
            return self.updateSeats(packet.seats)
        def handlePacketPokerPlayerInfo(packet):
            self.updatePlayer(packet.__dict__)
        def handlePacketPokerPlayerChips(packet):
            return self.updatePlayerChips(packet.serial, chips=packet.money, bet=packet.bet)
        def handlePacketPokerPlayerArrive(packet):
            self.updatePlayer(packet.__dict__)
        def handlePacketPokerPlayerLeave(packet):
            self.removePlayer(packet.seat)
        def handlePacketPokerSit(packet):
            self._get_player(packet.serial).sit()
        def handlePacketPokerSitOut(packet):
            self._get_player(packet.serial).sitOut()
        def handlePacketPokerRebuy(packet):
            assert self.id == packet.game_id
            self.rebuy(packet.serial, packet.amount)
        def handlePacketPokerInGame(packet):
            assert self.id == packet.game_id
            self.in_game = packet.players
        def handlePacketPokerPosition(packet):
            assert self.id == packet.game_id
            self.position = packet.position
        def handlePacketPokerStart(packet):
            assert self.id == packet.game_id
            self.reset()
            self.hand_serial = packet.hand_serial
        def handlePacketPokerDealer(packet):
            assert self.id == packet.game_id
            # assert self.dealer == packet.previous_dealer
            self.dealer = packet.dealer
        def handlePacketPokerPlayerCards(packet):
            self.updatePlayerCards(packet.serial, packet.cards)
            if packet.serial == self.avatar.serial:
                self.logIt("You got %r" % self._cards_to_string(packet.cards))
        def handlePacketPokerBoardCards(packet):
            self.board_cards = packet.cards
        def handlePacketPokerRaise(packet):
            self._get_player(packet.serial).bet(packet.amount)
        def handlePacketPokerCall(packet):
            player = self._get_player(packet.serial)
            highestbet = self.highestBetNotFold()
            bigb =self.bigBlind() if self._game_state == GAME_STATE_PRE_FLOP and not self.inSmallBlindPosition() else 0
            # import rpdb2; rpdb2.start_embedded_debugger("haha")
            self.logIt("%r, %r" % (highestbet,bigb))
            amount = min(
                max(highestbet,bigb) - player._bet,
                player.money
            )
            player.bet(amount)
        def handlePacketPokerState(packet):
            self._game_state = packet.string
        def handlePacketPokerBlind(packet):
            self._get_player(packet.serial).bet(packet.amount)

        try:
            handle = locals()["handle"+packet.__class__.__name__]
            return handle(packet)
        except KeyError:
            # self.logIt(" explain cant handle : %r" % packet.__class__.__name__)
            return True
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.logIt(packet.__class__.__name__, prefix=" EEE  handle failed: ")

            for exline in traceback.format_exception(exc_type, exc_value,
                                          exc_traceback):
                for line in exline.split('\n'):
                    self.logIt(str(line), prefix=" EEE ")

    def _cards_to_string(self, cards):
        """return a string for cards in a human readable way"""
        return repr(self._eval.card2string(map(lambda x: x & 63, cards)))\
            #.lower().replace("h", u"\u2761").replace("s", u"\u2660").replace("c", u"\u2663").replace("d", u"\u2662")
    def _get_or_create_player(self, serial, seat=None, **player_info):
        """returns the player with the serial, the player will be created if it does not exist yet"""
        # serial = player_info['serial']
        # seat = player_info['seat']
        if seat and self.seats[seat] != 0 and serial != self.seats[seat]:
            self.logIt("%s is allready on seat %s, cleared" % (self.seats[seat], seat))
            del self.players[self.seats[seat]]
            self.seats[seat] = serial

        if serial not in self.players:
            self.players[serial] = Player(serial=serial, seat=seat, **player_info)

        return self.players[serial]
    
    def _get_player(self, serial):
        """returns the player, raises an IndexError if it does not exist"""
        return self.players[serial]

    def _log_players(self):
        """ log player informations """
        self.logIt("Players:")
        for player in self.players.itervalues():
            self.logIt(player._player_info())
        self.logIt("")

    
    def getDebugLines(self):
        """returns a list of debug lines (yellow box)"""
        return self._get_table_info() + self._get_avatar_info() + self._get_player_info()

    @catcher
    def _get_table_info(self):
        """returns a list of table informations"""
        highestbet = self.highestBetNotFold(),
        bigb =self.bigBlind() if self._game_state == GAME_STATE_PRE_FLOP and not self.inSmallBlindPosition() else 0
        return ["blinds: small:%r big:%r" % (self.small_blind, self.big_blind),
                "buy_ins: min:%r max:%r" % (self.min_buy_in, self.max_buy_in),
                "bs: %r" % self.betting_structure,
                "highestbet = %r" % highestbet,
                "bigb = %r" % bigb,]
    @catcher
    def _get_player_info(self):
        """returns a list with player informations for all players"""
        return [player._player_info() for player in self.players.values()]
    @catcher
    def _get_avatar_info(self):
        """returns informations of the avatar that is currently logged in"""
        retvals = []
        if self.avatar.cards:
            retvals.append("hand: " + self._cards_to_string(self.avatar.cards))
        if self.board_cards:
            retvals.append("board: " + self._cards_to_string(self.board_cards))
            if self.avatar.cards:
                best_hand = self._eval.best_hand("hi", self.avatar.getCards() + self.getBoardCards())
                desc = best_hand.pop(0)
                retvals.append("%s: %s" % (desc, self._cards_to_string(best_hand)))
        return retvals

