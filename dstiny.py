"""Implements the dstiny driver
"""
import crcmod 
import logging
import ConfigParser


# definition of devices configured by the exhood's dStiny
EXHOOD_FAN_FLAP_dSxid = 1
EXHOOD_LIGHT_dSxid = 2
EXHOOD_FLAP_WINDOW_CONTACT_dSxid = 3

DS_GROUP_VENTILATION = 10
DS_GROUP_LIGHT = 1

DS_STATUS_VALUES_START = 0x10
DS_POLL_STATUS_ERROR = 8
DS_POLL_STATUS_INFO = 9

SCENE_REG_CONF_START = 16  # 0x10

# scene: register
fan_scenes_regs = {0: SCENE_REG_CONF_START,
                   1: SCENE_REG_CONF_START+1,
                   2: SCENE_REG_CONF_START+2,
                   3: SCENE_REG_CONF_START+3,
                   4: SCENE_REG_CONF_START+4,
                   5: SCENE_REG_CONF_START+5,
                   6: SCENE_REG_CONF_START+6,
                   7: SCENE_REG_CONF_START+7,
                   8: SCENE_REG_CONF_START+8,
                   9: SCENE_REG_CONF_START+9,
                   }


flap_scenes_regs = {20: SCENE_REG_CONF_START+10,
                    21: SCENE_REG_CONF_START+11,
                    22: SCENE_REG_CONF_START+12,
                    23: SCENE_REG_CONF_START+13,
                    24: SCENE_REG_CONF_START+14,
                    25: SCENE_REG_CONF_START+15,
                    26: SCENE_REG_CONF_START+16,
                    27: SCENE_REG_CONF_START+17,
                    28: SCENE_REG_CONF_START+18,
                    29: SCENE_REG_CONF_START+19,
                    }


fan_scenes_defaults = {0: 0,
                       1: 11,
                       2: 22,
                       3: 33,
                       4: 44,
                       5: 55,
                       6: 66,
                       7: 77,
                       8: 88,
                       9: 100,
                       }

flap_scenes_defaults = {20: 0,
                        21: 11,
                        22: 22,
                        23: 33,
                        24: 44,
                        25: 55,
                        26: 66,
                        27: 77,
                        28: 88,
                        29: 100,
                        }

# scene:intensity[%]
light_scenes = {13: 0,
                0: 0,
                # 1:100,
                14: 100}


###############################################################
# Support functions
###############################################################

def init_crc():
    POLYNOMIAL = 0x1d5  # 0xd5 + leading 1
    crc = crcmod.mkCrcFun(poly=POLYNOMIAL, initCrc=0, rev=False)
    return crc


class dSTel:
    """ Dstiny telegram

    args contains the positional arguments in the following order:
    bank, offset, val_lo, val_hi
    """

    def __init__(self, cmdch, dSidx, args):
        self.cmdch = cmdch
        self.dSidx = dSidx
        self.args = args
        self.NTRIES = 3  # number of times a  command is retried
        self.crc8_function = init_crc()

    def get(self):
        body = ''
        for i in self.args:
            body = body+'%02X' % i

        s = "%c%1X%s" % (self.cmdch, self.dSidx, body)
        crc = self.crc8_function(s.encode(encoding='utf-8'))
        s = "%s%02X\r\n" % (s, crc)
        return s


