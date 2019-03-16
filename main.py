"""Bridge translating messages between ds and mvune

This module implements two processes, one listening to the ds system
and forwarding the incoming messages to the mvune system, and one doing the
same forwarding in the other direction.
"""

import logging
from optparse import OptionParser
import Queue
import requests
import sys
import time
from threading import Thread

import dstiny
import mvune
from serial_port import serial_port


class Event:
    """ Events exchanged between threads

    Define the events to be transmitted by the dstiny. This class is used
    to exchange events between different threads.
    """

    def __init__(self, dSidx, value, sid, event_type):
        self.dSidx = dSidx
        self.value = value
        self.type = event_type  # {"Status","Binary"}
        self.SID = sid

    def __str__(self):
        return "dSidx:%d\tvalue:(%d,%d) (%04X)\ttype:%s"\
            % (self.dSidx, (self.value >> 8) & 0xFF,
                self.value & 0xFF, self.value, self.type)


def mvune_thread(mvune_ctr, _q):
    logging.info("Getting object model and valid services ids")
    mvune_ctr.get_objectModel()

    logging.info("Starting long polling thread")
    logging.info("mvune session id:\t"+mvune_ctr.sessionId)
    r = requests.get(mvune_ctr.longpolling)

    while True:
        if r.json():
            json_obj = r.json()
            success, fan, flap, window = mvune_ctr.decodeEvent(json_obj)

            if success:
                # if the controller is locked, it means that the
                # content of this event is not meant to be transferred
                # to the dSS. The message is the answer to a control
                # action
                if mvune_ctr.get_lock():
                    logging.info(
                        "This event is forwarded to the dSS only\
                            for visualization purposes")
                    index = dstiny.DS_POLL_STATUS_INFO+1  # different index

                    logging.info(
                        "Received flap value: %d, fan value:%d" % (flap, fan))
                    if fan >= 0:
                        mvune_ctr.set_fan_current_level(fan)

                    if flap >= 0:
                        mvune_ctr.set_flap_current_level(flap)

                    status = (fan << 8) | flap
                    e = Event(dstiny.EXHOOD_FAN_FLAP_dSxid, status, index,
                              "Status")  # see dstiny.py header
                    if not _q.full():
                        _q.put(e)

                else:
                    index = dstiny.DS_POLL_STATUS_INFO
                    if fan >= 0:
                        mvune_ctr.set_fan_current_level(fan)

                    if fan >= 0:
                        if flap < 0:
                            flap = 0
                        logging.info(
                            "Received flap value: %d, fan value:%d" % (flap, fan))
                        status = (fan << 8) | flap
                        e = Event(dstiny.EXHOOD_FAN_FLAP_dSxid, status,
                                  index, "Status")  # see dstiny.py header
                        if not _q.full():
                            _q.put(e)

                if window >= 0:  # if a change in window-conctact was received
                    logging.info("Received window value: %d" % window)
                    value = window & 0xFF
                    e = Event(dstiny.EXHOOD_FLAP_WINDOW_CONTACT_dSxid,
                              value, index, "Status")
                    if not _q.full():
                        _q.put(e)

            # unlock and relaunch controller
            mvune_ctr.set_lock(False)

            # re-launch long-polling request
            r = requests.get(mvune_ctr.longpolling)

        time.sleep(0.1)


def dstiny_thread(serport, mvune_ctr, logfile, conffile, _q):
    DSMS = 0x07  # register devices 0 and 1, and 2
    heartbeat = 30  # in seconds

    # DSCMD (8 Bit) 0 = do not transfer telegrams (default) 1 =
    # transfer telegrams for this device and activated group within
    # this zone 2 = transfer telegrams for this device and all
    # groups within this zone
    DSCMD = 1
