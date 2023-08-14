from main.inverters.base import BaseInverter
from umodbus.tcp import TCP


class Goodwe(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(Goodwe, self).__init__(*args, **kwargs)
        self.modbus_port: int = 502
        self.modbus_tcp: TCP = None
        self.device_type: int = 35011
        self.data_layer.data["type"] = "Goodwe"

    async def run(self):
        self.data_layer.data["status"] = self.connection_status
        if self.modbus_tcp is not None:
            try:
                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=36005, register_qty=3)
                self.process_msg(response, starting_addr=36005)

                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=37007, register_qty=1)
                self.process_msg(response, starting_addr=37007)

                self.reconnect_error_cnt = 0
                self.data_layer.data["ip"] = self.set_ip_address

            except Exception as e:
                self.logger.error(f"Modbus TCP error {e}")
                self.reconnect_error_cnt += 1
                if self.reconnect_error_cnt > self.max_reconnect_error_cnt:
                    await self.try_reconnect(modbus_port=self.modbus_port,
                                             ip_address=self.set_ip_address,
                                             slave_addr=1,
                                             starting_addr=self.device_type,
                                             number_of_reg=5,
                                             callback=self.check_msg)

    async def scann(self) -> None:
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.getIp(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=5,
                                                       callback=self.check_msg)

    def process_msg(self, response: tuple, starting_addr: int) -> None:
        if starting_addr == 36005:
            if len(response) > 2:
                self.data_layer.data["u1"] = self.wattmeter.data_layer.data["U1"] if self.wattmeter.data_layer.data["U1"] != 0 else 1
                self.data_layer.data["i1"] = int(response[0]*10/self.data_layer.data["u1"])
                self.data_layer.data["u2"] = self.wattmeter.data_layer.data["U2"] if self.wattmeter.data_layer.data["U2"] != 0 else 1
                self.data_layer.data["i2"] = int(response[1]*10 / self.data_layer.data["u2"])
                self.data_layer.data["u3"] = self.wattmeter.data_layer.data["U3"] if self.wattmeter.data_layer.data["U3"] != 0 else 1
                self.data_layer.data["i3"] = int(response[2]*10 / self.data_layer.data["u3"])
        elif starting_addr == 37007:
            if len(response) > 0:
                self.data_layer.data["soc"] = response[0]

    def check_msg(self, result: tuple) -> bool:
        device_type = ''
        for i in result:
            if i != 0:
                device_type = f"{device_type}{chr(i >> 8)}{chr(i & 0xFF)}"
        self.data_layer.data['id'] = device_type
        self.logger.info(f"Device type: {device_type}")
        if f"{device_type[0].lower()}{device_type[1].lower()}" == "gw":
            return True
        return False
