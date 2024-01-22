from main.inverters.base import BaseInverter
from umodbus.tcp import TCP
from gc import collect
from asyncio import sleep

collect()


class Huawei(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(Huawei, self).__init__(*args, **kwargs)
        self.modbus_port: int = 502
        self.modbus_tcp: TCP = None
        self.device_type: int = 30000
        self.data_layer.data["type"] = "Huawei"

    async def run(self):
        self.data_layer.data["status"] = self.connection_status
        if self.modbus_tcp is not None:
            try:
                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=37101, register_qty=12)
                self.process_msg(response, starting_addr=37101)
                await sleep(1)
                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=37004, register_qty=1)
                self.process_msg(response, starting_addr=37004)
                self.reconnect_error_cnt = 0
                self.data_layer.data["ip"] = self.set_ip_address

            except Exception as e:
                if e.errno == 128:
                    self.logger.error("Socket not connected (ENOTCONN)")
                    self.reconnect_error_cnt = 10
                elif e.errno == 116:
                    self.logger.error("Socket timeout (ETIMEDOUT)")
                elif e.errno == 104:
                    self.logger.error("Socket connection reset (ECONNRESET)")
                else:
                    self.logger.error(f"Modbus TCP error: {e}")

                self.reconnect_error_cnt += 1
                if self.reconnect_error_cnt > self.max_reconnect_error_cnt:
                    self.reconnect_error_cnt = 0
                    self.data_layer.data["status"] = 2
                    self.modbus_tcp = await self.try_reconnect(modbus_port=self.modbus_port,
                                                               ip_address=self.set_ip_address,
                                                               slave_addr=1,
                                                               starting_addr=self.device_type,
                                                               number_of_reg=15,
                                                               callback=self.check_msg)
                    collect()
        else:
            await self.scann()

    async def scann(self) -> None:
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.get_ip(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=15,
                                                       callback=self.check_msg)
        collect()

    def process_msg(self, response: tuple, starting_addr: int) -> None:

        if starting_addr == 37101:
            self.data_layer.data["u1"] = int((response[0] << 16) | int((response[1]) / 10))
            self.data_layer.data["u2"] = int((response[2] << 16) | int((response[3]) / 10))
            self.data_layer.data["u3"] = int((response[4] << 16) | int((response[5]) / 10))
            self.data_layer.data["i1"] = -1 * int((response[6] << 16) | (response[7]))
            self.data_layer.data["i2"] = -1 * int((response[8] << 16) | (response[9]))
            self.data_layer.data["i3"] = -1 * int((response[10] << 16) | (response[11]))
            self.data_layer.data["p1"] = int((self.data_layer.data["u1"] * self.data_layer.data["i1"]) / 100)
            self.data_layer.data["p2"] = int((self.data_layer.data["u2"] * self.data_layer.data["i2"]) / 100)
            self.data_layer.data["p3"] = int((self.data_layer.data["u3"] * self.data_layer.data["i3"]) / 100)

        elif starting_addr == 37004:
            self.data_layer.data["soc"] = int(response[0] / 10)

    def check_msg(self, result: tuple) -> bool:
        device_type = ''
        for i in result:
            if i != 0:
                device_type = f"{device_type}{chr(i >> 8)}{chr(i & 0xFF)}"
        self.logger.info(f"Device type: {device_type}")
        if f"{device_type[0].lower()}{device_type[1].lower()}{device_type[2].lower()}" == "sun":
            self.data_layer.data['id'] = device_type
            return True
        return False

    def wattmeter_register_table(self) -> dict:
        return {"u1": 37101,
                "i1": 37107,
                "u2": 37103,
                "i2": 37109,
                "u3": 37105,
                "i3": 37111,
                }

    def bms_register_table(self) -> dict:
        return {"soc": 37004}
