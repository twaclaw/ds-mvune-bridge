"""Implements REST interface for the mvune system

Author: Diego Sandoval
Date: 07.06.2017
"""
import logging
import requests


class Mvune:
    """
    Mvune controller

    `exhood` and `light` are the names of the extractor hood and light
    devices, respectively.
    """

    def __init__(self, url, exhood_service, window_contact_service,
                 light_service, logfile):

        self.server = "http://"+url
        self.sessionId = None
        self.objectModel = None
        self.light_service = light_service
        self.exhood_service = exhood_service
        self.window_contact_service = window_contact_service
        self.registered_services = {}
        self.logger = logging.getLogger(logfile)
        self.lock = False
        self.flap_current_level = 0
        self.fan_current_level = 0

    def set_fan_current_level(self, level):
        self.fan_current_level = level

    def set_flap_current_level(self, level):
        self.flap_current_level = level

    def get_fan_current_level(self):
        return self.fan_current_level

    def get_flap_current_level(self):
        return self.flap_current_level

    def set_lock(self, status):
        self.lock = status

    def get_lock(self):
        return self.lock

    def get_objectModel(self):
        """ Get session Id and services
        """
        url = self.server+"/json/?action=getObjectModelAndAjaxSessionId"
        r = requests.get(url)
        if r.json():
            json = r.json()
            try:
                self.sessionId = json["ajaxSessionId"]
                self.longpolling = self.server + \
                    "/json/?action=waitForEvents&ajaxSessionId=%s" % (
                        self.sessionId)
            except Exception, e:
                self.logger.error("Not able to get SessionId")
                self.logger.error(e)
                self.sessionId = None
                self.longpolling = None

            try:
                self.objectModel = json["objectModel"]
            except Exception, e:
                self.logger.error(e)
                self.logger.error("Not able to get objectModel")
                self.objectModel = None

            if self.objectModel:
                try:
                    self.services_list = []
                    for i in self.objectModel["devices"]:
                        if self.objectModel["devices"][i]["name"] ==\
                           self.light_service\
                           or self.objectModel["devices"][i]["name"] == \
                           self.exhood_service\
                           or self.objectModel["devices"][i]["name"] == \
                           self.window_contact_service:
                            serviceIds =\
                                self.objectModel["devices"][i]["serviceIds"]
                            name = self.objectModel["devices"][i]["name"]
                            self.services_list.append(
                                {"name": name, "serviceIds": serviceIds})
                except Exception, e:
                    self.logger.error("Not able to get objectModel.devices")
                    self.logger.error(e)
                    self.services_list = []

            # create dictionary
            if self.objectModel and len(self.services_list) > 0:
                try:
                    self.services = self.objectModel["services"]
                    for s_dict in self.services_list:
                        s = s_dict["serviceIds"]
                        name = s_dict["name"]
                        for ss in s:
                            # self.registered_services[self.services[ss]["name"]]=ss
                            name_service = self.services[ss]["name"]
                            if name == self.exhood_service:
                                name_service = name_service + "_haube"
                            self.registered_services[ss] = [name_service]
                except Exception, e:
                    self.logger.error(e)

            self.logger.info("Registered services:" +
                             str(self.registered_services))

    def setExhaustAir(self, value):
        """ Sets the exhood fan level
        ExhaustAirDeviceService service -> Controls the exhood FAN
        """
        try:
            for key in self.registered_services.keys():
                if u'exhaustAirDeviceService_haube' in\
                     self.registered_services[key]:
                    serviceId = key
                    break

        except Exception, e:
            self.logger.error("Service Id not registered")
            self.logger.error(e)
        try:
            url = self.server + \
                "/json/?event=objectmodel.MethodCall&arg[]=%s&arg[]=\
                    setExhaustAir&arg[]=%d&ajaxSessionId=%s&action=sendEvent"\
                    % (serviceId, value, self.sessionId)
            r = requests.get(url)
            if r.json():
                return r.json()["success"]
            else:
                return False
        except Exception, e:
            self.logger.error("Request could not be processed")
            self.logger.error(e)

    def setSupplyAir(self, value):
        """ Controls the exhood flap
        SupplyAirDeviceService service -> controls the exhood FLAP
        """
        try:
            for key in self.registered_services.keys():
                if u'supplyAirDeviceService_haube' in\
                     self.registered_services[key]:
                    serviceId = key
                    break

        except Exception, e:
            self.logger.error("Service Id not registered")
            self.logger.error(e)
        try:
            url = self.server + \
                "/json/?event=objectmodel.MethodCall&arg[]=%s&arg[]=\
                    setSupplyAir&arg[]=%d&ajaxSessionId=%s&action=sendEvent"\
                         % (serviceId, value, self.sessionId)
            r = requests.get(url)
            if r.json():
                return r.json()["success"]
            else:
                return False
        except Exception, e:
            self.logger.error("Request could not be processed")
            self.logger.error(e)

    def setLightIntensity(self, value):
        """
        Method for the     LightingDeviceService service
        """
        try:
            for key in self.registered_services.keys():
                if u'lightingDeviceService' in self.registered_services[key]:
                    serviceId = key
                    break
        except Exception, e:
            self.logger.error("Service Id not registered")
            self.logger.error(e)
        try:
            url = self.server + \
                "/json/?event=objectmodel.MethodCall&arg[]=%s&arg[]=\
                    setIntensity&arg[]=%f&ajaxSessionId=%s&action=sendEvent"\
                        % (serviceId, value, self.sessionId)
            r = requests.get(url)
            if r.json():
                return r.json()["success"]
            else:
                return False
        except Exception, e:
            self.logger.error("Request could not be processed")
            self.logger.error(e)

    def setIntensitySceneValue(self, value):
        """ Sets light value
        
        LightingDeviceService service
        """
        try:
            # associated service
            serviceId = self.registered_sevices["lightingDeviceService"]
        except Exception, e:
            self.logger.error("Service Id not registered")
            self.logger.error(e)
        try:
            url = self.server + \
                "/json/?event=objectmodel.MethodCall&arg[]=%s&arg[]=\
                    setIntensitySceneValue&arg[]=%f&ajaxSessionId=%s&action=sendEvent"\
                        % (serviceId, value, self.sessionId)
            r = requests.get(url)
            if r.json():
                return r.json()["success"]
            else:
                return False
        except Exception, e:
            self.logger.error("Request could not be processed")
            self.logger.error(e)

    def decodeEvent(self, json_obj):
        """ Decodes incoming events

        Evaluates events coming from the mvune system (long polling).
        This function returns the overall status, and values for the
        fan, flap, and window-contact
        """

        # hardcoded actions list
        FAN = 'exhaustAirFromField'
        FLAP = 'supplyAirFromField'
        WINDOW = 'maxSupplyAir'

        INVALID_VALUE = -1
        fan_value = INVALID_VALUE
        flap_value = INVALID_VALUE
        window_value = INVALID_VALUE

        try:
            events = json_obj["events"]  # list of events
            for event in events:
                eventName = event["eventName"]
                if eventName == 'notification.OMValueChange':
                    changedObjects = event["changedObjects"]
                    for service in self.registered_services:
                        key = service  # self.registered_services[service]
                        if key in changedObjects:
                            self.logger.info(
                                "Received field from %s service" % service)
                            msg = changedObjects[key]
                            if FAN in msg.keys():
                                fan_value = msg[FAN]
                            if FLAP in msg.keys():
                                flap_value = msg[FLAP]
                            if WINDOW in msg.keys():
                                window_value = msg[WINDOW]

        except Exception, e:
            self.logger.error("Error decoding mvune json  event")
            self.logger.error(e)
            return False, fan_value, flap_value, window_value

        return True, fan_value, flap_value, window_value
