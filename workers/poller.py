from PyQt5.QtCore import QThread, pyqtSignal
import time
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from controllers.detector import detect_controllers
from models.controller import Controller, ControllerType, ConnectionType
from os_layer import get_battery_provider

logger = logging.getLogger("gamepad_manager")

#   Classe responsável por detectar os controladores conectados e obter suas informações,
# incluindo o nível de bateria, se disponível. Ele roda em uma thread separada para não
# bloquear a interface do usuário. O resultado é emitido através de um sinal para que
# a interface possa ser atualizada.
#   O poller verifica periodicamente (a cada 2 segundos) se houve mudanças nos controladores
# detectados e só emite um sinal de atualização se houver alguma mudança, para evitar 
# atualizações desnecessárias na interface. Ele também lida com possíveis erros durante
# a detecção e obtenção de informações dos controladores, garantindo que o aplicativo
# continue funcionando mesmo que haja problemas com algum dispositivo.
#   O uso de um ThreadPoolExecutor para obter as informações de bateria permite que o
# processo seja mais eficiente, especialmente se houver vários controladores conectados,
# já que as consultas de bateria podem ser feitas em paralelo.
#   O método _parse_controller_type converte a string de tipo do detector para o enum
#   ControllerType usado na aplicação, enquanto o método _detect_connection_type tenta
# determinar se o controlador está conectado via USB ou Bluetooth com base no caminho
# do dispositivo.
#   O resultado final é uma lista de objetos Controller, cada um contendo o nome,
#  tipo, método de conexão e nível de bateria (se disponível) do controlador, que é
#  então emitida para a interface atualizar a exibição dos controladores conectados.



class ControllerPoller(QThread):
    updated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.battery_provider = get_battery_provider()
        self.last_controllers = None  # None to force first update
        self.battery_executor = ThreadPoolExecutor(max_workers=4)
        provider_name = type(self.battery_provider).__name__ if self.battery_provider else "None"
        logger.info(f"Battery diagnostics: provider={provider_name}")

    def run(self):
        while True:
            controllers = self.scan()
            
            # Only emit signal if controllers changed
            if self._controllers_changed(controllers):
                self.updated.emit(controllers)
                self.last_controllers = controllers
            
            time.sleep(2)

    def scan(self):
        """Detect connected controllers and get their battery info."""
        try:
            detected = detect_controllers()
            controllers = []
            logger.debug(f"Battery diagnostics: detected {len(detected)} controller candidate(s)")

            # Get batteries asynchronously
            battery_futures = {}
            for scan_index, device in enumerate(detected):
                indexed_device = dict(device)
                indexed_device["index"] = scan_index % 4
                logger.debug(
                    "Battery diagnostics: device "
                    f"name={indexed_device.get('name')} vid=0x{indexed_device.get('vid', 0):04X} "
                    f"pid=0x{indexed_device.get('pid', 0):04X} connection={indexed_device.get('connection')} "
                    f"xinput_index_hint={indexed_device.get('index')}"
                )
                if self.battery_provider:
                    future = self.battery_executor.submit(
                        self.battery_provider.get_battery, indexed_device
                    )
                    battery_futures[id(indexed_device)] = (indexed_device, future)
                else:
                    # No battery provider, create controller without battery
                    controller = Controller(
                        name=indexed_device["name"],
                        ctype=self._parse_controller_type(indexed_device["type"]),
                        connection=indexed_device["connection"],
                        battery=None
                    )
                    controllers.append(controller)
                    logger.debug(
                        f"Battery diagnostics: no provider, defaulting battery=None for {indexed_device.get('name')}"
                    )

            # Collect battery results
            for device_id, (device, future) in battery_futures.items():
                try:
                    battery = future.result(timeout=1.0)  # 1 second timeout per device
                    logger.debug(
                        f"Battery diagnostics: provider result for {device.get('name')} -> {battery}"
                    )
                except Exception as e:
                    battery = None
                    logger.warning(
                        f"Battery diagnostics: provider failed for {device.get('name')}: {e}"
                    )

                controller = Controller(
                    name=device["name"],
                    ctype=self._parse_controller_type(device["type"]),
                    connection=device["connection"],
                    battery=battery
                )
                controllers.append(controller)

            logger.debug(
                "Battery diagnostics: final controllers="
                + ", ".join(
                    f"{c.name}(type={c.type.value}, conn={c.connection.value}, battery={c.battery})"
                    for c in controllers
                )
            )

            return controllers
        except Exception as e:
            logger.error(f"Error scanning controllers: {e}", exc_info=True)
            return []

    def _controllers_changed(self, controllers):
        """Check if controller list has changed."""
        # Force first update
        if self.last_controllers is None:
            return True
            
        if len(controllers) != len(self.last_controllers):
            return True
        
        # Check if any controller info changed
        for new, old in zip(controllers, self.last_controllers):
            if (new.name != old.name or 
                new.type != old.type or 
                new.connection != old.connection or
                new.battery != old.battery):
                return True
        
        return False

    def _parse_controller_type(self, type_string):
        """Convert detector type string to ControllerType enum."""
        mapping = {
            "Xbox": ControllerType.XBOX,
            "PlayStation": ControllerType.PLAYSTATION,
            "Nintendo": ControllerType.NINTENDO,
            "GameSir": ControllerType.GAMESIR,
        }
        return mapping.get(type_string, ControllerType.UNKNOWN)
