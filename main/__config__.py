import bootloader
from collections import OrderedDict
import os
import ulogging


class Config:

    def __init__(self):
        """
        Variable saved in flash.
        """
        self.boot = bootloader.Bootloader('https://github.com/lipic/wattrouter', "")
        self.data = OrderedDict()
        self.data['txt,ACTUAL SW VERSION'] = '0'

        self.data['sw,AUTOMATIC UPDATE'] = '1'
        self.data['sw,TESTING SOFTWARE'] = '0'
        self.data['sw,Wi-Fi AP'] = '1'
        self.data['sw,AC IN ACTIVE: HIGH'] = '0'

        self.data['bt,RESET PV-ROUTER'] = '0'
        self.data['btn,BOOST-MODE'] = '0'

        self.data['in,OVERFLOW-OFFSET'] = '100'
        self.data['in,TUV-VOLUME'] = '200'
        self.data['in,TUV-POWER'] = '2200'
        self.data['in,NIGHT-BOOST'] = '64800'
        self.data['in,NIGHT-TEMPERATURE'] = '55'
        self.data['in,MORNING-BOOST'] = '21600'
        self.data['in,MORNING-TEMPERATURE'] = '40'
        self.data['in,BOOST-TIMEOUT'] = '120'
        self.data['in,TIME-ZONE'] = '2'
        self.data['in,STOP-SOC'] = '70'

        self.data['in,POWER-RELAY'] = '1000'
        self.data['in,TIMEOUT-RELAY'] = '10'
        self.data['in,RELAY-LOAD'] = '2000'

        self.data['bti,INVERTER-TYPE'] = '0'
        self.data['INVERTER_IP_ADDR'] = '0'


        self.data['BOOST'] = '0'
        self.data['ERRORS'] = '0'
        self.data['ID'] = '0'
        self.data['TYPE'] = '3'

        self.logger = ulogging.getLogger("__config__")
        if int(self.data['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

        self.setting_profile = 'setting.dat'
        self.handle_configure('txt,ACTUAL SW VERSION', self.boot.get_version(""))

    # Update self.config from setting.dat and return dict(config)
    def get_config(self) -> None:
        setting = {}
        try:
            setting = self.read_setting()
        except OSError:
            setting = {}

        if len(setting) != len(self.data):
            with open(self.setting_profile, 'w') as file:
                file.write('')
                file.close()

            for i in self.data:
                if i in setting:
                    if self.data[i] != setting[i]:
                        self.data[i] = setting[i]
            setting = {}

        for i in self.data:
            if i in setting:
                if self.data[i] != setting[i]:
                    self.data[i] = setting[i]
            else:
                setting[i] = self.data[i]
                self.write_setting(setting)

        if self.data['ID'] == '0':
            _id = bytearray(os.urandom(4))
            rand_id = ''
            for i in range(0, len(_id)):
                rand_id += str((int(_id[i])))
            self.data['ID'] = rand_id[-5:]
            self.handle_configure('ID', self.data['ID'])

        return self.data

    # Update self.config. Write new value to self.config and to file setting.dat
    def handle_configure(self, variable: str, value: str) -> bool:
        try:
            if variable == 'bt,RESET PV-ROUTER':
                from machine import reset
                reset()

            if len(variable) > 0:
                try:
                    setting = self.read_setting()
                except OSError:
                    setting: dict = {}

                if setting[variable] != value:
                    setting[variable] = value
                    self.write_setting(setting)
                    self.get_config()
                    return True
            else:
                return False
        except Exception as e:
            self.logger.error("handle_configure exception: {}.".format(e))
            return False

    def read_setting(self) -> dict:
        with open(self.setting_profile) as f:
            lines: list[str] = f.readlines()
        setting: dict = {}
        try:
            for line in lines:
                variable, value = line.strip("\n").split(";")
                setting[variable] = value
            return setting

        except Exception as e:
            self.logger.error("read_setting exception: {}.".format(e))
            self.write_setting(self.data)
            return self.data

    # method for write data to file.dat
    def write_setting(self, setting: OrderedDict[str, str]) -> None:
        lines: list[str] = []
        for variable, value in setting.items():
            lines.append("%s;%s\n" % (variable, value))
        with open(self.setting_profile, "w") as f:
            f.write(''.join(lines))
