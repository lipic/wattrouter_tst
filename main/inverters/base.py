from umodbus.tcp import TCP
import uasyncio as asyncio
from collections import OrderedDict
import ulogging

UNCONNECTED: int = 0
CONNECTED: int = 1
SEARCHING: int = 2


class BaseInverter:
    def __init__(self, wifi_manager, config, wattmeter=None):
        self.wifi_manager = wifi_manager
        self.start_ip: int = 1
        self.end_ip: int = 254
        self.data_layer: Datalayer = Datalayer()
        self.config: object = config
        self.set_ip_address: str = self.config.data['INVERTER_IP_ADDR']
        self.connection_status: int = UNCONNECTED
        self.reconnect_error_cnt: int = 0
        self.max_reconnect_error_cnt: int = 10
        self.wattmeter = wattmeter

        self.logger = ulogging.getLogger(__name__)
        if int(self.config.data['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    async def run(self):
        raise NotImplementedError("Implement me!")

    async def scann(self):
        raise NotImplementedError("Implement me!")

    def process_msg(self):
        raise NotImplementedError("Implement me!")

    async def scan_ip_address(self, ip_address: str, modbus_port: int, slave_addr: int, starting_addr: int,
                              number_of_reg: int, clbck: callable) -> TCP | None:
        reader = None
        writer = None
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip_address, modbus_port), timeout=2)
        except asyncio.TimeoutError:
            pass
        if writer is not None and reader is not None:
            writer.close()
            await writer.wait_closed()
            modbus_tcp = TCP(slave_ip=ip_address, slave_port=modbus_port, timeout=5)
            response = None
            for i in range(0, 3):
                try:
                    response = modbus_tcp.read_holding_registers(slave_addr=slave_addr,
                                                                 starting_addr=starting_addr,
                                                                 register_qty=number_of_reg)
                except Exception as e:
                    self.logger.error(f"Timeout error occurs: {e}")

            if clbck(response) is True:
                self.connection_status = CONNECTED
                self.set_ip_address = ip_address
                self.config.handle_configure(variable="INVERTER_IP_ADDR", value=ip_address)
                return modbus_tcp

        writer.close()
        await writer.wait_closed()
        return None

    async def scan_network(self, modbus_port: int, ip_address: str, slave_addr: int, starting_addr: int,
                           number_of_reg: int, callback: callable) -> TCP:
        if self.set_ip_address != '0':
            response = await self.try_reconnect(modbus_port, self.set_ip_address, slave_addr, starting_addr,
                                                number_of_reg, callback)
            if response is not None:
                return response

        ip_address_base = '.'.join(ip_address.split('.')[:3])
        for ip_suffix in range(self.start_ip, self.end_ip + 1):
            self.connection_status = SEARCHING
            ip_address = ip_address_base + f".{ip_suffix}"
            try:
                self.logger.info(f"Try found inverter on ip address: {ip_address}")
                result = await self.scan_ip_address(ip_address, modbus_port, slave_addr, starting_addr, number_of_reg, callback)
                if result is not None:
                    self.logger.info(f"Device found on ip address: {ip_address}")
                    return result
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                self.logger.info(e)
        self.connection_status = UNCONNECTED

    async def try_reconnect(self, modbus_port: int, ip_address: str, slave_addr: int, starting_addr: int,
                            number_of_reg: int, callback: callable) -> TCP | None:
        for i in range(0, 5):
            try:
                self.logger.info(f"Try to reconnect on ip address: {ip_address}")
                result = await self.scan_ip_address(ip_address, modbus_port, slave_addr, starting_addr, number_of_reg,
                                                    callback)
                if result is not None:
                    self.logger.info(f"Device found on ip address: {ip_address}")
                    return result
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                self.logger.info(e)
                self.connection_status = UNCONNECTED
            await asyncio.sleep(2)
        return None


class Datalayer:
    def __str__(self):
        return self.data

    def __init__(self):
        self.data = OrderedDict()
        self.data["soc"]: int = 0
        self.data["u1"]: int = 0
        self.data["u2"]: int = 0
        self.data["u3"]: int = 0
        self.data["i1"]: int = 0
        self.data["i2"]: int = 0
        self.data["i3"]: int = 0
        self.data["p1"]: int = 0
        self.data["p2"]: int = 0
        self.data["p3"]: int = 0
        self.data["status"]: int = 0
        self.data["id"]: str = "-,-"
        self.data["ip"]: str = ""
        self.data["type"]: str = ""