class dstiny:
    def __init__(self, port, mivune_ctr, logfile, conffile):
        self.port = port
        self.port.ser.close()
        self.port.ser.open()
        self.logger = logging.getLogger(logfile)
        self.crc8_function = init_crc()
        self.conffile = conffile
        self.config = ConfigParser.ConfigParser()
        self.config.readfp(open(self.conffile))
        self.mivune_ctr = mivune_ctr
        self.checkConfig()
        self.NTRIES = 3
        # self.memory_map=[]

    def checkConfig(self):
        for scene in fan_scenes_regs.keys():
            reg = fan_scenes_regs[scene]
            if not self.config.has_option('Fan_Flap', str(reg)):
                value = fan_scenes_defaults[scene]
                self.setConfSceneLevel('Fan_Flap', reg, value)

        for scene in flap_scenes_regs.keys():
            reg = flap_scenes_regs[scene]
            if not self.config.has_option('Fan_Flap', str(reg)):
                value = flap_scenes_defaults[scene]
                self.setConfSceneLevel('Fan_Flap', reg, value)

    def getConfSceneLevel(self, section, scene):
        """
        Return the corresponding configured value, or -1 if not
        present or improperly configured
        """

        scene = str(scene)
        if self.config.has_option(section, str(scene)):
            try:
                ret = int(self.config.getint(section, str(scene)))
                return ret
            except Exception as e:
                self.logger.exception(e)
                return -1
        else:
            self.logger.info("section does not exist:"+section+"->"+scene)
            return -1

    def setConfSceneLevel(self, section, scene, value):
        try:
            self.config.set(section, str(scene), str(value))
            with open(self.conffile, 'w') as c:
                self.config.write(c)
                return True
        except ConfigParser.NoSectionError:
            self.config.add_section(section)
            self.config.set(section, str(scene), str(value))
            with open(self.conffile, 'w') as c:
                self.config.write(c)
                return True
        except Exception as e:
            self.logger.exception(e)
            return False

    def getTel(self, data):
        """
        If the received string is a valid telegram and the CRC is
        correct, then return the telegram.
        """
        try:
            mydata = data[:-2]  # remove end of line characters
            self.recv_crc = int(mydata[-2:], 16)  # extract CRC,
            self.payload = mydata[:-2]  # payload without CRC
            self.comp_crc = self.crc8_function(self.payload)

            if self.recv_crc == self.comp_crc:
                cmd = self.payload[0]
                dsxid = int(self.payload[1], 16)
                array = self.payload[2:]
                args = []
                i = 0
                if array:
                    while i < len(array):
                        n = int(array[i:i+2], 16)
                        i = i+2
                        args.append(n)

                    Tel = dSTel(cmd, dsxid, args)
                    return Tel
                else:
                    return None
            else:
                self.logger.warning("CRC error in dstiny rx chain: %s" % data)
                return None
        except Exception as e:
            self.logger.exception(e)
            return None

    def read(self):
        s = self.port.ser.readline()
        return s

    def write_read_verify(self, Tel):
        """
        Writes a telegram. Waits for the OK answer. If no answer come,
        retry. The received answer telegram is verified.
        """
        counter = 0
        s = ''
        self.write(Tel)  # send telegram
        s = self.read()
        while not s and counter < self.NTRIES:
            self.write(Tel)  # retry
            s = self.read()
            counter = counter+1

        if not s and counter >= self.NTRIES:
            self.logger.warning("No response received")
            return None
        else:
            tel = self.getTel(s)
            if tel:
                self.logger.info("[pc <- dstiny]\t[answer]\t"+tel.get()[:-2])
                return tel
            else:
                return None

    def write(self, Tel):
        s = Tel.get()
        self.logger.info("[pc -> dstiny]\t[write]\t"+s.encode('utf-8')[:-2])
        self.port.ser.write(s.encode('utf-8'))

    def readWord(self, bank, offset, dSidx):
        sendTel = dSTel('c', dSidx, [0x03, bank, offset, 0x00, 0x00])
        recvTel = self.write_read_verify(sendTel)
        return recvTel

    def register(self, DSMS):
        """
        Send registration command
        """
        registerTel = dSTel('c', 0, [0x02, 0x40, 0x04, 0x01, DSMS])
        ans = self.write_read_verify(registerTel)
        return ans

    def joinGroup(self, dSidx, group, delete=False):
        if group <= 15:
            addr = 0x10
            base = 0
        elif group >= 16 and group <= 31:
            addr = 0x12
            base = 16
        elif group >= 32 and group <= 47:
            addr = 0x14
            base = 32
        elif group >= 48 and group <= 63:
            addr = 0x16
            base = 48
        else:
            return None

        shift = max(group-base, 0)
        mask = (1 << shift)

        rword = self.readWord(0x01, addr, dSidx)
        if rword:
            group_id = rword.args[3] | (rword.args[4] << 8)
            if delete:  # delete the group
                mask = group_id & ~mask
            else:  # add the group: default behavior
                mask = group_id | mask

            mask_l = mask & 0xFF
            mask_h = (mask >> 8) & 0xFF

            #self.logger.info("mask_l:%d\tmask_h:%d" % (mask_l,mask_h))
            groupTel = dSTel('c', dSidx, [0x02, 0x01, addr, mask_l, mask_h])
            # groupTel=dSTel('c',dSidx,[0x02,0x01,addr,0x01,0x05])
            #print groupTel.get()
            ans = self.write_read_verify(groupTel)

            return ans
        else:
            return None

    def writeByte(self, dSidx, bank, offset, value):
        Tel = dSTel('c', dSidx, [0x00, bank, offset, value, 0x00])
        ans = self.write_read_verify(Tel)
        if ans:
            return ans
        else:
            return None

    def activateDSCommands(self, dSidx, DSCMD):
        """
        DSCMD (8 Bit) 0 = do not transfer telegrams (default) 1 =
        transfer telegrams for this device and activated group within
        this zone 2 = transfer telegrams for this device and all
        groups within this zone
        """
        Tel = dSTel('c', dSidx, [0x00, 0x03, 0x32, DSCMD, 0x00])
        ans = self.write_read_verify(Tel)
        if ans:
            return ans
        else:
            return None

    def PTP_reply(self, recvTel, value):
        """
        Replies to PassThrough telegram recvTel with value
        """
        value_hi = (value >> 8) & 0xFF
        value_lo = value & 0xFF
        bank = recvTel.args[1]
        addr = recvTel.args[2]
        Tel = dSTel('q', recvTel.dSidx, [0x03, bank, addr, value_lo, value_hi])
        ans = self.write_read_verify(Tel)
        if ans:
            return ans
        else:
            return None

    def writeStatusValue(self, dSidx, sensorID, value):
        value_hi = (value >> 8) & 0xFF
        value_lo = value & 0xFF
        Tel = dSTel('c', dSidx, [0x06, sensorID, 0x00, value_lo, value_hi])
        ans = self.write_read_verify(Tel)
        if ans:
            return ans
        else:
            return None

    def genStatusPollEvent(self, dSidx, sensorID):
        Tel = dSTel('g', dSidx, [0x07, sensorID, 0x00])
        ans = self.write_read_verify(Tel)
        if ans.cmdch == 'e':
            return ans
        else:
            return None

    def parse_dSCommand(self, Tel):
        cmdch = Tel.cmdch
        dSidx = Tel.dSidx

        if cmdch == 'p':  # pass through commands
            """
            Memory map for the pass through registers (bank 0x7F, registers 0-0xFF)

            Registers 0x00 - 0x0F -> reserved for control
            Registers 0x10 - 0x1F -> reserved for configuration

            0x10 -> Configuration scene 0
            0x11 -> Configuration scene 1
            0x12 -> Configuration scene 2
            0x13 -> Configuration scene 3
            0x14 -> Configuration scene 4

            0x15 -> Configuration scene 5
            0x16 -> Configuration scene 6
            0x17 -> Configuration scene 7
            0x18 -> Configuration scene 8
            0x19 -> Configuration scene 9

            0x1A -> Configuration scene 20 ...
            """

            cmdcd = Tel.args[0]
            bank = Tel.args[1]
            reg = Tel.args[2]

            # check the memory map
            if cmdcd == 0x03:  # read
                if dSidx == 1:  # FAN & FLAP
                    if reg in fan_scenes_regs.values():  # scenes 0-4 -> fan
                        value = 0x0000  # 16-bit answer
                        low = self.getConfSceneLevel(
                            'Fan_Flap', reg)  # lower part
                        high = self.getConfSceneLevel(
                            'Fan_Flap', reg+1)  # upper part
                        value = low | (high << 8)
                        self.PTP_reply(Tel, value)

                    elif reg in flap_scenes_regs.values():  # scenes 20-24 -> flap
                        value = 0x0000  # 16-bit answer
                        low = self.getConfSceneLevel(
                            'Fan_Flap', reg)  # lower part
                        high = self.getConfSceneLevel(
                            'Fan_Flap', reg+1)  # upper part
                        if high >= 0:
                            value = low | (high << 8)
                        else:
                            value = low

                        self.PTP_reply(Tel, value)

            elif cmdcd == 0x02:  # write
                value = Tel.args[3]
                if dSidx == 1:  # FAN & FLAP
                    if reg in fan_scenes_regs.values():  # scenes 0-4 -> fan
                        self.setConfSceneLevel('Fan_Flap', reg, value)
                        self.logger.info(
                            "Configured ExHood->Fan register:%d to level:%d%%" % (reg, value))

                    elif reg in flap_scenes_regs.values():  # scenes 20-24 -> flap
                        self.setConfSceneLevel('Fan_Flap', reg, value)
                        self.logger.info(
                            "Configured ExHood->Flap register:%d to level:%d%%" % (reg, value))

                    # success=mivune_ctr.set_exhaust_percent(value)

        elif cmdch == 'i':  # scene
            addr_lo = Tel.args[0]
            addr_hi = Tel.args[1]
            addr = (addr_hi << 8) | addr_lo
            cmd = Tel.args[2]
            cmd_val_lo = Tel.args[3]
            cmd_val_hi = Tel.args[4]
            cmd_val = (cmd_val_hi << 8) | cmd_val_lo

            addr1 = (addr >> 6)  # 10 MSB

            if cmd == 0x08 and (cmd_val >> 8) & 0xFF == 0x02:
                scene = cmd_val & 0xFF
                if addr1 <= 15:  # addr1 is the zone and addr2 is the group
                    addr2 = addr & 0x3F  # group
                    self.logger.info(
                        "Group scene: dsidx:"+str(dSidx)+"\tscene:"+str(scene)+"\tgroup:"+str(addr2))

                    if dSidx == EXHOOD_LIGHT_dSxid:  # Light
                        self.logger.info("Got light scene")
                        if scene in light_scenes.keys():
                            value = light_scenes[scene]
                            success = self.mivune_ctr.setLightIntensity(
                                value)  # Fan

                else:
                    self.logger.info(
                        "Individual addressing: dsidx:"+str(dSidx)
                        + "\tscene:"+str(scene))
                    # Implement the reaction to scenes only here
                    # React to scenes only when the device is addressed 
                    # as single device

                    # Process scene
                    if dSidx == EXHOOD_FAN_FLAP_dSxid:  # Extractor hood -> FAN and FLAP
                        if scene in fan_scenes_regs.keys():  # fan
                            reg = fan_scenes_regs[scene]
                            level = self.getConfSceneLevel("Fan_Flap", reg)
                            if level >= 0:
                                self.logger.info(
                                    "Retrieved fan scene:%d -> level:%d %%"
                                    % (scene, level))

                                # update the level only if necessary,
                                # otherwise the mivune system will not
                                # generate an event an the lock will
                                # remain true.
                                if level !=\
                                   self.mivune_ctr.get_fan_current_level():
                                    success = self.mivune_ctr.setExhaustAir(
                                        level)  # Fan
                                    if success:
                                        self.logger.info(
                                            "Scene send to mivune controller")
                                        # indicates to the mivune controller,
                                        # that the next event is not meant to
                                        # be forwarded to the dSS
                                        self.mivune_ctr.set_lock(True)

                        elif scene in flap_scenes_regs.keys():
                            reg = flap_scenes_regs[scene]
                            level = self.getConfSceneLevel("Fan_Flap", reg)
                            if level >= 0:

                                self.logger.info(
                                    "Retrieved flap scene:%d -> level:%d %%" %
                                    (scene, level))

                                # update the level only if necessary,
                                # otherwise the mivune system will not
                                # generate an event an the lock will
                                # remain true.

                                self.logger.info("level:%d\tcurrent_level:%d" 
                                    % (level, 
                                       self.mivune_ctr.get_flap_current_level()))

                                if level !=\
                                   self.mivune_ctr.get_flap_current_level():
                                    success = self.mivune_ctr.setSupplyAir(
                                        level)  # Flap
                                    if success:
                                        # indicates to the mivune controller,
                                        # that the next event is not meant to
                                        # be forwarded to the dSS
                                        self.mivune_ctr.set_lock(True)
