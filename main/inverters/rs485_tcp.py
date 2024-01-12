from main.inverters.base import BaseInverter
from umodbus.tcp import TCP
from gc import collect

collect()


class RS485_Tcp(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(RS485_Tcp, self).__init__(*args, **kwargs)
        self.modbus_port: int = 502
        self.modbus_tcp: TCP = None
        self.device_type: int = 50
        self.data_layer.data["type"] = "RS485/TCP"

    async def run(self):
        self.data_layer.data["status"] = self.connection_status
        if self.modbus_tcp is not None:
            try:
                response = self.modbus_tcp.read_holding_registers(slave_addr=1, starting_addr=0, register_qty=11)
                self.process_msg(response, starting_addr=0x0)
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
                    self.data_layer.data["status"] = 2
                    self.modbus_tcp = await self.try_reconnect(modbus_port=self.modbus_port,
                                                               ip_address=self.set_ip_address,
                                                               slave_addr=1,
                                                               starting_addr=self.device_type,
                                                               number_of_reg=12,
                                                               callback=self.check_msg)
                    collect()
        else:
            await self.inverter.scann()

    async def scann(self) -> None:
        self.data_layer.data["status"] = 2
        self.modbus_tcp: TCP = await self.scan_network(modbus_port=self.modbus_port,
                                                       ip_address=self.wifi_manager.get_ip(),
                                                       slave_addr=1,
                                                       starting_addr=self.device_type,
                                                       number_of_reg=12,
                                                       callback=self.check_msg)
        collect()

    def process_msg(self, response: tuple, starting_addr: int) -> None:

        if starting_addr == 0x0:
            print(response)
            self.data_layer.data["u1"] = int(response[0])
            self.data_layer.data["u2"] = int(response[1])
            self.data_layer.data["u3"] = int(response[2])
            self.data_layer.data["i1"] = int(response[3])
            self.data_layer.data["i2"] = int(response[4])
            self.data_layer.data["i3"] = int(response[5])
            self.data_layer.data["p1"] = int(response[6])
            self.data_layer.data["p2"] = int(response[7])
            self.data_layer.data["p3"] = int(response[8])
            self.data_layer.data["soc"] = int(response[9])

    def check_msg(self, result: tuple) -> bool:
        device_type = ''
        for i in result:
            if i != 0:
                device_type = f"{device_type}{chr(i)}"
        if device_type.startswith('-'):
            device_type = device_type[1:].split('-')
            self.data_layer.data['id'] = device_type[1]
            self.data_layer.data["type"] = device_type[0]
            self.logger.info(f"Device type: {device_type[0]}:{device_type[1]}")
            return True
        return False
