from machine import Pin, PWM
from collections import OrderedDict
import ulogging

SSR1_PIN: int = 33
SSR2_PIN: int = 23
FREQUENCY: int = 5
WATTER_CONST: int = 4180
MODE_OFF: int = 0
MODE_HDO: int = 1
MODE_BOOST: int = 2
MODE_HDO_BOOST: int = 3

PWM_MAX: int = 1023
PWM_OFF: int = 0


class Regulation:

    def __init__(self, wattmeter, config: OrderedDict[str, str]) -> None:

        self.power_hyst: int = 0
        self.power_step_count: int = 0
        self.power_step: int = 0
        self.ssr1: PWM = PWM(Pin(SSR1_PIN), FREQUENCY)
        self.config: OrderedDict[str, str] = config
        self.wattmeter = wattmeter
        self.target_power: int = 0
        self.temp_input: int = 10
        self.tuv_energy_night: int = 0
        self.tuv_energy_morning: int = 0
        self.overflow_limit: int = -30  # limit pro handlovani pretoku
        self.delay: int = 0

        self.target_duty: int = 0
        self.sec_night_boost: int = 0  # kolik sekund se musinahrivat aby se dosahlo teloty boostu
        self.sec_morning_boost: int = 0
        self.power_simulator: int = 0

        self.logger = ulogging.getLogger("Regulation")
        if int(self.config.data['sw,TESTING SOFTWARE']) == 1:
            self.logger.setLevel(ulogging.DEBUG)
        else:
            self.logger.setLevel(ulogging.INFO)

    def run(self, hour: int, minute: int, power: int) -> None:
        """
        Regulation function. 100% pwm = 1023, 0% pwm = 0
        """
        self.logger.debug("#################################################")
        if power > 32767:  # max kladne cislo
            power = power - 65536  # uint16 vcetne 0

        actual_time: int = hour * 3600 + minute * 60
        '''
        self.config.data['btn,BOOST-MODE']
        self.config.data['in,TUV-VOLUME']
        self.config.data['in,TUV-POWER']
        self.config.data['in,NIGHT-BOOST']
        self.config.data['in,NIGHT-TEMPERATURE']
        self.config.data['in,MORNING-BOOST']
        self.config.data['in,MORNING-TEMPERATURE']
        self.config.data['in,BOOST-TIMEOUT']
        self.config.data['BOOST']
        '''
        self.power_step = int(self.config.data['in,TUV-POWER']) / (1000 / FREQUENCY / 20)  # 1000ms 20ms
        self.power_step_count = int(self.config.data['in,TUV-POWER']) / self.power_step
        self.power_hyst = self.power_step / 4  # hystereze regulace 1/4 minimalniho kroku
        # vypocet energie pro nocni boost
        self.tuv_energy_night = WATTER_CONST * int(self.config.data['in,TUV-VOLUME']) * (
                    int(self.config.data['in,NIGHT-TEMPERATURE']) - self.temp_input) / 3600
        # vypocet sekund se ma nahrivat nocni boost, pocitejme ze 1/4 v bojleru zustala, takze 3/4
        self.sec_night_boost = self.tuv_energy_night * 3600 * 3 / 4 / int(self.config.data['in,TUV-POWER'])
        # vypocet energie pro ranni boost
        self.tuv_energy_morning = WATTER_CONST * int(self.config.data['in,TUV-VOLUME']) * (
                    int(self.config.data['in,MORNING-TEMPERATURE']) - self.temp_input) / 3600
        # vypocet sekund se ma nahrivat ranni boost, pocitejme ze 1/4 v bojleru zustala, takze 3/4
        self.sec_morning_boost = self.tuv_energy_night * 3600 * 3 / 4 / int(self.config.data['in,TUV-POWER'])

        self.logger.debug("Power = {}W".format(power))
        
        self.delay += 1
        if self.delay > 2:
            # regulace podle pretoku celych periodach 20ms
            if power < self.overflow_limit:
                self.delay = 0
                self.logger.debug("Přidávám")
                if power < (-self.power_hyst):
                    self.target_power += self.power_step
                    if self.target_power > int(self.config.data['in,TUV-POWER']):
                        self.target_power = int(self.config.data['in,TUV-POWER'])
            elif power > self.power_hyst:
                self.delay = 0
                self.logger.debug("Ubírám")
                self.target_power -= self.power_step
                if self.target_power < 0:
                    self.target_power = 0

        # pokud je aktivovany nejaky BOOST
        if int(self.config.data['btn,BOOST-MODE']) == MODE_BOOST:

            if self.get_boost_status(actual_time):
                self.target_power = int(self.config.data['in,TUV-POWER'])
                self.logger.debug("SSR sepnuto casovym boostem")

        elif int(self.config.data['btn,BOOST-MODE']) == MODE_HDO:

            if self.wattmeter.data_layer.data['HDO'] != 0:
                self.target_power = int(self.config.data['in,TUV-POWER'])
                self.logger.debug("SSR sepnuto HDOckem")

        elif int(self.config.data['btn,BOOST-MODE']) == MODE_HDO_BOOST:
            if self.get_boost_status(actual_time) and self.wattmeter.data_layer.data['HDO'] != 0:
                self.target_power = int(self.config.data['in,TUV-POWER'])
                self.logger.debug("ssr sepnuto casovym boostem a soucasne HDO")

        # manualni boost
        if int(self.config.data['BOOST']):
            self.target_power = int(self.config.data['in,TUV-POWER'])
            self.logger.debug("SSR sepnuto manualne v overview")

        # strida
        self.target_duty = int((self.target_power / int(self.config.data['in,TUV-POWER'])) * 1024)
        if self.target_duty > PWM_MAX:
            self.target_duty = PWM_MAX
        self.logger.debug("Target duty: {}".format(self.target_duty))
        self.logger.debug("Target power: {}W".format(self.target_power))
        self.ssr1.duty(self.target_duty)

    def get_boost_status(self, time_sec: int) -> bool:
        if (int(self.config.data['in,NIGHT-BOOST']) - self.sec_night_boost) < time_sec < int(
                self.config.data['in,NIGHT-BOOST']):
            return True
        elif (int(self.config.data['in,MORNING-BOOST']) - self.sec_morning_boost) < time_sec < int(
                self.config.data['in,MORNING-BOOST']):
            return True
        else:
            return False
