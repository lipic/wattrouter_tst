import ujson as json
import time
from machine import Pin, UART
from gc import collect, mem_free
import ulogging
from main.regulation import Regulation
from collections import OrderedDict


class Wattmeter:

    def __init__(self, wattmeter_interface, config: OrderedDict[str, str]):
        self.relay: Pin = Pin(19, Pin.OUT)
        self.wattmeter_interface = wattmeter_interface
        self.data_layer: DataLayer = DataLayer()
        self.daily_consumption: str = 'daily_consumption.dat'
        self.time_init: bool = False
        self.time_offset: bool = False
        self.last_minute: int = 0
        self.last_hour: int = 0
        self.last_day: int = 0
        self.last_month: int = 0
        self.last_year: int = 0
        self.average_power: list = []
        self.start_up_time: int = 0
        self.config = config
        self.data_layer.data['ID'] = self.config.data['ID']
        self.logger = ulogging.getLogger("Wattmeter")

        self.regulation = Regulation(wattmeter=self, config=self.config)

        if int(self.config.data['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

        self.file_handler = FileHandler(debug=int(self.config.data['sw,TESTING SOFTWARE']))

    async def wattmeter_handler(self, inverter_data=None) -> None:

        if (self.time_offset is False) and self.time_init:
            self.start_up_time = time.time()
            self.last_minute = int(time.localtime()[4])
            self.last_day = int(time.localtime()[2])
            self.last_month = int(time.localtime()[1])
            self.last_year = int(time.localtime()[0])
            self.data_layer.data['D'] = self.file_handler.read_data(self.daily_consumption)
            self.data_layer.data["M"] = self.file_handler.get_monthly_energy(self.daily_consumption)
            self.time_offset = True

        self.data_layer.data['RUN_TIME'] = time.time() - self.start_up_time
        curent_year: str = str(time.localtime()[0])[-2:]
        self.data_layer.data['WATTMETER_TIME'] = (
            "{0:02}.{1:02}.{2}  {3:02}:{4:02}:{5:02}".format(time.localtime()[2], time.localtime()[1], curent_year,
                                                             time.localtime()[3], time.localtime()[4],
                                                             time.localtime()[5]))

        await self.__read_wattmeter_data(6002, 22)
        battery_soc = inverter_data['soc'] if inverter_data is not None else None
        self.regulation.run(hour=time.localtime()[3], minute=time.localtime()[4], power=self.data_layer.data['P_REGULATION'], soc=battery_soc)

        if (self.last_minute != int(time.localtime()[4])) and self.time_init:
            minute_energy: int = self.data_layer.data['E1_P_min'] - self.data_layer.data['E1_N_min']
            if len(self.data_layer.data["Pm"]) < 61:
                self.data_layer.data["Pm"].append(minute_energy * 6)
            else:
                self.data_layer.data["Pm"] = self.data_layer.data["Pm"][1:]
                self.data_layer.data["Pm"].append(minute_energy * 6)

            self.data_layer.data["Pm"][0] = len(self.data_layer.data["Pm"])

            async with self.wattmeter_interface as w:
                await w.write_wattmeter_register(100, [1])

            self.last_minute = int(time.localtime()[4])

        if self.time_init:
            if self.last_hour != int(time.localtime()[3]):

                async with self.wattmeter_interface as w:
                    await w.write_wattmeter_register(101, [1])

                self.last_hour = int(time.localtime()[3])
                if len(self.data_layer.data["Es"]) < 97:
                    self.data_layer.data["Es"].append(self.last_hour)
                    self.data_layer.data["Es"].append(self.data_layer.data['E1_P_hour'])
                    self.data_layer.data["Es"].append(self.data_layer.data['E_TUV_hour'])
                    self.data_layer.data["Es"].append(self.data_layer.data['HDO'])
                else:
                    self.data_layer.data["Es"] = self.data_layer.data["Es"][4:]
                    self.data_layer.data["Es"].append(self.last_hour)
                    self.data_layer.data["Es"].append(self.data_layer.data['E1_P_hour'])
                    self.data_layer.data["Es"].append(self.data_layer.data['E_TUV_hour'])
                    self.data_layer.data["Es"].append(self.data_layer.data['HDO'])

                self.data_layer.data["Es"][0] = len(self.data_layer.data["Es"])

            else:
                if len(self.data_layer.data["Es"]) < 97:
                    self.data_layer.data["Es"][len(self.data_layer.data["Es"]) - 3] = self.data_layer.data['E1_P_hour']
                    self.data_layer.data["Es"][len(self.data_layer.data["Es"]) - 2] = self.data_layer.data['E_TUV_hour']
                    self.data_layer.data["Es"][len(self.data_layer.data["Es"]) - 1] = self.data_layer.data['HDO']
                else:
                    self.data_layer.data["Es"][94] = self.data_layer.data['E1_P_hour']
                    self.data_layer.data["Es"][95] = self.data_layer.data['E_TUV_hour']
                    self.data_layer.data["Es"][96] = self.data_layer.data['HDO']

        if (self.last_day != int(time.localtime()[2])) and self.time_init and self.time_offset:
            day: dict = {("{0:02}/{1:02}/{2}".format(self.last_month, self.last_day, str(self.last_year)[-2:])): [
                self.data_layer.data["E1_P_day"], self.data_layer.data["E1_N_day"], self.data_layer.data["E_TUV_day"]]}
            async with self.wattmeter_interface as w:
                await w.write_wattmeter_register(102, [1])

            self.last_year = int(time.localtime()[0])
            self.last_month = int(time.localtime()[1])
            self.last_day = int(time.localtime()[2])
            self.file_handler.write_data(self.daily_consumption, day)
            self.data_layer.data["D"] = self.file_handler.read_data(self.daily_consumption)
            self.data_layer.data["M"] = self.file_handler.get_monthly_energy(self.daily_consumption)

    async def __read_wattmeter_data(self, reg: int, length: int) -> None:

        try:
            async with self.wattmeter_interface as w:
                receive_data = await w.read_wattmeter_register(reg, length)

            if (len(receive_data) >= length * 2) and (reg == 6002):

                hdo_input: int = int(((receive_data[0]) << 8) | (receive_data[1]))
                if hdo_input == 1 and '1' == self.config.data['sw,AC IN ACTIVE: HIGH']:
                    self.data_layer.data['HDO'] = 1
                elif hdo_input == 0 and '0' == self.config.data['sw,AC IN ACTIVE: HIGH']:
                    self.data_layer.data['HDO'] = 1
                else:
                    self.data_layer.data['HDO'] = 0

                self.data_layer.data['I1'] = int(((receive_data[2]) << 8) | (receive_data[3]))

                self.average_power.append(int(((receive_data[4]) << 8) | (receive_data[5])))
                if len(self.average_power) > 5:
                    self.average_power = self.average_power[1:]
                actual_power: int = 0
                count: int = 0
                for power in self.average_power:
                    actual_power += (power - 65536) if power > 32767 else power
                    count += 1
                self.data_layer.data['P1'] = int(actual_power / count)
                self.data_layer.data['U1'] = int(((receive_data[6]) << 8) | (receive_data[7]))
                self.data_layer.data['E1_P_min'] = int(((receive_data[8]) << 8) | (receive_data[9]))
                self.data_layer.data['E1_N_min'] = int(((receive_data[10]) << 8) | (receive_data[11]))
                self.data_layer.data['E1_P_hour'] = int(((receive_data[12]) << 8) | (receive_data[13]))
                self.data_layer.data['E1_N_hour'] = int(((receive_data[14]) << 8) | (receive_data[15]))
                self.data_layer.data['E1_P_day'] = int(((receive_data[16]) << 8) | (receive_data[17]))
                self.data_layer.data['E1_N_day'] = int(((receive_data[18]) << 8) | (receive_data[19]))
                self.data_layer.data['E1_P'] = int(
                    (receive_data[22] << 24) | (receive_data[23] << 16) | (receive_data[20] << 8) | receive_data[21])
                self.data_layer.data['E1_N'] = int(
                    (receive_data[26] << 24) | (receive_data[27] << 16) | (receive_data[24] << 8) | receive_data[25])
                self.data_layer.data['I_TUV'] = int(((receive_data[28]) << 8) | (receive_data[29]))
                self.data_layer.data['P_TUV'] = int(((receive_data[30]) << 8) | (receive_data[31]))
                self.data_layer.data['E_TUV_min'] = int(((receive_data[32]) << 8) | (receive_data[33]))
                self.data_layer.data['E_TUV_hour'] = int(((receive_data[34]) << 8) | (receive_data[35]))
                self.data_layer.data['E_TUV_day'] = int(((receive_data[36]) << 8) | (receive_data[37]))
                self.data_layer.data['P_REGULATION'] = int(((receive_data[38]) << 8) | (receive_data[39]))
                self.data_layer.data['E_TUV'] = int(
                    (receive_data[42] << 24) | (receive_data[43] << 16) | (receive_data[40] << 8) | receive_data[41])

            else:
                self.logger.debug("Timed out waiting for result.")

        except Exception as e:
            self.logger.error("Exception: {}. UART is probably not connected.".format(e))

    def negotiation_relay(self):
        if self.relay.value():
            self.relay.off()
            self.data_layer.data["RELAY"] = 0
            return False
        else:
            self.relay.on()
            self.data_layer.data["RELAY"] = 1
            return True


class DataLayer:
    def __str__(self) -> dict:
        return self.data

    def __init__(self) -> None:
        self.data: dict = dict()
        self.data['HDO'] = 0
        self.data['I1'] = 0
        self.data['U1'] = 0
        self.data['P1'] = 0
        self.data['E1_P_min'] = 0
        self.data['E1_N_min'] = 0
        self.data['E1_P_hour'] = 0
        self.data['E1_N_hour'] = 0
        self.data['E1_P_day'] = 0
        self.data['E1_N_day'] = 0
        self.data['E1_P'] = 0
        self.data['E1_N'] = 0
        self.data['I_TUV'] = 0
        self.data['P_TUV'] = 0
        self.data['E_TUV_min'] = 0
        self.data['E_TUV_hour'] = 0
        self.data['E_TUV_day'] = 0
        self.data['E_TUV'] = 0
        self.data['P_REGULATION'] = 0
        self.data["Pm"] = [0]  # minute power
        self.data["Es"] = [0]  # Hour energy
        self.data['D'] = []  # Daily energy
        self.data['M'] = []  # Monthly energy
        self.data['RUN_TIME'] = 0
        self.data['WATTMETER_TIME'] = 0
        self.data['ID'] = 0


class FileHandler:
    def __init__(self, debug: int) -> None:
        self.logger = ulogging.getLogger("FileHandler")
        if debug == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def read_data(self, file: str):
        try:
            b = mem_free()
            csv_gen = self.csv_reader(file)
            row_count = 0
            data = []
            for row in csv_gen:
                collect()
                row_count += 1

            csv_gen = self.csv_reader(file)
            cnt = 0
            for i in csv_gen:
                cnt += 1
                if cnt > row_count - 31:
                    data.append(i.replace("\n", ""))
                collect()
            self.logger.debug("Mem free before:{}; after:{}; difference:{} ".format(b, mem_free(), b - mem_free()))
            return data
        except Exception as e:
            self.logger.error("Read wattmeter data error: {}.".format(e))
            return []

    def csv_reader(self, file_name: str):
        for row in open(file_name, "r"):
            try:
                yield row
            except StopIteration:
                return

    def get_monthly_energy(self, file: str) -> list[str]:
        energy: list[str] = []
        last_month: int = 0
        last_year: int = 0
        positive_energy: int = 0
        negative_energy: int = 0
        boiler_energy: int = 0

        try:
            b = mem_free()
            csv_gen = self.csv_reader(file)
            for line in csv_gen:
                line = line.replace("\n", "").replace("/", ":").replace("[", "").replace("]", "").replace(",",
                                                                                                          ":").replace(
                    " ", "").split(":")
                self.logger.debug("Mem free before:{}; after:{}; difference:{} ".format(b, mem_free(), b - mem_free()))
                if last_month == 0:
                    last_month = int(line[0])
                    last_year = int(line[2])

                if last_month != int(line[0]):
                    if len(energy) >= 36:
                        energy = energy[1:]

                    energy.append("{}/{}:[{},{},{}]".format(last_month, last_year, positive_energy, negative_energy,
                                                            boiler_energy))

                    positive_energy = 0
                    negative_energy = 0
                    boiler_energy = 0
                    last_month = int(line[0])
                    last_year = int(line[2])

                positive_energy += int(line[3])
                negative_energy += int(line[4])
                boiler_energy += int(line[5])
                collect()

            if len(energy) >= 36:
                energy = energy[1:]
            energy.append(
                "{}/{}:[{},{},{}]".format(last_month, last_year, positive_energy, negative_energy, boiler_energy))

            if energy is None:
                return []
            return energy

        except Exception as e:
            self.logger.error("Get monthly energy error: {}.".format(e))
            return []

    def write_data(self, file: str, data: dict[str, list]) -> None:
        lines = []
        for variable, value in data.items():
            lines.append(("%s:%s\n" % (variable, value)).replace(" ", ""))

        with open(file, "a+") as f:
            f.write(''.join(lines))