##############################

    tiny = dstiny.dstiny(serport, mvune_ctr, logfile, conffile,)
    FSM_state = "dSINIT"

    logging.info("Starting dStiny thread")

    prev_telegram = ""

    while True:
        if FSM_state == "dSINIT":
            s = tiny.read()
            if s:
                tel = tiny.getTel(s)
                if tel:
                    if tel.cmdch == 's' and tel.args[0] == 0x00:
                        # configure heartbeat
                        ans = tiny.writeByte(0, 0x03, 0x3A, heartbeat)

                        # Register dstiny subdevices. The dstiny can
                        # represent several indepedent logical devices
                        ans = tiny.joinGroup(
                            dstiny.EXHOOD_FAN_FLAP_dSxid, 
                            dstiny.DS_GROUP_VENTILATION)  # see dstiny.py

                        ans = tiny.joinGroup(
                            dstiny.EXHOOD_FLAP_WINDOW_CONTACT_dSxid, 
                            dstiny.DS_GROUP_VENTILATION)  # see dstiny.py

                        # configure light
                        # ans=tiny.writeByte(0,0x03,0x01,0x0F) #set LTNUMGRP to 0x15
                        # ans=tiny.writeByte(1,0x03,0x01,0x0F) #set LTNUMGRP to 0x15
                        # set LTNUMGRP to 0x15 (1=light, 5=room push button)
                        ans = tiny.writeByte(
                            dstiny.EXHOOD_LIGHT_dSxid, 0x03, 0x01, 0x15)
                        ans = tiny.joinGroup(
                            dstiny.EXHOOD_LIGHT_dSxid, 
                            dstiny.DS_GROUP_LIGHT)  # see dstiny.py
                        # set output to switched
                        ans = tiny.writeByte(
                            dstiny.EXHOOD_LIGHT_dSxid, 0x03, 0x00, 0x10)

                        tiny.activateDSCommands(dstiny.EXHOOD_LIGHT_dSxid, 
                                                DSCMD)
                        tiny.activateDSCommands(dstiny.EXHOOD_FAN_FLAP_dSxid, 
                                                DSCMD)
                        ans = tiny.register(DSMS)

                    elif tel.cmdch == 's' and tel.args[0] == 0x20:
                        FSM_state = "dSONLINE"

                    logging.info(
                        "[pc <- dstiny]\t[telegram]\t" + tel.get()[:-2])

        elif FSM_state == "RESTART":
            s = tiny.read()
            if s:
                tel = tiny.getTel(s)
                if tel:
                    if tel.cmdch == 's' and tel.args[0] == 0x00:
                        ans = tiny.register(DSMS)
                        if not ans:
                            FSM_state = "dSINIT"
                    elif tel.cmdch == 's' and tel.args[0] == 0x20:
                        FSM_state = "dSONLINE"

        elif FSM_state == "dSONLINE":
            s = tiny.read()

            if s:
                tel = tiny.getTel(s)
                if tel:
                    if tel.get()[:-2] != prev_telegram:  # log only updates
                        logging.info(
                            "[pc <- dstiny]\t[telegram]\t"+tel.get()[:-2])
                        prev_telegram = tel.get()[:-2]
                    if tel.cmdch == 's' and tel.args[0] == 0x00:
                        FSM_state = "RESTART"
                        logging.info("Restarting dstiny")
                    else:
                        tiny.parse_dSCommand(tel)
            else:
                # Check whether a message from the long polling
                # process has arrived
                while not _q.empty():  # check that the queue isn't empty
                    e = _q.get()  # print the item from the queue
                    logging.info("Tranmitting event:%s" % e)
                    if e.type == "Status":
                        tiny.writeStatusValue(
                            e.dSidx, dstiny.DS_STATUS_VALUES_START
                            + e.SID, e.value)
                        tiny.genStatusPollEvent(e.dSidx, e.SID)
                    _q.task_done()  # specify that you are done with the item552
                    # restrict the interval between consecutive events
                    time.sleep(5)

        time.sleep(0.1)


if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-c", "--connection", dest="address",
                      help="mvune server address", default="127.0.0.1")

    parser.add_option("-p", "--port", dest="serial_port",
                      help="serial port", default="/dev/ttyS3")

    parser.add_option("-X", "--extractor-hood-service", 
                      dest="extractor_hood_service",
                      help="mvune extractor hood service", 
                      default="integrierter Haubenluefter")

    parser.add_option("-L", "--light-service", dest="light_service",
                      help="mvune light service", default="Licht1")

    parser.add_option("-W", "--window-contact-service", 
                      dest="window_contact_service",
                      help="mvune window contact service", 
                      default="Zuluft FKS")

    parser.add_option("-l", "--log-file", dest="logfile",
                      help="log file", default="__tiny.log")

    parser.add_option("-s", "--scene-conf-file", dest="conffile",
                      help="scenes configuration file", 
                      default="__scenes.conf")

    (options, args) = parser.parse_args()

    try:
        p0n = options.serial_port
        p0 = serial_port(port=p0n, baudrate=19200)

        # set up logging to file - see previous section for more details
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s\
                             %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            filename=options.logfile,
                            filemode='a')
        # define a Handler which writes INFO messages or higher
        # to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        # set a format which is simpler for console use
        formatter = logging.Formatter(
            '%(name)-12s: %(levelname)-8s %(message)s')
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger('').addHandler(console)

    except Exception, e:
        logging.error(e)
        sys.exit(-1)

    try:
        mvune_ctr = mvune.Mvune(options.address,
                                options.extractor_hood_service,
                                options.window_contact_service,
                                options.light_service, options.logfile)

        q = Queue.Queue()
        t1 = Thread(target=dstiny_thread, args=(
            p0, mvune_ctr, options.logfile, options.conffile, q,))
        t2 = Thread(target=mvune_thread, args=(mvune_ctr, q,))
        t1.start()
        t2.start()
        q.join()

    except Exception, e:
        logging.error("Unable to start thread")
        logging.error(e)

    sys.exit(0)
