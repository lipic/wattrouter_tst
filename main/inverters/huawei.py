from main.inverters.base import BaseInverter
from umodbus.tcp import TCP


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

                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=37004, register_qty=1)
                self.process_msg(response, starting_addr=37004)
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
                                             number_of_reg=15,
                                             callback=self.check_msg)

    async def scann(self) -> None:
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.get_ip(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=15,
                                                       callback=self.check_msg)

    def process_msg(self, response: tuple, starting_addr: int) -> None:

        if starting_addr == 37101:
            register_table: dict = self.wattmeter_register_table()
            for key in register_table:
                self.data_layer.data[key] = (response[register_table[key] - starting_addr] << 16) | (response[register_table[key] - starting_addr+1])

        elif starting_addr == 37004:
            register_table: dict = self.bms_register_table()
            for key in register_table:
                self.data_layer.data[key] = int(response[register_table[key] - starting_addr]/10)

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
