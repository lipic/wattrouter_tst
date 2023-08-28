from main.inverters.base import BaseInverter
from umodbus.tcp import TCP


class Solax(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(Solax, self).__init__(*args, **kwargs)
        self.modbus_port: int = 502
        self.modbus_tcp: TCP = None
        self.device_type: int = 0x7
        self.data_layer.data["type"] = "Solax"

    async def run(self):
        self.data_layer.data["status"] = self.connection_status
        if self.modbus_tcp is not None:
            try:
                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=0xCA, register_qty=6)
                self.process_msg(response, starting_addr=0xCA)

                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=0XBE, register_qty=1)
                self.process_msg(response, starting_addr=0XBE)
                self.reconnect_error_cnt = 0
                self.data_layer.data["ip"] = self.set_ip_address

            except Exception as e:
                self.logger.error(f"Modbus TCP error: {e}")
                self.reconnect_error_cnt += 1
                if self.reconnect_error_cnt > self.max_reconnect_error_cnt:
                    self.data_layer.data["status"] = 2
                    await self.try_reconnect(modbus_port=self.modbus_port,
                                             ip_address=self.set_ip_address,
                                             slave_addr=1,
                                             starting_addr=self.device_type,
                                             number_of_reg=6,
                                             callback=self.check_msg)

    async def scann(self) -> None:
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.get_ip(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=6,
                                                       callback=self.check_msg)

    def process_msg(self, response: tuple, starting_addr: int) -> None:

        if starting_addr == 0xCA:
            self.data_layer.data["u1"] = int(response[0])
            self.data_layer.data["u2"] = int(response[1])
            self.data_layer.data["u3"] = int(response[2])
            self.data_layer.data["i1"] = int(response[3])
            self.data_layer.data["i2"] = int(response[4])
            self.data_layer.data["i3"] = int(response[5])

        elif starting_addr == 0XBE:
            self.data_layer.data["soc"] = int(response[0])

    def check_msg(self, result: tuple) -> bool:
        print(result)
        device_type = ''
        for i in result:
            if i != 0:
                device_type = f"{device_type}{chr(i >> 8)}{chr(i & 0xFF)}"
        self.logger.info(f"Device type: {device_type}")
        if f"{device_type[0].lower()}{device_type[1].lower()}{device_type[2].lower()}" == "sol":
            self.data_layer.data['id'] = device_type
            return True
        return False

    def wattmeter_register_table(self) -> dict:
        return {"u1": 0xCA,
                "u2": 0xCB,
                "u3": 0xCC,
                "i1": 0xCE,
                "i2": 0xCF,
                "i3": 0xD0,
                }

    def bms_register_table(self) -> dict:
        return {"soc": 0XBE}
