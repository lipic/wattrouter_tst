from main.inverters.base import BaseInverter
from umodbus.tcp import TCP


class Infigy(BaseInverter):

    def __init__(self, *args, **kwargs):
        super(Infigy, self).__init__(*args, **kwargs)
        self.data_layer.data["type"] = "Infigy"

    async def run(self):
        pass

    async def scann(self) -> None:
        pass

