import picoweb
from machine import reset, RTC
from time import time
import ujson as json
from gc import collect, mem_free
import uasyncio as asyncio
import ulogging


class WebServerApp:
    def __init__(self, wlan, wattmeter, watt_io, setting, inverter):
        self.watt_io = watt_io
        self.wifi_manager = wlan
        self.ip_address = self.wifi_manager.get_ip()
        self.wattmeter = wattmeter
        self.inverter = inverter
        self.port = 8000
        self.datalayer = dict()
        self.setting = setting
        self.routes = [
            ("/", self.main),
            ("/datatable", self.data_table),
            ("/overview", self.over_view),
            ("/updateWificlient", self.update_wificlient),
            ("/updateSetting", self.update_setting),
            ("/updateData", self.update_data),
            ("/settings", self.settings),
            ("/powerChart", self.power_chart),
            ("/energyChart", self.energy_chart),
            ("/getEspID", self.get_esp_id),
            ("/modbusRW", self.modbus_rw)
        ]
        self.app = picoweb.WebApp(None, self.routes)

        self.logger = ulogging.getLogger("WebServerApp")
        if int(self.setting.data['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def main(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "main.html")

    def over_view(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "overview.html")

    def settings(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "settings.html", (req,))

    def power_chart(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "powerChart.html", (req,))

    def energy_chart(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "energyChart.html", (req,))

    def modbus_rw(self, req, resp) -> None:
        collect()
        if req.method == "POST":
            datalayer: dict = {}
            req = await self.process_msg(req)
            for i in req.form:
                i = json.loads(i)
                reg = int(i['reg'])
                _id = int(i['id'])
                data = int(i['value'])
                if i['type'] == 'read':
                    try:
                        if _id == 0:
                            async with self.watt_io as w:
                                data = await w.read_wattmeter_register(reg, 1)
                        if len(data) == 0:
                            datalayer = {"process": 0, "value": "Error during reading register"}
                        else:
                            datalayer = {"process": 1, "value": int(((data[0]) << 8) | (data[1]))}

                    except Exception as e:
                        datalayer = {"process": e}

                elif i['type'] == 'write':
                    try:
                        if _id == 0:
                            async with self.watt_io as w:
                                data = await w.write_wattmeter_register(reg, [data])

                        if data is None:
                            datalayer = {"process": 0, "value": "Error during writing register"}
                        else:
                            datalayer = {"process": 1, "value": int(((data[0]) << 8) | (data[1]))}

                    except Exception as e:
                        datalayer = {"process": e}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def update_data(self, req, resp) -> None:
        collect()
        datalayer = {}
        if req.method == "POST":
            req = await self.process_msg(req)
            for i in req.form:
                i = json.loads(i)
                if list(i.keys())[0] == 'relay':
                    if self.wattmeter.negotiation_relay():
                        datalayer = {"process": 1}
                    else:
                        datalayer = {"process": 0}
                elif list(i.keys())[0] == 'time':
                    rtc = RTC()
                    rtc.datetime((int(i["time"][2]), int(i["time"][1]), int(i["time"][0]), 0, int(i["time"][3]),
                                  int(i["time"][4]), int(i["time"][5]), 0))
                    self.wattmeter.start_up_time = time()
                    self.wattmeter.time_init = True
                    datalayer = {"process": "OK"}
            yield from picoweb.jsonify(resp, datalayer)

        else:
            merged_dict = self.wattmeter.data_layer.__str__()
            if self.inverter:
                merged_dict.update(self.inverter.data_layer.__str__())

            merged_json = json.dumps(merged_dict)
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(merged_json)
            collect()

    def update_wificlient(self, req, resp) -> None:
        collect()
        if req.method == "POST":
            size = int(req.headers[b"Content-Length"])
            qs = yield from req.reader.read(size)
            req.qs = qs.decode()
            try:
                i = json.loads(req.qs)
            except:
                pass
            datalayer = await self.wifi_manager.handle_configure(i["ssid"], i["password"])
            self.ip_address = self.wifi_manager.get_ip()
            datalayer = {"process": datalayer, "ip": self.ip_address}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            client = self.wifi_manager.getSSID()
            datalayer = {}
            for i in client:
                if client[i] > -86 and len(i) > 0:
                    datalayer[i] = client[i]
            datalayer["connectSSID"] = self.wifi_manager.getCurrentConnectSSID()

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def update_setting(self, req, resp) -> None:
        collect()
        if req.method == "POST":
            datalayer = {}
            req = await self.process_msg(req)

            for i in req.form:
                i = json.loads(i)
                datalayer = self.setting.handle_configure(i["variable"], i["value"])
                datalayer = {"process": datalayer}

            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

        else:
            datalayer = self.setting.get_config()
            yield from picoweb.start_response(resp, "application/json")
            yield from resp.awrite(json.dumps(datalayer))

    def data_table(self, req, resp) -> None:
        collect()
        yield from picoweb.start_response(resp)
        yield from self.app.render_template(resp, "datatable.html", (req,))

    def get_esp_id(self, req, resp) -> None:
        datalayer = {"ID": " PV-router: {}".format(self.setting.get_config()['ID']), "IP": self.wifi_manager.get_ip()}
        yield from picoweb.start_response(resp, "application/json")
        yield from resp.awrite(json.dumps(datalayer))

    def process_msg(self, req) -> dict:
        size = int(req.headers[b"Content-Length"])
        qs = yield from req.reader.read(size)
        req.qs = qs.decode()
        req.parse_qs()
        return req

    async def web_server_run(self) -> None:
        try:
            self.logger.info("Webserver app started.")
            self.app.run(debug=False, host='', port=self.port)
            while True:
                await asyncio.sleep(100)
        except Exception as e:
            self.logger.error("web_server_run exception: {}.".format(e))
            reset()
