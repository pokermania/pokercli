import traceback, sys
import urllib
import simplejson
from pokerpackets import packets, networkpackets
from pokernetwork.client import UGAMEClientProtocol, UGAMEClientFactory

from explain import Player, Table, NoneTable
from twisted.web.client import getPage

STATE_LOGIN = "login"
STATE_SEARCH = "search"
STATE_JOIN = "join"
STATE_PLAYING = "playing"


class PokerClientProtocol(UGAMEClientProtocol):
    def __init__(self, screenObj, msgpokerurl):
        UGAMEClientProtocol.__init__(self)
        self.screenObj = screenObj
        self.screenObj.executeCmd = self.executeCmd
        self.state = STATE_LOGIN
        self.avatar = Player()
        self.table = NoneTable()

        self.game_id = -1
        self.msgpokerurl = msgpokerurl

    def logIt(self, astr, show_it=True, prefix=" [D] "):
        if show_it:
            self.screenObj.addLine(prefix + str(astr))
        else:
            self.screenObj._log_into_file(prefix + str(astr))

    def cantHandle(self, handler, name):
        return
        # the following lines are still here to activate the debug lines easily again
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
        if serial == -1 or serial not in self.table.in_game:
            return
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
        do_buy_in = do_bi
        def do_l(*args):
            if len(args) >= 2:
                email = args.pop(0)
                pw = args.pop(0)
            else:
                self.logIt("Error no email and password specified")
                self.logIt("l <email> <password>")

            def ok(raw_resp):
                try:
                    self.logIt("ok")
                    for line in raw_resp.splitlines():
                        self.logIt(line)
                    resp = simplejson.loads(raw_resp)
                    self._auth = resp['auth_key']
                    self.sendPacket(packets.PacketAuth(auth=self._auth))

                except:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    self.screenObj.addLine(" EEE  login failed: " + repr(cmd))

                    for exline in traceback.format_exception(exc_type, exc_value,
                                                  exc_traceback):
                        for line in exline.split('\n'):
                            self.screenObj.addLine(" EEE " + str(line))
            d = getPage(self.msgpokerurl+"/site/login?api_key=special-key",
                method='POST',
                postdata=simplejson.dumps({
                    'email': email,
                    'password': pw,
                    'rememberMe': False }),
                headers={'Content-Type':'application/json'})
            def err(reaseon):
                self.logIt(str(reason), prefix="EEE")
            d.addCallback(ok)
            d.addErrback(err)
            self.logIt("getPage")


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
        do_call = do_c
        def do_f(*args):
            self.table.doFold()
        do_fold = do_f
        def do_r(amount, *args):
            self.table.doRaise(int(amount))
        do_raise = do_r
        def do_rebuy(*args):
            if len(args) > 0:
                amount = int(args[0])
            else:
                amount = self.table.max_buy_in
            self.table.doRebuy(amount)
        def do_ci(*args):
            self.logIt(self.table.getAvatarInfo())
        def do_all_in(*args):
            self.table.doAllIn()
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

    def itsYourTurn(self):
        self.logIt("Your Turn POSITION: " + self.table.getAvatarInfo(), prefix=" $ ")

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
            self.sendPacket(networkpackets.PacketPokerGetPlayerInfo())
            self.sendPacket(networkpackets.PacketPokerGetUserInfo(serial=serial))
        def handlePacketPokerPlayerInfo(packet):
            # you could update, your name/outfit/url
            pass
        def handlePacketPokerUserInfo(packet):
            self.avatar.updateMoney(packet.money)
            table_type = "%s\tholdem" % "1" if 1 in self.avatar.money else ""
            self.sendPacket(networkpackets.PacketPokerTableSelect(string=table_type))
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
            self.logIt("POSITION pp:%s, mp:%s, chips:%s" % (packet.position,self.myPosition(), self.avatar.getChips()))
            if packet.position == self.myPosition():
                self.itsYourTurn()
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

    def botLogin(self, name, password):
        """login for bots"""
        self.sendPacket(packets.PacketLogin(name=name, password=password))

class PokerFactory(UGAMEClientFactory):

    """
    Factory used for creating Poker protocol objects 
    """

    protocol = PokerClientProtocol

    def __init__(self, screenObj, msgpokerurl):
        UGAMEClientFactory.__init__(self)
        self.screenObj = screenObj
        self.protocol = PokerClientProtocol
        self.established_deferred.addCallback(self.letsGo)
        self.msgpokerurl = msgpokerurl

    def letsGo(self, protocol):
        # protocol.sendPacket(packets.PacketLogin(name="testuser", password="testpass"))
        # protocol.avatar.name = "testuser"
        self.screenObj.addLine("lets go")


    def buildProtocol(self, addr=None):
        instance = self.protocol(self.screenObj, self.msgpokerurl)
        instance.factory = self
        self.protocol_instance = instance
        self.screenObj._p = instance
        return instance

    def clientConnectionLost(self, conn, reason):
        pass