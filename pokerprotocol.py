import traceback, sys
from pokerpackets import packets, clientpackets, networkpackets
from pokernetwork.client import UGAMEClientProtocol, UGAMEClientFactory

from explain import Player, Table, NoneTable

STATE_LOGIN = "login"
STATE_SEARCH = "search"
STATE_JOIN = "join"
STATE_PLAYING = "playing"


class PokerClientProtocol(UGAMEClientProtocol):
    def __init__(self, screenObj):
        UGAMEClientProtocol.__init__(self)
        self.screenObj = screenObj
        self.screenObj.executeCmd = self.executeCmd
        self.state = STATE_LOGIN
        self.avatar = Player()
        self.table = NoneTable()

        self.game_id = -1

    def logIt(self, astr, show_it=True, prefix=" [D] "):
        if show_it:
            self.screenObj.addLine(prefix + str(astr))
        else:
            self.screenObj._log_into_file(prefix + str(astr))

    def cantHandle(self, handler, name):
        if name not in (
                'PacketPokerSit',
                'PacketPokerPlayerChips',
                'PacketPokerSeats',
                'PacketPokerPlayerArrive',
                'PacketPokerPlayerLeave',
                'PacketPokerRebuy',
                'PacketPokerSitOut',
                'PacketPokerInGame',
                'PacketPokerDealer',
                'PacketPokerStart',
            ):
            self.logIt("%s can't handle %r" % (handler, name))

    def myPosition(self):
        serial = self.avatar.serial
        if serial != -1 and serial not in self.table.in_game:
            return -1
        return self.table.in_game.index(serial)

    def changeState(self, state):
        if self.state == STATE_LOGIN:
            assert state == STATE_SEARCH
        if self.state == STATE_SEARCH:
            assert state in (STATE_LOGIN, STATE_JOIN)
        self.logIt("changeState from %s to %s" % (self.state, state))
        self.state = state

    def executeCmd(self, cmd):
        self.logIt(cmd, prefix=">>> ")
        _serial_and_game_id = dict(serial=self.avatar.serial, game_id=self.game_id)
        def do_join(table_serial, *args):
            #self.logIt("join %s" % (table_serial,))
            # import rpdb2; rpdb2.start_embedded_debugger("haha")
            self.game_id = int(table_serial)
            packet = networkpackets.PacketPokerTableJoin(serial=self.avatar.serial, game_id=self.game_id)
            self.sendPacket(packet)
        def do_j(*args):
            if len(args) > 0:
                do_join(*args)
            else:
                do_join("28")
        def do_seat(*args):
            seat = 255
            self.sendPacket(networkpackets.PacketPokerSeat(seat=seat, **_serial_and_game_id))
        do_s = do_seat
        def do_pp(*args):
            if self.table:
                self.table._log_players()
        def do_bi(*args):
            # import rpdb2; rpdb2.start_embedded_debugger("haha")
            self.table.doBuyIn()
            self.table.doSit()
        def do_l(*args):
            if len(args) >= 2:
                name = args.pop(0)
                pw = args.pop(0)
            else:
                name = "testuser"
                pw = "testpass"
            self.sendPacket(packets.PacketLogin(name=name, password=pw))
            self.avatar.name = name

        def do_le(*args):
            self.table.doFold()
            self.table.doQuit()
        def do_so(*args):
            self.table.doSitOut()
        def do_si(*args):
            self.table.doSit()
        def do_ch(*args):
            self.table.doCheck()
        def do_c(*args):
            self.table.doCall()    
        def do_f(*args):
            self.table.doFold()
        def do_r(amount, *args):
            self.table.doRaise(int(amount))
        def do_ci(*args):
            self.logIt(self.table.getAvatarInfo())
        def default(commando, *args):
            self.logIt("commando %r unknown" % commando)

        #self.logIt(cmd)
        args = cmd.split()
        commando = args.pop(0)
        try:
            handle = locals()["do_"+commando]
            handle(*args)
        except KeyError:
            default(commando, *args)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.screenObj.addLine(" EEE  cmd failed: " + repr(cmd))

            for exline in traceback.format_exception(exc_type, exc_value,
                                          exc_traceback):
                for line in exline.split('\n'):
                    self.screenObj.addLine(" EEE " + str(line))
    def getDebugLines(self):
        return self.table.getDebugLines()

    def addTable(self, table_info):
        blinds, buy_ins, limit = table_info.betting_structure.split('_')
        min_buy_in, max_buy_in = buy_ins.split('-')
        info = " id=%s\t%-20s\t%s" % (table_info.id, table_info.name, table_info.betting_structure)
        print_ = False
        if int(max_buy_in) < 5000:
            print_ = True        
        self.logIt(str(info), show_it=print_, prefix=" [_] ")

    def createTable(self, table_info):
        self.table = Table(self, self.avatar, table_info)

    def defaultHandler(self, packet):
        self.table.explain(packet, self.state)

    def handleLogin(self, packet):
        if packet.type == packets.PACKET_AUTH_OK:
            self.sendPacket(networkpackets.PacketPokerSetRole(roles="PLAY"))
            self.changeState(STATE_SEARCH)
        elif packet.type == packets.PACKET_AUTH_REFUSED:
            # :( inform about the problem ):
            pass
        return False

    def handleSearch(self, packet):
        def handlePacketSerial(packet):
            serial = packet.serial
            self.avatar.serial = serial
            self.sendPacket(clientpackets.PacketPokerGetPlayerInfo())
            self.sendPacket(clientpackets.PacketPokerGetUserInfo(serial=serial))
        def handlePacketPokerPlayerInfo(packet):
            # you could update, your name/outfit/url
            pass
        def handlePacketPokerUserInfo(packet):
            self.avatar.updateMoney(packet.money)
            table_type = "%s\tholdem" % "1" if 1 in self.avatar.money else ""
            self.sendPacket(clientpackets.PacketPokerTableSelect(string=table_type))
        def handlePacketPokerTableList(packet):
            for p in packet.packets:
                self.addTable(p)
        def handlePacketPokerTable(packet):
            """ table join was successfull"""
            self.createTable(packet.__dict__)
            self.changeState(STATE_JOIN)
        try:
            handle = locals()["handle"+packet.__class__.__name__]
            handle(packet)
            return False
        except KeyError:
            self.cantHandle("Search", packet.__class__.__name__)
            return True

    def handleJoin(self, packet):
        def handlePacketPokerBuyInLimits(packet):
            return True
        # def handlePacketPokerBatchMode(packet):
        #     self.changeState(STATE_BATCH)
        def handlePacketPokerStart(packet):
            self.changeState(STATE_PLAYING)
        try:
            handle = locals()["handle"+packet.__class__.__name__]
            handle(packet)
            return False
        except KeyError:
            self.cantHandle("Join", packet.__class__.__name__)
            return True

    def handlePlaying(self, packet):
        def handlePacketPokerPosition(packet):
            if packet.position != -1 and packet.position == self.myPosition():
                self.logIt("Your Turn: " + self.table.getAvatarInfo(), prefix=" $ ")
        try:
            handle = locals()["handle"+packet.__class__.__name__]
            handle(packet)
            return False
        except KeyError:
            self.cantHandle("Playing", packet.__class__.__name__)
            return True
    # def handleBatch(self, packet):
    #     def handlePacketPokerStreamMode(packet):
    #         self.changeState(STATE_JOIN)
    #     try:
    #         handle = locals()["handle"+packet.__class__.__name__]
    #         handle(packet)
    #         return False
    #     except KeyError:
    #         self.cantHandle("Batch", packet.__class__.__name__)
    #         return self.handleJoin(packet)

    def _get_handler(self, state):
        try:
            return getattr(self, "handle" + state.capitalize())
        except:
            return self.defaultHandler

    def _handleConnection(self, packet):
        """get packets from server"""
        self.screenObj.addLine("> " + str(packet))

        if self._get_handler(self.state)(packet):
            self.defaultHandler(packet)

    def sendPacket(self, packet):
        try:
            UGAMEClientProtocol.sendPacket(self, packet)
            self.screenObj.addLine("< " + str(packet))
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.screenObj.addLine(" EEE  sendPacket failed: " + str(packet))

            for exline in traceback.format_exception(exc_type, exc_value,
                                          exc_traceback):
                for line in exline.split('\n'):
                    self.screenObj.addLine(" EEE " + str(line))


class PokerFactory(UGAMEClientFactory):

    """
    Factory used for creating Poker protocol objects 
    """

    protocol = PokerClientProtocol

    def __init__(self, screenObj):
        UGAMEClientFactory.__init__(self)
        self.screenObj = screenObj
        self.protocol = PokerClientProtocol
        self.established_deferred.addCallback(self.letsGo)

    def letsGo(self, protocol):
        # protocol.sendPacket(packets.PacketLogin(name="testuser", password="testpass"))
        # protocol.avatar.name = "testuser"
        self.screenObj.addLine("lets go")


    def buildProtocol(self, addr=None):
        instance = self.protocol(self.screenObj)
        instance.factory = self
        self.protocol_instance = instance
        self.screenObj._p = instance
        return instance

    def clientConnectionLost(self, conn, reason):
        pass